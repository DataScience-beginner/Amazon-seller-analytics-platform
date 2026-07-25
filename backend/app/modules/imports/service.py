from __future__ import annotations

import hashlib
import logging
import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings
from app.core.errors import ApplicationError, ConflictError, NotFoundError
from app.models.domain import (
    AuditEvent,
    ImportBatch,
    ImportColumn,
    ImportRowError,
    ImportStatus,
    MappingSource,
    MappingStatus,
    Marketplace,
    Product,
    ProductSnapshot,
    RawAttribute,
    RowErrorSeverity,
    SnapshotKind,
    StrategyRecommendation,
)
from app.models.domain import (
    ScoreResult as ScoreResultRecord,
)
from app.modules.imports.dataset_schema import (
    DatasetColumnClassification,
    DatasetSchemaInspection,
    ProductFinderDatasetSchema,
    observation_date_candidates,
    suggest_observed_on,
)
from app.modules.imports.domain import (
    MappingClassification,
    MappingReport,
    SourceColumn,
    WorkbookInspection,
    WorkbookInspectionError,
    WorkbookRow,
    WorkbookSafetyLimits,
)
from app.modules.imports.registry import AliasRegistry, RegistryValidationError
from app.modules.imports.schemas import (
    ConfirmImportCommand,
    ImportDatasetResponse,
    ImportDetailResponse,
    ImportFailure,
    ImportListItem,
    ImportListResponse,
    ImportSummary,
    ImportWorkbook,
    MappingColumnResponse,
    MappingResponse,
    MappingUpdate,
    PreviewRowResponse,
)
from app.modules.imports.storage import StagedUpload, remove_staged_upload
from app.modules.imports.workbook import inspect_workbook, iter_workbook_rows
from app.modules.scoring.engine import score_market_metrics
from app.modules.scoring.types import MarketMetrics, ScoreCard
from app.modules.strategies.classifier import StrategyClassifier
from app.modules.strategies.models import MarketScores, StrategyContext, StrategyDecision

logger = logging.getLogger(__name__)

_ASIN_PATTERN = re.compile(r"^[A-Z0-9]{10}$")
_QUERY_CHUNK_SIZE = 500
_SNAPSHOT_FLUSH_CHUNK_SIZE = 100
_POSTGRES_RETRYABLE_SQLSTATES = frozenset({"40001", "40P01", "55P03"})


@dataclass(frozen=True, slots=True)
class _ValidRow:
    row: WorkbookRow
    asin: str


def workbook_limits(settings: Settings) -> WorkbookSafetyLimits:
    return WorkbookSafetyLimits(
        max_archive_bytes=settings.max_upload_size_bytes,
        max_total_uncompressed_bytes=settings.max_workbook_uncompressed_bytes,
        max_worksheets=settings.max_workbook_sheets,
        max_columns=settings.max_workbook_columns,
        preview_rows=settings.import_preview_rows,
        max_data_scan_rows=settings.max_workbook_rows,
        max_data_rows=settings.max_workbook_rows,
    )


def create_import_for_workspace(
    session: Session,
    staged: StagedUpload,
    settings: Settings,
    *,
    organisation_id: str,
    marketplace_id: str,
) -> ImportDetailResponse:
    _get_marketplace(session, organisation_id=organisation_id, marketplace_id=marketplace_id)
    existing = session.scalar(
        select(ImportBatch)
        .options(selectinload(ImportBatch.columns), selectinload(ImportBatch.row_errors))
        .where(
            ImportBatch.organisation_id == organisation_id,
            ImportBatch.marketplace_id == marketplace_id,
            ImportBatch.checksum == staged.checksum_sha256,
        )
    )
    if existing is not None:
        remove_staged_upload(staged)
        return _detail_response(existing, registry=AliasRegistry.default(), duplicate=True)

    registry = AliasRegistry.default()
    try:
        inspection = inspect_workbook(
            staged.path,
            registry,
            limits=workbook_limits(settings),
        )
    except WorkbookInspectionError as exc:
        failed = _new_batch(
            staged,
            organisation_id=organisation_id,
            marketplace_id=marketplace_id,
        )
        failed.status = ImportStatus.failed
        failed.failure_code = exc.code.value
        failed.failure_message = exc.user_message
        failed.storage_key = None
        session.add(failed)
        session.add(
            _audit_event(
                organisation_id=organisation_id,
                event_type="import.validation_failed",
                entity_type="import_batch",
                entity_id=failed.id,
                payload={"failure_code": exc.code.value},
            )
        )
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
        remove_staged_upload(staged)
        raise ApplicationError(
            exc.code.value,
            exc.user_message,
            status_code=422,
            details={"import_id": failed.id, **exc.details},
        ) from exc

    batch = _new_batch(
        staged,
        organisation_id=organisation_id,
        marketplace_id=marketplace_id,
    )
    batch.workbook_sheet_name = inspection.selected_sheet
    batch.header_row_number = inspection.header_row
    batch.alias_registry_version = registry.version
    _apply_dataset_metadata(batch, inspection)
    session.add(batch)
    _apply_mapping_report(batch, inspection)
    session.add(
        _audit_event(
            organisation_id=organisation_id,
            event_type="import.uploaded",
            entity_type="import_batch",
            entity_id=batch.id,
            payload={
                "checksum": batch.checksum,
                "mapping_requires_confirmation": inspection.mapping.requires_confirmation,
                "dataset_schema_id": batch.dataset_schema_id,
                "dataset_schema_version": batch.dataset_schema_version,
                "dataset_schema_match": batch.dataset_schema_match,
                "observed_on_suggestion": (
                    batch.observed_on_suggestion.isoformat()
                    if batch.observed_on_suggestion is not None
                    else None
                ),
                "observation_suggestion_source": batch.observation_suggestion_source,
            },
        )
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        duplicate = session.scalar(
            select(ImportBatch)
            .options(selectinload(ImportBatch.columns), selectinload(ImportBatch.row_errors))
            .where(
                ImportBatch.organisation_id == organisation_id,
                ImportBatch.marketplace_id == marketplace_id,
                ImportBatch.checksum == staged.checksum_sha256,
            )
        )
        remove_staged_upload(staged)
        if duplicate is None:
            raise ConflictError(
                "import_conflict",
                "The workbook could not be registered because of a concurrent change",
            ) from exc
        return _detail_response(duplicate, registry=registry, duplicate=True)
    session.refresh(batch)
    return _detail_response(batch, registry=registry, inspection=inspection)


def list_imports(
    session: Session,
    *,
    organisation_id: str,
    marketplace_id: str,
) -> ImportListResponse:
    _get_marketplace(session, organisation_id=organisation_id, marketplace_id=marketplace_id)
    batches = session.scalars(
        select(ImportBatch)
        .options(selectinload(ImportBatch.row_errors))
        .where(
            ImportBatch.organisation_id == organisation_id,
            ImportBatch.marketplace_id == marketplace_id,
        )
        .order_by(ImportBatch.uploaded_at.desc(), ImportBatch.id.desc())
    ).all()
    return ImportListResponse(
        items=[
            ImportListItem(
                id=batch.id,
                original_filename=batch.original_filename,
                status=batch.status.value,
                uploaded_at=batch.uploaded_at,
                completed_at=batch.completed_at,
                observed_on=batch.observed_on,
                period_month=batch.period_month,
                revision=batch.dataset_revision,
                summary=_summary(batch) if batch.status is ImportStatus.completed else None,
            )
            for batch in batches
        ]
    )


def get_import(
    session: Session,
    import_id: str,
    settings: Settings,
    *,
    organisation_id: str,
    marketplace_id: str,
) -> ImportDetailResponse:
    batch = _get_batch(
        session,
        import_id,
        organisation_id=organisation_id,
        marketplace_id=marketplace_id,
    )
    registry = AliasRegistry.default()
    inspection = _try_load_inspection(batch, registry, settings)
    return _detail_response(batch, registry=registry, inspection=inspection)


def update_mapping(
    session: Session,
    import_id: str,
    command: MappingUpdate,
    settings: Settings,
    *,
    organisation_id: str,
    marketplace_id: str,
) -> ImportDetailResponse:
    batch = _get_batch(
        session,
        import_id,
        organisation_id=organisation_id,
        marketplace_id=marketplace_id,
        for_update=True,
    )
    if batch.status is not ImportStatus.pending:
        raise ConflictError(
            "import_not_pending",
            "Only a pending import can have its mapping changed",
        )
    registry = AliasRegistry.default()
    if batch.alias_registry_version != registry.version:
        raise ConflictError(
            "alias_registry_version_mismatch",
            "The import was created with a different alias registry version",
        )
    path = _batch_path(batch, settings)
    existing_user_decisions = {
        column.source_column_ordinal: column.canonical_field
        for column in batch.columns
        if column.mapping_source is MappingSource.user
    }
    explicit_mappings = {**existing_user_decisions, **command.mappings}
    try:
        inspection = inspect_workbook(
            path,
            registry,
            explicit_mappings=explicit_mappings,
            limits=workbook_limits(settings),
        )
    except (WorkbookInspectionError, RegistryValidationError, ValueError) as exc:
        message = str(exc)
        code = exc.code.value if isinstance(exc, WorkbookInspectionError) else "invalid_mapping"
        raise ApplicationError(code, message, status_code=422) from exc

    if inspection.checksum_sha256 != batch.checksum:
        raise ConflictError("workbook_changed", "The staged workbook no longer matches this import")
    _apply_mapping_report(batch, inspection)
    session.add(
        _audit_event(
            organisation_id=batch.organisation_id,
            event_type="import.mapping_updated",
            entity_type="import_batch",
            entity_id=batch.id,
            payload={"ordinals": sorted(command.mappings)},
        )
    )
    session.commit()
    session.refresh(batch)
    return _detail_response(batch, registry=registry, inspection=inspection)


def confirm_import(
    session: Session,
    import_id: str,
    command: ConfirmImportCommand,
    settings: Settings,
    *,
    organisation_id: str,
    marketplace_id: str,
) -> ImportDetailResponse:
    try:
        return _confirm_import_once(
            session,
            import_id,
            command,
            settings,
            organisation_id=organisation_id,
            marketplace_id=marketplace_id,
        )
    except OperationalError as exc:
        session.rollback()
        if _is_retryable_operational_error(exc):
            logger.warning(
                "Import confirmation deferred by a transient database failure",
                extra={"import_id": import_id},
            )
            raise ApplicationError(
                "import_confirmation_retryable",
                "The import database is temporarily unavailable; retry confirmation",
                status_code=503,
                details={"import_id": import_id, "retryable": True},
            ) from exc
        logger.error(
            "Import confirmation stopped by a non-retryable database failure",
            extra={
                "import_id": import_id,
                "failure_class": type(exc.orig).__name__,
                "retryable": False,
            },
        )
        raise ApplicationError(
            "import_confirmation_database_error",
            "The import could not be confirmed because of a database failure",
            status_code=500,
            details={"import_id": import_id, "retryable": False},
        ) from exc


def _is_retryable_operational_error(exc: OperationalError) -> bool:
    if exc.connection_invalidated:
        return True

    original = exc.orig
    if isinstance(original, sqlite3.OperationalError):
        sqlite_code = getattr(original, "sqlite_errorcode", None)
        if isinstance(sqlite_code, int) and (sqlite_code & 0xFF) in {
            sqlite3.SQLITE_BUSY,
            sqlite3.SQLITE_LOCKED,
        }:
            return True
        normalized_message = str(original).strip().lower()
        return normalized_message in {
            "database is locked",
            "database is busy",
            "database table is locked",
            "database schema is locked",
        }

    sqlstate = getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)
    return isinstance(sqlstate, str) and (
        sqlstate.startswith("08") or sqlstate in _POSTGRES_RETRYABLE_SQLSTATES
    )


def _confirm_import_once(
    session: Session,
    import_id: str,
    command: ConfirmImportCommand,
    settings: Settings,
    *,
    organisation_id: str,
    marketplace_id: str,
) -> ImportDetailResponse:
    batch = _get_batch(
        session,
        import_id,
        organisation_id=organisation_id,
        marketplace_id=marketplace_id,
        for_update=True,
    )
    registry = AliasRegistry.default()
    if batch.status is ImportStatus.completed:
        if batch.observed_on != command.observed_on:
            raise ConflictError(
                "import_observed_on_conflict",
                "A completed import cannot be reassigned to a different observation date",
                details={
                    "confirmed_observed_on": (
                        batch.observed_on.isoformat() if batch.observed_on is not None else None
                    )
                },
            )
        _cleanup_staged_upload(session, batch, settings, lifecycle="completed")
        return _detail_response(batch, registry=registry)
    if batch.status is not ImportStatus.pending:
        if batch.status is ImportStatus.failed:
            _cleanup_staged_upload(session, batch, settings, lifecycle="failed")
        raise ConflictError("import_not_pending", "Only a pending import can be confirmed")
    if batch.alias_registry_version != registry.version:
        raise ConflictError(
            "alias_registry_version_mismatch",
            "The import was created with a different alias registry version",
        )
    if command.observed_on > datetime.now(UTC).date():
        raise ApplicationError(
            "observed_on_in_future",
            "The dataset observation date cannot be in the future",
            status_code=422,
        )

    try:
        inspection = _load_inspection(batch, registry, settings)
        path = _batch_path(batch, settings)
    except OperationalError:
        raise
    except Exception as exc:
        failure_code, failure_message = _failure_record(exc)
        _record_import_failure(
            session,
            batch,
            failure_code=failure_code,
            failure_message=failure_message,
        )
        _cleanup_staged_upload(session, batch, settings, lifecycle="failed")
        raise _public_import_failure(exc, import_id) from exc
    if inspection.mapping.requires_confirmation:
        raise ConflictError(
            "mapping_confirmation_required",
            "Resolve every ambiguous source column before confirming the import",
        )
    if inspection.mapping.missing_required_fields:
        raise ConflictError(
            "required_mapping_missing",
            "The workbook is missing required canonical fields",
            details={"fields": list(inspection.mapping.missing_required_fields)},
        )
    _apply_dataset_metadata(batch, inspection)
    _assign_dataset_observation(session, batch, observed_on=command.observed_on)

    try:
        rows = tuple(
            iter_workbook_rows(
                path,
                inspection,
                registry,
                limits=workbook_limits(settings),
            )
        )
        _persist_rows(session, batch, rows, inspection)
        batch.confirmed_at = datetime.now(UTC)
        batch.completed_at = batch.confirmed_at
        batch.status = ImportStatus.completed
        batch.failure_code = None
        batch.failure_message = None
        session.add(
            _audit_event(
                organisation_id=batch.organisation_id,
                event_type="import.completed",
                entity_type="import_batch",
                entity_id=batch.id,
                payload={
                    "created": batch.created_rows,
                    "matched": batch.matched_rows,
                    "skipped": batch.skipped_rows,
                    "failed": batch.failed_rows,
                    "observed_on": batch.observed_on.isoformat()
                    if batch.observed_on is not None
                    else None,
                    "period_month": batch.period_month.isoformat()
                    if batch.period_month is not None
                    else None,
                    "dataset_revision": batch.dataset_revision,
                    "dataset_schema_id": batch.dataset_schema_id,
                    "dataset_schema_version": batch.dataset_schema_version,
                },
            )
        )
        session.commit()
    except OperationalError:
        raise
    except IntegrityError as exc:
        session.rollback()
        if _is_dataset_revision_conflict(exc):
            logger.warning(
                "Import dataset revision assignment conflicted and can be retried",
                extra={"import_id": import_id},
            )
            raise ApplicationError(
                "import_dataset_revision_retryable",
                "Another dataset revision completed concurrently; retry confirmation",
                status_code=503,
                details={"import_id": import_id, "retryable": True},
            ) from exc
        logger.error(
            "Import processing failed",
            extra={"import_id": import_id, "failure_class": type(exc).__name__},
        )
        failed = _get_batch(
            session,
            import_id,
            organisation_id=organisation_id,
            marketplace_id=marketplace_id,
            for_update=True,
        )
        failure_code, failure_message = _failure_record(exc)
        _record_import_failure(
            session,
            failed,
            failure_code=failure_code,
            failure_message=failure_message,
        )
        _cleanup_staged_upload(session, failed, settings, lifecycle="failed")
        raise _public_import_failure(exc, import_id) from exc
    except Exception as exc:
        session.rollback()
        logger.error(
            "Import processing failed",
            extra={"import_id": import_id, "failure_class": type(exc).__name__},
        )
        failed = _get_batch(
            session,
            import_id,
            organisation_id=organisation_id,
            marketplace_id=marketplace_id,
            for_update=True,
        )
        if failed is not None and failed.status is ImportStatus.pending:
            failure_code, failure_message = _failure_record(exc)
            _record_import_failure(
                session,
                failed,
                failure_code=failure_code,
                failure_message=failure_message,
            )
        _cleanup_staged_upload(session, failed, settings, lifecycle="failed")
        raise _public_import_failure(exc, import_id) from exc

    _cleanup_staged_upload(session, batch, settings, lifecycle="completed")
    return get_import(
        session,
        import_id,
        settings,
        organisation_id=organisation_id,
        marketplace_id=marketplace_id,
    )


def _cleanup_staged_upload(
    session: Session,
    batch: ImportBatch,
    settings: Settings,
    *,
    lifecycle: str,
) -> None:
    path = _candidate_batch_path(batch, settings)
    if path is None:
        return
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        logger.error(
            "Import staged-file cleanup failed",
            extra={
                "import_id": batch.id,
                "failure_class": type(exc).__name__,
                "lifecycle": lifecycle,
            },
        )
        return

    batch.storage_key = None
    try:
        session.commit()
    except (IntegrityError, OperationalError) as exc:
        session.rollback()
        logger.error(
            "Import cleanup reference could not be cleared",
            extra={
                "import_id": batch.id,
                "failure_class": type(exc).__name__,
                "lifecycle": lifecycle,
            },
        )


def _persist_rows(
    session: Session,
    batch: ImportBatch,
    rows: tuple[WorkbookRow, ...],
    inspection: WorkbookInspection,
) -> None:
    if (
        batch.observed_on is None
        or batch.observed_on_source is None
        or batch.period_month is None
        or batch.dataset_revision is None
    ):
        raise RuntimeError("Import observation metadata must be assigned before row persistence")
    marketplace = _get_marketplace(
        session,
        organisation_id=batch.organisation_id,
        marketplace_id=batch.marketplace_id,
    )
    batch.total_rows = len(rows)
    valid_rows: list[_ValidRow] = []
    seen_asins: set[str] = set()
    row_error_count = 0
    for row in rows:
        for issue in row.issues:
            if issue.canonical_field == "asin" and issue.code == "missing_required_value":
                continue
            session.add(
                ImportRowError(
                    import_batch=batch,
                    row_number=row.row_number,
                    field_name=issue.canonical_field,
                    error_code=issue.code,
                    severity=RowErrorSeverity.warning,
                    message=issue.message,
                )
            )
            row_error_count += 1

        asin = _normalize_asin(row.canonical_values.get("asin"))
        if asin is None:
            batch.failed_rows += 1
            session.add(
                ImportRowError(
                    import_batch=batch,
                    row_number=row.row_number,
                    field_name="asin",
                    error_code="invalid_asin",
                    severity=RowErrorSeverity.error,
                    message="ASIN must contain exactly 10 letters or digits",
                )
            )
            row_error_count += 1
            continue
        if asin in seen_asins:
            batch.skipped_rows += 1
            session.add(
                ImportRowError(
                    import_batch=batch,
                    row_number=row.row_number,
                    field_name="asin",
                    error_code="duplicate_asin_in_workbook",
                    severity=RowErrorSeverity.error,
                    message="A later row repeats an ASIN already processed in this workbook",
                )
            )
            row_error_count += 1
            continue
        seen_asins.add(asin)
        valid_rows.append(_ValidRow(row=row, asin=asin))

    existing_products = _load_products(
        session,
        organisation_id=batch.organisation_id,
        marketplace_id=batch.marketplace_id,
        asins=seen_asins,
    )
    products = dict(existing_products)
    new_products: list[Product] = []
    for item in valid_rows:
        if item.asin in products:
            continue
        product = Product(
            organisation_id=batch.organisation_id,
            marketplace_id=batch.marketplace_id,
            asin=item.asin,
        )
        products[item.asin] = product
        new_products.append(product)
        session.add(product)
    session.flush()

    history_months = _history_months(
        session,
        {product.id for product in products.values()},
        through_period=batch.period_month,
    )
    scoring_checksum = _configuration_checksum(
        Path(__file__).parents[1] / "scoring" / "configs" / "v1.json"
    )
    strategy_checksum = _configuration_checksum(
        Path(__file__).parents[1] / "strategies" / "policies" / "v1.json"
    )
    classifier = StrategyClassifier()
    imported_at = datetime.now(UTC)
    dataset_schema = ProductFinderDatasetSchema.default()
    dataset_classifications = {
        entry.column.ordinal: dataset_schema.classify_column(
            normalized_header=entry.column.normalized_header,
        )
        for entry in inspection.mapping.columns
        if entry.column is not None
    }

    new_product_ids = {product.id for product in new_products}
    for item in valid_rows:
        product = products[item.asin]
        values = item.row.canonical_values
        snapshot = ProductSnapshot(
            id=str(uuid.uuid4()),
            product=product,
            import_batch=batch,
            snapshot_kind=SnapshotKind.keepa,
            snapshot_at=imported_at,
            observed_on=batch.observed_on,
            observed_on_source=batch.observed_on_source,
            source_row_number=item.row.row_number,
            title=_text(values.get("title")),
            brand=_text(values.get("brand")),
            category=_text(values.get("category")),
            subcategory=_text(values.get("subcategory")),
            buy_box_price=_decimal(values.get("buy_box_price")),
            buy_box_price_90d=_decimal(values.get("buy_box_price_90d")),
            currency_code=marketplace.default_currency_code,
            sales_rank=_integer(values.get("sales_rank_current")),
            sales_rank_90d=_integer(values.get("sales_rank_90d")),
            sales_rank_drops_90d=_integer(values.get("sales_rank_drops_90d")),
            review_rating=_bounded_decimal(values.get("rating"), Decimal("0"), Decimal("5")),
            review_count=_integer(values.get("review_count")),
            new_offer_count=_integer(values.get("new_offer_count")),
            total_offer_count=_integer(values.get("total_offer_count")),
            buy_box_winner_count_90d=_integer(values.get("buy_box_winner_count_90d")),
            buy_box_oos_percentage_90d=_bounded_decimal(
                values.get("buy_box_oos_percentage_90d"), Decimal("0"), Decimal("100")
            ),
            monthly_sold=_integer(values.get("monthly_sold")),
            is_fba=_boolean(values.get("buy_box_is_fba")),
            image_url=_text(values.get("image_url")),
            amazon_url=_text(values.get("amazon_url")),
            market_metrics=dict(values),
            source_payload=[
                {
                    "ordinal": source_cell.ordinal,
                    "header": source_cell.source_header,
                    "value": source_cell.value,
                }
                for source_cell in item.row.source_values
            ],
        )
        session.add(snapshot)
        malformed_ordinals = {
            issue.column_ordinal for issue in item.row.issues if issue.column_ordinal is not None
        }
        for source_cell in item.row.source_values:
            if (
                source_cell.ordinal not in malformed_ordinals
                and dataset_classifications[source_cell.ordinal]
                is not DatasetColumnClassification.unrecognized
            ):
                continue
            snapshot.raw_attributes.append(
                RawAttribute(
                    source_column_ordinal=source_cell.ordinal,
                    source_header=source_cell.source_header,
                    value=source_cell.value,
                )
            )

        scorecard = score_market_metrics(_market_metrics(values))
        _add_scores(snapshot, scorecard, scoring_checksum)
        decision = classifier.classify(
            StrategyContext(
                scores=MarketScores(
                    demand=scorecard.demand.value,
                    competition=scorecard.competition.value,
                    price_stability=scorecard.price_stability.value,
                    data_confidence=scorecard.data_confidence.value,
                    overall_opportunity=scorecard.overall_opportunity.value,
                ),
                history_months=history_months.get(product.id, 1),
            )
        )
        _add_recommendation(
            snapshot,
            decision,
            confidence_score=scorecard.data_confidence.value,
            configuration_checksum=strategy_checksum,
        )
        if _should_replace_latest_snapshot(product.latest_snapshot, snapshot):
            _update_product_summary(product, values)
            product.latest_snapshot = snapshot
        if product.id in new_product_ids:
            batch.created_rows += 1
        else:
            batch.matched_rows += 1

        chunk_position = batch.created_rows + batch.matched_rows
        if chunk_position % _SNAPSHOT_FLUSH_CHUNK_SIZE == 0:
            _flush_snapshot_chunk(session, _SNAPSHOT_FLUSH_CHUNK_SIZE)

    final_chunk_size = len(valid_rows) % _SNAPSHOT_FLUSH_CHUNK_SIZE
    if final_chunk_size:
        _flush_snapshot_chunk(session, final_chunk_size)

    expected = batch.created_rows + batch.matched_rows + batch.skipped_rows + batch.failed_rows
    if expected != batch.total_rows:
        raise RuntimeError("Import row accounting invariant failed")
    logger.info(
        "Import rows prepared",
        extra={"import_id": batch.id, "rows": batch.total_rows, "row_errors": row_error_count},
    )


def _flush_snapshot_chunk(session: Session, row_count: int) -> None:
    if row_count < 1 or row_count > _SNAPSHOT_FLUSH_CHUNK_SIZE:
        raise RuntimeError("Import snapshot flush chunk invariant failed")
    session.flush()


def _add_scores(
    snapshot: ProductSnapshot,
    scorecard: ScoreCard,
    configuration_checksum: str,
) -> None:
    for score in scorecard.scores:
        payload = score.to_dict()
        snapshot.score_results.append(
            ScoreResultRecord(
                score_name=score.name.value,
                formula_version=score.formula_version,
                configuration_checksum=configuration_checksum,
                score_value=score.value,
                inputs={
                    "inputs": payload["inputs"],
                    "components": payload["components"],
                    "reasons": payload["reasons"],
                },
                reason_codes=list(score.reason_codes),
            )
        )


def _add_recommendation(
    snapshot: ProductSnapshot,
    decision: StrategyDecision,
    *,
    confidence_score: int,
    configuration_checksum: str,
) -> None:
    evidence = [
        {
            "reason_code": item.reason_code.value,
            "polarity": item.polarity.value,
            "source": item.source.value,
            "signal": item.signal,
            "observed_value": _json_evidence_value(item.observed_value),
            "comparison": item.comparison.value,
            "threshold_value": _json_evidence_value(item.threshold_value),
            "threshold_upper_value": _json_evidence_value(item.threshold_upper_value),
            "statement": item.statement,
        }
        for item in decision.evidence
    ]
    snapshot.recommendations.append(
        StrategyRecommendation(
            strategy=decision.strategy.value,
            rules_version=decision.rules_version,
            configuration_checksum=configuration_checksum,
            confidence_score=confidence_score,
            evidence=evidence,
        )
    )


def _market_metrics(values: dict[str, Any]) -> MarketMetrics:
    return MarketMetrics(
        sales_rank_current=values.get("sales_rank_current"),
        sales_rank_90_day_average=values.get("sales_rank_90d"),
        rank_drops_90_days=values.get("sales_rank_drops_90d"),
        monthly_sold=values.get("monthly_sold"),
        offer_count=_first_available(
            values.get("total_offer_count"), values.get("new_offer_count")
        ),
        review_count=values.get("review_count"),
        buy_box_winner_count_90_days=values.get("buy_box_winner_count_90d"),
        buy_box_price=values.get("buy_box_price"),
        buy_box_price_90_day_average=values.get("buy_box_price_90d"),
        buy_box_oos_percent=values.get("buy_box_oos_percentage_90d"),
    )


def _new_batch(
    staged: StagedUpload,
    *,
    organisation_id: str,
    marketplace_id: str,
) -> ImportBatch:
    return ImportBatch(
        id=str(uuid.uuid4()),
        organisation_id=organisation_id,
        marketplace_id=marketplace_id,
        original_filename=staged.original_filename,
        checksum=staged.checksum_sha256,
        checksum_algorithm="sha256",
        file_size_bytes=staged.size_bytes,
        content_type=staged.content_type,
        storage_key=staged.storage_key,
        status=ImportStatus.pending,
    )


def _apply_mapping_report(batch: ImportBatch, inspection: WorkbookInspection) -> None:
    existing = {column.source_column_ordinal: column for column in batch.columns}
    samples_by_ordinal: dict[int, list[Any]] = {column.ordinal: [] for column in inspection.columns}
    for preview_row in inspection.preview_rows:
        for source_cell in preview_row.source_values:
            samples_by_ordinal[source_cell.ordinal].append(source_cell.value)

    updated: list[ImportColumn] = []
    for entry in inspection.mapping.columns:
        if entry.column is None:
            continue
        column = existing.get(entry.column.ordinal)
        if column is None:
            column = ImportColumn(
                import_batch=batch,
                source_column_ordinal=entry.column.ordinal,
                source_header=entry.column.source_header,
                normalized_header=entry.column.normalized_header,
            )
        column.canonical_field = entry.canonical_field
        column.mapping_status = _mapping_status(entry.classification)
        column.mapping_source = (
            MappingSource.user
            if entry.explicitly_resolved
            else MappingSource.registry
            if entry.is_resolved
            else MappingSource.unmapped
        )
        column.mapping_candidates = list(entry.candidates)
        column.sample_values = samples_by_ordinal.get(entry.column.ordinal, [])
        column.is_required = entry.is_required
        column.is_mapped = entry.is_resolved
        updated.append(column)
    batch.columns[:] = updated
    batch.workbook_sheet_name = inspection.selected_sheet
    batch.header_row_number = inspection.header_row
    batch.alias_registry_version = inspection.mapping.registry_version


def _apply_dataset_metadata(
    batch: ImportBatch,
    inspection: WorkbookInspection,
) -> DatasetSchemaInspection:
    dataset = ProductFinderDatasetSchema.default().inspect(inspection.columns)
    suggestion = suggest_observed_on(
        sheet_name=inspection.selected_sheet,
        original_filename=batch.original_filename,
    )
    batch.dataset_schema_id = dataset.schema_id or "keepa.unregistered"
    batch.dataset_schema_version = dataset.schema_version or (
        f"headers-{dataset.source_header_checksum[:12]}"
    )
    batch.dataset_schema_match = dataset.match.value
    batch.dataset_schema_checksum = ProductFinderDatasetSchema.default().configuration_checksum
    batch.source_header_checksum = dataset.source_header_checksum
    batch.source_column_count = dataset.source_column_count
    batch.observed_on_suggestion = suggestion.observed_on if suggestion is not None else None
    batch.observation_suggestion_source = (
        suggestion.source.value if suggestion is not None else None
    )
    batch.observation_date_candidates = [
        {"date": candidate.observed_on.isoformat(), "source": candidate.source.value}
        for candidate in observation_date_candidates(
            sheet_name=inspection.selected_sheet,
            original_filename=batch.original_filename,
        )
    ]
    return dataset


def _assign_dataset_observation(
    session: Session,
    batch: ImportBatch,
    *,
    observed_on: date,
) -> None:
    if batch.dataset_schema_id is None:
        raise RuntimeError("Dataset schema identity must be assigned before observation metadata")
    period_month = date(observed_on.year, observed_on.month, 1)
    revisions = session.scalars(
        select(ImportBatch.dataset_revision)
        .where(
            ImportBatch.organisation_id == batch.organisation_id,
            ImportBatch.marketplace_id == batch.marketplace_id,
            ImportBatch.dataset_schema_id == batch.dataset_schema_id,
            ImportBatch.period_month == period_month,
            ImportBatch.id != batch.id,
        )
        .order_by(ImportBatch.dataset_revision.desc())
        .with_for_update()
    ).all()
    batch.observed_on = observed_on
    batch.observed_on_source = "user_confirmed"
    batch.period_month = period_month
    batch.dataset_revision = (
        max((revision for revision in revisions if revision is not None), default=0) + 1
    )


def _is_dataset_revision_conflict(exc: IntegrityError) -> bool:
    constraint_name = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
    if constraint_name == "uq_import_dataset_period_revision":
        return True
    normalized = str(exc.orig).casefold()
    return (
        "unique constraint failed" in normalized
        and "import_batches.dataset_revision" in normalized
        and "import_batches.period_month" in normalized
    )


def _mapping_status(classification: MappingClassification) -> MappingStatus:
    if classification in (MappingClassification.required, MappingClassification.optional):
        return MappingStatus.mapped
    if classification is MappingClassification.ambiguous:
        return MappingStatus.ambiguous
    return MappingStatus.unknown


def _detail_response(
    batch: ImportBatch,
    *,
    registry: AliasRegistry,
    inspection: WorkbookInspection | None = None,
    duplicate: bool = False,
) -> ImportDetailResponse:
    mapping = (
        _mapping_response_from_report(inspection.mapping, inspection)
        if inspection is not None
        else _mapping_response_from_records(batch, registry)
    )
    return ImportDetailResponse(
        id=batch.id,
        organisation_id=batch.organisation_id,
        marketplace_id=batch.marketplace_id,
        original_filename=batch.original_filename,
        checksum=batch.checksum,
        status=batch.status.value,
        uploaded_at=batch.uploaded_at,
        confirmed_at=batch.confirmed_at,
        completed_at=batch.completed_at,
        workbook=ImportWorkbook(
            sheet_name=batch.workbook_sheet_name,
            header_row_number=batch.header_row_number,
            alias_registry_version=batch.alias_registry_version,
        ),
        dataset=_dataset_response(batch, inspection),
        mapping=mapping,
        preview_rows=_preview_response(inspection) if inspection is not None else [],
        summary=_summary(batch) if batch.status is ImportStatus.completed else None,
        failure=(
            ImportFailure(code=batch.failure_code, message=batch.failure_message)
            if batch.failure_code and batch.failure_message
            else None
        ),
        duplicate=duplicate,
    )


def _mapping_response_from_report(
    report: MappingReport,
    inspection: WorkbookInspection,
) -> MappingResponse:
    dataset_schema = ProductFinderDatasetSchema.default()
    samples_by_ordinal: dict[int, list[Any]] = {column.ordinal: [] for column in inspection.columns}
    for row in inspection.preview_rows:
        for cell in row.source_values:
            samples_by_ordinal[cell.ordinal].append(cell.value)
    missing_required = list(report.missing_required_fields)
    missing_optional = [
        entry.canonical_field
        for entry in report.missing
        if not entry.is_required and entry.canonical_field is not None
    ]
    return MappingResponse(
        registry_id=report.registry_id,
        registry_version=report.registry_version,
        columns=[
            MappingColumnResponse(
                ordinal=entry.column.ordinal,
                header=entry.column.source_header,
                normalized_header=entry.column.normalized_header,
                canonical_field=entry.canonical_field,
                classification=entry.classification.value,
                dataset_classification=dataset_schema.classify_column(
                    normalized_header=entry.column.normalized_header,
                ).value,
                candidates=list(entry.candidates),
                required_candidates=list(entry.required_candidates),
                is_required=entry.is_required,
                samples=samples_by_ordinal.get(entry.column.ordinal, []),
            )
            for entry in report.columns
            if entry.column is not None
        ],
        missing_required=missing_required,
        missing_optional=missing_optional,
        requires_confirmation=report.requires_confirmation or bool(missing_required),
    )


def _mapping_response_from_records(
    batch: ImportBatch,
    registry: AliasRegistry,
) -> MappingResponse:
    dataset_schema = ProductFinderDatasetSchema.default()
    represented = {
        column.canonical_field for column in batch.columns if column.canonical_field is not None
    }
    candidate_fields = {
        candidate for column in batch.columns for candidate in column.mapping_candidates
    }
    missing = [
        field
        for field in registry.fields
        if field.name not in represented and field.name not in candidate_fields
    ]
    missing_required = [field.name for field in missing if field.required]
    missing_optional = [field.name for field in missing if not field.required]
    columns = []
    for column in sorted(batch.columns, key=lambda item: item.source_column_ordinal):
        classification = (
            "required"
            if column.is_mapped and column.is_required
            else "optional"
            if column.is_mapped
            else column.mapping_status.value
        )
        required_candidates = [
            name
            for name in column.mapping_candidates
            if name in registry.fields_by_name and registry.fields_by_name[name].required
        ]
        columns.append(
            MappingColumnResponse(
                ordinal=column.source_column_ordinal,
                header=column.source_header,
                normalized_header=column.normalized_header,
                canonical_field=column.canonical_field,
                classification=classification,
                dataset_classification=dataset_schema.classify_column(
                    normalized_header=column.normalized_header,
                ).value,
                candidates=list(column.mapping_candidates),
                required_candidates=required_candidates,
                is_required=column.is_required,
                samples=list(column.sample_values),
            )
        )
    return MappingResponse(
        registry_id=registry.registry_id,
        registry_version=batch.alias_registry_version or registry.version,
        columns=columns,
        missing_required=missing_required,
        missing_optional=missing_optional,
        requires_confirmation=any(
            column.mapping_status is MappingStatus.ambiguous for column in batch.columns
        )
        or bool(missing_required),
    )


def _dataset_response(
    batch: ImportBatch,
    inspection: WorkbookInspection | None,
) -> ImportDatasetResponse:
    schema = ProductFinderDatasetSchema.default()
    columns = (
        inspection.columns
        if inspection is not None
        else tuple(
            SourceColumn(
                ordinal=column.source_column_ordinal,
                source_header=column.source_header,
                normalized_header=column.normalized_header,
            )
            for column in sorted(batch.columns, key=lambda item: item.source_column_ordinal)
        )
    )
    inspected = schema.inspect(columns)
    suggestion = suggest_observed_on(
        sheet_name=(
            inspection.selected_sheet if inspection is not None else batch.workbook_sheet_name
        ),
        original_filename=batch.original_filename,
    )
    candidates = observation_date_candidates(
        sheet_name=(
            inspection.selected_sheet if inspection is not None else batch.workbook_sheet_name
        ),
        original_filename=batch.original_filename,
    )
    return ImportDatasetResponse(
        schema_id=batch.dataset_schema_id or inspected.schema_id or "keepa.unregistered",
        schema_version=batch.dataset_schema_version
        or inspected.schema_version
        or f"headers-{inspected.source_header_checksum[:12]}",
        schema_match=batch.dataset_schema_match or inspected.match.value,
        dataset_schema_checksum=(batch.dataset_schema_checksum or schema.configuration_checksum),
        source_column_count=batch.source_column_count or inspected.source_column_count,
        registered_column_count=inspected.registered_column_count,
        matched_column_count=inspected.matched_column_count,
        new_headers=list(inspected.new_headers),
        missing_headers=list(inspected.missing_headers),
        source_header_checksum=batch.source_header_checksum or inspected.source_header_checksum,
        observed_on=batch.observed_on,
        period_month=batch.period_month,
        revision=batch.dataset_revision,
        date_status=(
            "confirmed"
            if batch.observed_on is not None
            else "legacy_unconfirmed"
            if batch.status is ImportStatus.completed
            else "pending_confirmation"
        ),
        observation_date_candidates=(
            list(batch.observation_date_candidates)
            if batch.observation_date_candidates
            else [
                {"date": candidate.observed_on.isoformat(), "source": candidate.source.value}
                for candidate in candidates
            ]
        ),
        observed_on_suggestion=batch.observed_on_suggestion
        or (suggestion.observed_on if suggestion is not None else None),
        suggestion_source=batch.observation_suggestion_source
        or (suggestion.source.value if suggestion is not None else None),
        observed_on_source=batch.observed_on_source,
    )


def _preview_response(inspection: WorkbookInspection) -> list[PreviewRowResponse]:
    mapping_by_ordinal = {
        entry.column.ordinal: entry
        for entry in inspection.mapping.columns
        if entry.column is not None
    }
    result: list[PreviewRowResponse] = []
    for row in inspection.preview_rows:
        values: dict[str, Any] = {}
        for cell in row.source_values:
            entry = mapping_by_ordinal[cell.ordinal]
            key = entry.canonical_field or f"{cell.ordinal}:{cell.source_header or 'unnamed'}"
            values[key] = cell.value
        result.append(
            PreviewRowResponse(
                row_number=row.row_number,
                values=values,
                issues=[
                    {
                        "code": issue.code,
                        "message": issue.message,
                        "ordinal": issue.column_ordinal,
                        "canonical_field": issue.canonical_field,
                    }
                    for issue in row.issues
                ],
            )
        )
    return result


def _summary(batch: ImportBatch) -> ImportSummary:
    return ImportSummary(
        total=batch.total_rows,
        created=batch.created_rows,
        matched=batch.matched_rows,
        skipped=batch.skipped_rows,
        failed=batch.failed_rows,
        row_error_count=len(batch.row_errors),
    )


def _get_marketplace(
    session: Session,
    *,
    organisation_id: str,
    marketplace_id: str,
) -> Marketplace:
    marketplace = session.scalar(
        select(Marketplace).where(
            Marketplace.id == marketplace_id,
            Marketplace.organisation_id == organisation_id,
        )
    )
    if marketplace is None:
        raise NotFoundError("Marketplace")
    return marketplace


def _get_batch(
    session: Session,
    import_id: str,
    *,
    organisation_id: str,
    marketplace_id: str,
    for_update: bool = False,
) -> ImportBatch:
    statement = (
        select(ImportBatch)
        .options(selectinload(ImportBatch.columns), selectinload(ImportBatch.row_errors))
        .where(
            ImportBatch.id == import_id,
            ImportBatch.organisation_id == organisation_id,
            ImportBatch.marketplace_id == marketplace_id,
        )
    )
    if for_update:
        statement = statement.with_for_update()
    batch = session.scalar(statement)
    if batch is None:
        raise NotFoundError("Import")
    return batch


def _try_load_inspection(
    batch: ImportBatch,
    registry: AliasRegistry,
    settings: Settings,
) -> WorkbookInspection | None:
    if batch.status is not ImportStatus.pending or batch.storage_key is None:
        return None
    try:
        return _load_inspection(batch, registry, settings)
    except (ApplicationError, WorkbookInspectionError, OSError):
        logger.warning("Unable to rebuild import preview", extra={"import_id": batch.id})
        return None


def _failure_record(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, WorkbookInspectionError):
        return exc.code.value, exc.user_message
    if isinstance(exc, ApplicationError):
        return exc.code, exc.message
    return "processing_failed", "The workbook could not be processed safely"


def _public_import_failure(exc: Exception, import_id: str) -> ApplicationError:
    if isinstance(exc, WorkbookInspectionError):
        return ApplicationError(
            exc.code.value,
            exc.user_message,
            status_code=422,
            details={"import_id": import_id, **exc.details},
        )
    if isinstance(exc, ApplicationError):
        return ApplicationError(
            exc.code,
            exc.message,
            status_code=exc.status_code,
            details={"import_id": import_id, **exc.details},
        )
    return ApplicationError(
        "import_processing_failed",
        "The workbook could not be processed safely",
        status_code=422,
        details={"import_id": import_id},
    )


def _record_import_failure(
    session: Session,
    batch: ImportBatch,
    *,
    failure_code: str,
    failure_message: str,
) -> None:
    batch.status = ImportStatus.failed
    batch.failure_code = failure_code
    batch.failure_message = failure_message
    session.add(
        _audit_event(
            organisation_id=batch.organisation_id,
            event_type="import.processing_failed",
            entity_type="import_batch",
            entity_id=batch.id,
            payload={"failure_code": failure_code},
        )
    )
    session.commit()


def _load_inspection(
    batch: ImportBatch,
    registry: AliasRegistry,
    settings: Settings,
) -> WorkbookInspection:
    path = _batch_path(batch, settings)
    explicit_mappings = {
        column.source_column_ordinal: column.canonical_field
        for column in batch.columns
        if column.mapping_source is MappingSource.user
    }
    inspection = inspect_workbook(
        path,
        registry,
        explicit_mappings=explicit_mappings,
        limits=workbook_limits(settings),
    )
    if inspection.checksum_sha256 != batch.checksum:
        raise ConflictError("workbook_changed", "The staged workbook no longer matches this import")
    return inspection


def _candidate_batch_path(batch: ImportBatch, settings: Settings) -> Path | None:
    if batch.storage_key is None:
        return None
    upload_directory = settings.upload_directory.resolve()
    path = (upload_directory / batch.storage_key).resolve()
    return path if path.parent == upload_directory else None


def _batch_path(batch: ImportBatch, settings: Settings) -> Path:
    path = _candidate_batch_path(batch, settings)
    if path is None:
        raise ConflictError("import_file_unavailable", "The staged workbook key is invalid")
    if not path.is_file():
        raise ConflictError("import_file_unavailable", "The staged workbook is no longer available")
    return path


def _load_products(
    session: Session,
    *,
    organisation_id: str,
    marketplace_id: str,
    asins: set[str],
) -> dict[str, Product]:
    products: dict[str, Product] = {}
    ordered = sorted(asins)
    for start in range(0, len(ordered), _QUERY_CHUNK_SIZE):
        chunk = ordered[start : start + _QUERY_CHUNK_SIZE]
        for product in session.scalars(
            select(Product)
            .options(
                selectinload(Product.latest_snapshot).selectinload(ProductSnapshot.import_batch)
            )
            .where(
                Product.organisation_id == organisation_id,
                Product.marketplace_id == marketplace_id,
                Product.asin.in_(chunk),
            )
        ):
            products[product.asin] = product
    return products


def _history_months(
    session: Session,
    product_ids: set[str],
    *,
    through_period: date,
) -> dict[str, int]:
    periods_by_product: dict[str, set[date]] = {product_id: set() for product_id in product_ids}
    ordered = sorted(product_ids)
    for start in range(0, len(ordered), _QUERY_CHUNK_SIZE):
        chunk = ordered[start : start + _QUERY_CHUNK_SIZE]
        rows = session.execute(
            select(ProductSnapshot.product_id, ImportBatch.period_month)
            .join(ImportBatch, ImportBatch.id == ProductSnapshot.import_batch_id)
            .where(
                ProductSnapshot.product_id.in_(chunk),
                ImportBatch.period_month.is_not(None),
                ImportBatch.period_month <= through_period,
            )
            .distinct()
        )
        for product_id, period_month in rows:
            if period_month is not None:
                periods_by_product[product_id].add(period_month)
    return {
        product_id: len(periods | {through_period})
        for product_id, periods in periods_by_product.items()
    }


def _update_product_summary(product: Product, values: dict[str, Any]) -> None:
    for attribute, canonical_field in (
        ("title", "title"),
        ("brand", "brand"),
        ("category", "category"),
        ("subcategory", "subcategory"),
        ("image_url", "image_url"),
        ("amazon_url", "amazon_url"),
    ):
        value = _text(values.get(canonical_field))
        if value is not None:
            setattr(product, attribute, value)


def _should_replace_latest_snapshot(
    latest: ProductSnapshot | None,
    candidate: ProductSnapshot,
) -> bool:
    if latest is None:
        return True
    if candidate.observed_on is None:
        return False
    if latest.observed_on is None:
        return True
    if candidate.observed_on != latest.observed_on:
        return candidate.observed_on > latest.observed_on
    candidate_batch = candidate.import_batch
    latest_batch = latest.import_batch
    candidate_revision = candidate_batch.dataset_revision if candidate_batch is not None else None
    latest_revision = latest_batch.dataset_revision if latest_batch is not None else None
    if candidate_revision is None:
        return False
    if latest_revision is None:
        return True
    return candidate_revision > latest_revision


def _normalize_asin(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().upper()
    return normalized if _ASIN_PATTERN.fullmatch(normalized) else None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return result or None


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        return None
    return result if result.is_finite() else None


def _bounded_decimal(value: Any, minimum: Decimal, maximum: Decimal) -> Decimal | None:
    result = _decimal(value)
    if result is None or result < minimum or result > maximum:
        return None
    return result


def _integer(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return int(value)


def _boolean(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _json_evidence_value(value: Any) -> Any:
    return str(value) if isinstance(value, Decimal) else value


def _first_available(primary: Any, fallback: Any) -> Any:
    return fallback if primary is None else primary


def _configuration_checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _audit_event(
    *,
    organisation_id: str,
    event_type: str,
    entity_type: str,
    entity_id: str,
    payload: dict[str, Any],
) -> AuditEvent:
    return AuditEvent(
        organisation_id=organisation_id,
        actor_type="system",
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        event_payload=payload,
    )


# Deliberately absent: implicit tenant state. Every public import operation receives
# explicit organisation and marketplace scope, including opaque-ID detail and mutation reads.

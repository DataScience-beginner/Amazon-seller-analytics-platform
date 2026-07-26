from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from app.core.config import Settings
from app.core.errors import ApplicationError

_XLSX_CONTENT_TYPES = frozenset(
    {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/octet-stream",
        "application/zip",
    }
)


@dataclass(frozen=True, slots=True)
class StagedUpload:
    original_filename: str
    content_type: str | None
    storage_key: str
    path: Path
    size_bytes: int
    checksum_sha256: str


def stage_xlsx_upload(
    upload: UploadFile, settings: Settings, *, purpose: str = "Keepa export"
) -> StagedUpload:
    supplied_filename = (upload.filename or "").replace("\\", "/")
    original_filename = Path(supplied_filename).name.strip()
    if not original_filename or not original_filename.casefold().endswith(".xlsx"):
        raise ApplicationError(
            "unsupported_file_type",
            f"Upload a {purpose} in .xlsx format",
            status_code=415,
        )
    if len(original_filename) > 512:
        raise ApplicationError(
            "filename_too_long",
            "The workbook filename exceeds the 512-character limit",
            status_code=422,
        )
    if upload.content_type and upload.content_type.casefold() not in _XLSX_CONTENT_TYPES:
        raise ApplicationError(
            "unsupported_file_type",
            "The uploaded file does not have a supported .xlsx content type",
            status_code=415,
        )

    settings.upload_directory.mkdir(parents=True, exist_ok=True)
    storage_key = f"{uuid.uuid4().hex}.xlsx"
    path = settings.upload_directory / storage_key
    digest = hashlib.sha256()
    size_bytes = 0
    try:
        with path.open("xb") as destination:
            while chunk := upload.file.read(1024 * 1024):
                size_bytes += len(chunk)
                if size_bytes > settings.max_upload_size_bytes:
                    raise ApplicationError(
                        "upload_too_large",
                        "The workbook exceeds the configured upload limit",
                        status_code=413,
                        details={"limit_bytes": settings.max_upload_size_bytes},
                    )
                digest.update(chunk)
                destination.write(chunk)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally:
        upload.file.close()

    if size_bytes == 0:
        path.unlink(missing_ok=True)
        raise ApplicationError("empty_upload", "The uploaded workbook is empty", status_code=422)

    return StagedUpload(
        original_filename=original_filename,
        content_type=upload.content_type,
        storage_key=storage_key,
        path=path,
        size_bytes=size_bytes,
        checksum_sha256=digest.hexdigest(),
    )


def remove_staged_upload(staged: StagedUpload) -> None:
    staged.path.unlink(missing_ok=True)

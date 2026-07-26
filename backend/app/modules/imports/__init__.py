"""Pure Keepa workbook inspection and canonical column mapping."""

from app.modules.imports.domain import (
    CanonicalField,
    CanonicalValueType,
    CellIssue,
    ColumnMapping,
    MappingClassification,
    MappingReport,
    SourceCell,
    SourceColumn,
    WorkbookErrorCode,
    WorkbookInspection,
    WorkbookInspectionError,
    WorkbookRow,
    WorkbookSafetyLimits,
)
from app.modules.imports.mapping import MappingResolutionError, map_headers
from app.modules.imports.normalization import normalize_header
from app.modules.imports.registry import AliasRegistry, RegistryValidationError
from app.modules.imports.workbook import inspect_workbook, iter_workbook_rows, read_workbook_rows

__all__ = [
    "AliasRegistry",
    "CanonicalField",
    "CanonicalValueType",
    "CellIssue",
    "ColumnMapping",
    "MappingClassification",
    "MappingReport",
    "MappingResolutionError",
    "RegistryValidationError",
    "SourceCell",
    "SourceColumn",
    "WorkbookErrorCode",
    "WorkbookInspection",
    "WorkbookInspectionError",
    "WorkbookRow",
    "WorkbookSafetyLimits",
    "inspect_workbook",
    "iter_workbook_rows",
    "map_headers",
    "normalize_header",
    "read_workbook_rows",
]

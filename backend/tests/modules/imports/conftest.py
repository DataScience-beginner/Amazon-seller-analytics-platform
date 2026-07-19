from __future__ import annotations

import io
from collections.abc import Iterable, Sequence
from typing import Any, Protocol
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from openpyxl import Workbook

from app.modules.imports import AliasRegistry


class WorkbookBytesFactory(Protocol):
    def __call__(
        self,
        rows: Iterable[Sequence[Any]],
        *,
        title: str = "Products",
    ) -> bytes: ...


class ArchiveMemberAdder(Protocol):
    def __call__(self, source: bytes, member_name: str, content: bytes) -> bytes: ...


@pytest.fixture
def registry() -> AliasRegistry:
    return AliasRegistry.default()


@pytest.fixture
def make_workbook_bytes() -> WorkbookBytesFactory:
    def factory(
        rows: Iterable[Sequence[Any]],
        *,
        title: str = "Products",
    ) -> bytes:
        workbook = Workbook()
        worksheet = workbook.active
        assert worksheet is not None
        worksheet.title = title
        for row in rows:
            worksheet.append(list(row))
        output = io.BytesIO()
        workbook.save(output)
        workbook.close()
        return output.getvalue()

    return factory


@pytest.fixture
def add_archive_member() -> ArchiveMemberAdder:
    def add(source: bytes, member_name: str, content: bytes) -> bytes:
        output = io.BytesIO()
        with (
            ZipFile(io.BytesIO(source), "r") as original,
            ZipFile(output, "w", compression=ZIP_DEFLATED) as modified,
        ):
            for member in original.infolist():
                modified.writestr(member, original.read(member.filename))
            modified.writestr(member_name, content)
        return output.getvalue()

    return add

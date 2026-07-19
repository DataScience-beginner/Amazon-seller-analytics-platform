import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect


def test_alembic_upgrade_and_downgrade(tmp_path: Path) -> None:
    backend_dir = Path(__file__).parents[1]
    database_path = tmp_path / "migration-test.db"
    database_url = f"sqlite:///{database_path}"
    environment = {**os.environ, "DATABASE_URL": database_url}

    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    engine = create_engine(database_url)
    assert "organisations" in inspect(engine).get_table_names()
    assert "product_snapshots" in inspect(engine).get_table_names()
    engine.dispose()

    subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "base"],
        cwd=backend_dir,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    engine = create_engine(database_url)
    assert "organisations" not in inspect(engine).get_table_names()
    engine.dispose()

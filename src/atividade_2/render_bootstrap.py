"""Optional database bootstrap flow for hosted environments such as Render."""

from __future__ import annotations

import os
from pathlib import Path

from .config import load_settings
from .database_dump import DatabaseResetService
from .db import connect

DEFAULT_BACKUP_FILE = Path("backup_atividade_2.sql")
BOOTSTRAP_FLAG = "AUTO_RESTORE_ON_EMPTY_DB"
BOOTSTRAP_FILE_FLAG = "BOOTSTRAP_BACKUP_FILE"


def bootstrap_if_needed() -> bool:
    """Restore the canonical backup when the configured database is empty."""
    if not _is_enabled(os.environ.get(BOOTSTRAP_FLAG)):
        return False

    settings = load_settings()
    with connect(settings.database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT count(*)
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE';
                """
            )
            table_count = int(cursor.fetchone()[0])

    if table_count != 0:
        return False

    backup_file = Path(os.environ.get(BOOTSTRAP_FILE_FLAG, str(DEFAULT_BACKUP_FILE)))
    DatabaseResetService(backup_file=backup_file).restore_backup(backup_file)
    return True


def main() -> int:
    bootstrap_if_needed()
    return 0


def _is_enabled(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    raise SystemExit(main())

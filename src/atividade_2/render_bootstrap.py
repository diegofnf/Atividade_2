"""Optional database bootstrap flow for hosted environments such as Render."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from .config import load_settings
from .database_dump import DatabaseResetService
from .db import connect

DEFAULT_BACKUP_FILE = Path("backup_atividade_2.sql")
BOOTSTRAP_FLAG = "AUTO_RESTORE_ON_EMPTY_DB"
BOOTSTRAP_FILE_FLAG = "BOOTSTRAP_BACKUP_FILE"
BOOTSTRAP_METADATA_TABLE = "render_bootstrap_metadata"
REQUIRED_TABLES = (
    "datasets",
    "modelos",
    "perguntas",
    "respostas_atividade_1",
    "prompt_juizes",
    "avaliacoes_juiz",
)
REQUIRED_DATA_TABLES = (
    "datasets",
    "modelos",
    "perguntas",
    "respostas_atividade_1",
)


def bootstrap_if_needed() -> bool:
    """Restore the canonical backup when the database is empty, partial, or stale."""
    if not _is_enabled(os.environ.get(BOOTSTRAP_FLAG)):
        print("Render bootstrap disabled: AUTO_RESTORE_ON_EMPTY_DB is not enabled.", flush=True)
        return False

    settings = load_settings()
    backup_file = Path(os.environ.get(BOOTSTRAP_FILE_FLAG, str(DEFAULT_BACKUP_FILE)))
    backup_hash = _backup_sha256(backup_file)
    with connect(settings.database_url) as connection:
        with connection.cursor() as cursor:
            if _is_bootstrap_complete(cursor) and _restored_backup_hash(cursor) == backup_hash:
                print("Render bootstrap skipped: database already matches the versioned backup.", flush=True)
                return False

    print(f"Render bootstrap restoring database from {backup_file}.", flush=True)
    DatabaseResetService(backup_file=backup_file).restore_backup(backup_file)
    with connect(settings.database_url) as connection:
        with connection.cursor() as cursor:
            if not _is_bootstrap_complete(cursor):
                raise RuntimeError("Render bootstrap restore finished, but required backup data is still missing.")
            _record_restored_backup(cursor, backup_hash)
    print(f"Render bootstrap completed successfully with backup sha256={backup_hash}.", flush=True)
    return True


def _is_bootstrap_complete(cursor: object) -> bool:
    cursor.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE';
        """
    )
    table_names = {row[0] for row in cursor.fetchall()}
    if not table_names:
        return False
    if not set(REQUIRED_TABLES).issubset(table_names):
        return False

    for table_name in REQUIRED_DATA_TABLES:
        cursor.execute(f"SELECT count(*) FROM {table_name};")
        if int(cursor.fetchone()[0]) == 0:
            return False

    cursor.execute("SELECT count(*) FROM prompt_juizes WHERE ativo = TRUE;")
    active_prompt_count = int(cursor.fetchone()[0])
    return active_prompt_count > 0


def _restored_backup_hash(cursor: object) -> str | None:
    cursor.execute(f"SELECT to_regclass('public.{BOOTSTRAP_METADATA_TABLE}') IS NOT NULL;")
    if not bool(cursor.fetchone()[0]):
        return None
    cursor.execute(
        f"""
        SELECT backup_sha256
        FROM {BOOTSTRAP_METADATA_TABLE}
        WHERE id = 1;
        """
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return str(row[0])


def _record_restored_backup(cursor: object, backup_hash: str) -> None:
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {BOOTSTRAP_METADATA_TABLE} (
            id integer PRIMARY KEY,
            backup_sha256 text NOT NULL,
            restored_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    cursor.execute(
        f"""
        INSERT INTO {BOOTSTRAP_METADATA_TABLE} (id, backup_sha256)
        VALUES (1, %s)
        ON CONFLICT (id) DO UPDATE
        SET backup_sha256 = EXCLUDED.backup_sha256,
            restored_at = CURRENT_TIMESTAMP;
        """,
        (backup_hash,),
    )


def _backup_sha256(backup_file: Path) -> str:
    if not backup_file.exists():
        raise RuntimeError(f"Backup file not found: {backup_file}")

    digest = hashlib.sha256()
    with backup_file.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    bootstrap_if_needed()
    return 0


def _is_enabled(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    raise SystemExit(main())

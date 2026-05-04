from __future__ import annotations

from atividade_2.render_bootstrap import _backup_sha256, _is_bootstrap_complete, _record_restored_backup, _restored_backup_hash


class FakeCursor:
    def __init__(
        self,
        *,
        tables: set[str],
        counts: dict[str, int],
        metadata_hash: str | None = None,
    ) -> None:
        self.tables = tables
        self.counts = counts
        self.metadata_hash = metadata_hash
        self._last_sql = ""
        self._last_params = ()

    def execute(self, sql: str, params: tuple[str, ...] = ()) -> None:
        self._last_sql = sql
        self._last_params = params
        if "INSERT INTO render_bootstrap_metadata" in sql:
            self.metadata_hash = params[0]

    def fetchall(self) -> list[tuple[str]]:
        return [(table_name,) for table_name in self.tables]

    def fetchone(self) -> tuple[int] | tuple[str] | None:
        if "to_regclass('public.render_bootstrap_metadata')" in self._last_sql:
            return (self.metadata_hash is not None,)
        if "SELECT backup_sha256" in self._last_sql:
            if self.metadata_hash is None:
                return None
            return (self.metadata_hash,)
        if "prompt_juizes WHERE ativo = TRUE" in self._last_sql:
            return (self.counts.get("active_prompt_juizes", 0),)
        for table_name in self.counts:
            if f"FROM {table_name}" in self._last_sql:
                return (self.counts[table_name],)
        return (0,)


REQUIRED_TABLES = {
    "datasets",
    "modelos",
    "perguntas",
    "respostas_atividade_1",
    "prompt_juizes",
    "avaliacoes_juiz",
}


def test_bootstrap_is_incomplete_when_core_data_is_missing() -> None:
    cursor = FakeCursor(
        tables=REQUIRED_TABLES,
        counts={
            "datasets": 1,
            "modelos": 1,
            "perguntas": 0,
            "respostas_atividade_1": 1,
            "active_prompt_juizes": 1,
        },
    )

    assert _is_bootstrap_complete(cursor) is False


def test_bootstrap_is_complete_when_schema_and_seed_data_exist() -> None:
    cursor = FakeCursor(
        tables=REQUIRED_TABLES,
        counts={
            "datasets": 1,
            "modelos": 1,
            "perguntas": 1,
            "respostas_atividade_1": 1,
            "active_prompt_juizes": 1,
        },
    )

    assert _is_bootstrap_complete(cursor) is True


def test_backup_sha256_uses_backup_file_contents(tmp_path) -> None:
    backup_file = tmp_path / "backup_atividade_2.sql"
    backup_file.write_text("SELECT 1;\n", encoding="utf-8")

    assert _backup_sha256(backup_file) == "b4e0497804e46e0a0b0b8c31975b062152d551bac49c3c2e80932567b4085dcd"


def test_bootstrap_metadata_records_restored_backup_hash() -> None:
    cursor = FakeCursor(tables=REQUIRED_TABLES, counts={}, metadata_hash=None)

    assert _restored_backup_hash(cursor) is None

    _record_restored_backup(cursor, "abc123")

    assert _restored_backup_hash(cursor) == "abc123"

from __future__ import annotations

from atividade_2.render_bootstrap import _is_bootstrap_complete


class FakeCursor:
    def __init__(self, *, tables: set[str], counts: dict[str, int]) -> None:
        self.tables = tables
        self.counts = counts
        self._last_sql = ""

    def execute(self, sql: str) -> None:
        self._last_sql = sql

    def fetchall(self) -> list[tuple[str]]:
        return [(table_name,) for table_name in self.tables]

    def fetchone(self) -> tuple[int]:
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

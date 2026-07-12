from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1


def json_dumps(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, default=str)


def json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class JournalStore:
    """SQLite-backed journal, decision, and learning memory for review runs."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode = WAL;

                CREATE TABLE IF NOT EXISTS schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS review_runs (
                    run_id TEXT PRIMARY KEY,
                    run_date TEXT NOT NULL,
                    generated_at TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    goal_weekly_return_pct REAL NOT NULL,
                    freshness_status TEXT NOT NULL,
                    ml_status TEXT NOT NULL,
                    ml_model_kind TEXT NOT NULL,
                    llm_mode TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS decision_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    run_date TEXT NOT NULL,
                    portfolio_id TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    action TEXT NOT NULL,
                    decision_origin TEXT NOT NULL,
                    current_weight_pct REAL NOT NULL,
                    recommended_weight_pct REAL NOT NULL,
                    weight_change_pct REAL NOT NULL,
                    expected_5d_return_pct REAL NOT NULL,
                    confidence_score REAL NOT NULL,
                    evidence_summary TEXT NOT NULL,
                    intuition_summary TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    recommendation_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_decision_records_run
                    ON decision_records(run_id);
                CREATE INDEX IF NOT EXISTS idx_decision_records_ticker
                    ON decision_records(ticker, run_date);

                CREATE TABLE IF NOT EXISTS journal_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    entry_date TEXT NOT NULL,
                    entry_type TEXT NOT NULL,
                    basis TEXT NOT NULL,
                    category TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    details TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    source TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_journal_entries_run
                    ON journal_entries(run_id);
                CREATE INDEX IF NOT EXISTS idx_journal_entries_basis
                    ON journal_entries(basis, entry_date);

                CREATE TABLE IF NOT EXISTS outcome_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    decision_id INTEGER,
                    run_id TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    outcome_date TEXT NOT NULL,
                    horizon TEXT NOT NULL,
                    realized_return_pct REAL NOT NULL,
                    benchmark_return_pct REAL NOT NULL,
                    target_hit INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_outcome_records_run
                    ON outcome_records(run_id);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_outcome_records_unique
                    ON outcome_records(run_id, ticker, outcome_date, horizon);

                CREATE TABLE IF NOT EXISTS learning_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    entry_date TEXT NOT NULL,
                    learning_type TEXT NOT NULL,
                    basis TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    status TEXT NOT NULL,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_learning_records_status
                    ON learning_records(status, entry_date);

                CREATE TABLE IF NOT EXISTS signal_attribution (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    signal_name TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    contribution REAL NOT NULL,
                    evidence_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS llm_context_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    model TEXT NOT NULL,
                    used INTEGER NOT NULL,
                    context_json TEXT NOT NULL,
                    response_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_llm_context_snapshots_run
                    ON llm_context_snapshots(run_id);
                """
            )
            conn.execute(
                "INSERT OR REPLACE INTO schema_meta(key, value) VALUES (?, ?)",
                ("schema_version", str(SCHEMA_VERSION)),
            )

    def record_review(
        self,
        payload: dict[str, Any],
        recommendations: list[dict[str, Any]],
        diagnostics: list[dict[str, Any]],
        llm_context: dict[str, Any],
        llm_review: dict[str, Any],
    ) -> None:
        self.initialize()
        run_id = str(payload["run_id"])
        created_at = now_iso()
        ml = payload.get("ml", {})
        llm = payload.get("llm", {})
        freshness = payload.get("freshness", {})
        goal = payload.get("goal", {})
        with self.connect() as conn:
            conn.execute("DELETE FROM decision_records WHERE run_id = ?", (run_id,))
            conn.execute("DELETE FROM journal_entries WHERE run_id = ?", (run_id,))
            conn.execute("DELETE FROM learning_records WHERE run_id = ?", (run_id,))
            conn.execute("DELETE FROM llm_context_snapshots WHERE run_id = ?", (run_id,))
            conn.execute(
                """
                INSERT OR REPLACE INTO review_runs (
                    run_id, run_date, generated_at, model_version, goal_weekly_return_pct,
                    freshness_status, ml_status, ml_model_kind, llm_mode, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    str(payload.get("date", "")),
                    str(payload.get("generated_at", "")),
                    str(payload.get("model_version", "")),
                    float(goal.get("weekly_return_pct", 0.0)),
                    str(freshness.get("status", "")),
                    str(ml.get("status", "")),
                    str(ml.get("model_kind", "")),
                    str(llm.get("mode", "")),
                    json_dumps(payload),
                    created_at,
                ),
            )
            for recommendation in recommendations:
                conn.execute(
                    """
                    INSERT INTO decision_records (
                        run_id, run_date, portfolio_id, ticker, action, decision_origin,
                        current_weight_pct, recommended_weight_pct, weight_change_pct,
                        expected_5d_return_pct, confidence_score, evidence_summary,
                        intuition_summary, model_version, recommendation_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        str(recommendation.get("date", "")),
                        str(recommendation.get("portfolio_id", "")),
                        str(recommendation.get("ticker", "")),
                        str(recommendation.get("action", "")),
                        str(recommendation.get("decision_origin", "")),
                        float(recommendation.get("current_weight_pct", 0.0)),
                        float(recommendation.get("recommended_weight_pct", 0.0)),
                        float(recommendation.get("weight_change_pct", 0.0)),
                        float(recommendation.get("expected_5d_return_pct", 0.0)),
                        float(recommendation.get("confidence_score", 0.0)),
                        str(recommendation.get("evidence_summary", "")),
                        str(recommendation.get("intuition_summary", "")),
                        str(recommendation.get("model_version", "")),
                        json_dumps(recommendation),
                        created_at,
                    ),
                )
                self._insert_journal_entry(
                    conn,
                    run_id=run_id,
                    entry_date=str(recommendation.get("date", "")),
                    entry_type="recommendation",
                    basis="evidence",
                    category="mechanical_decision",
                    summary=str(recommendation.get("evidence_summary", "")),
                    details=str(recommendation.get("thesis", "")),
                    ticker=str(recommendation.get("ticker", "")),
                    confidence=float(recommendation.get("confidence_score", 0.0)) / 100.0,
                    source="mechanical",
                    payload=recommendation,
                    created_at=created_at,
                )
                self._insert_journal_entry(
                    conn,
                    run_id=run_id,
                    entry_date=str(recommendation.get("date", "")),
                    entry_type="recommendation",
                    basis="intuition",
                    category="intuition_placeholder",
                    summary=str(recommendation.get("intuition_summary", "")),
                    details="Stored separately so future LLM/human intuition can be evaluated against outcomes.",
                    ticker=str(recommendation.get("ticker", "")),
                    confidence=0.0,
                    source="placeholder",
                    payload=recommendation,
                    created_at=created_at,
                )
            for diagnostic in diagnostics:
                self._insert_journal_entry(
                    conn,
                    run_id=run_id,
                    entry_date=str(diagnostic.get("date", payload.get("date", ""))),
                    entry_type="goal_progress",
                    basis="evidence",
                    category="portfolio_diagnostic",
                    summary=(
                        f"{diagnostic.get('portfolio_id', '')} weekly return "
                        f"{diagnostic.get('weekly_return_pct', 0.0)}%; target gap "
                        f"{diagnostic.get('target_gap_pct', 0.0)}%."
                    ),
                    details=json_dumps(diagnostic),
                    ticker="",
                    confidence=1.0,
                    source="mechanical",
                    payload=diagnostic,
                    created_at=created_at,
                )
            self._insert_llm_outputs(conn, run_id, str(payload.get("date", "")), llm_review, created_at)
            conn.execute(
                """
                INSERT INTO llm_context_snapshots (
                    run_id, created_at, model, used, context_json, response_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    created_at,
                    str(llm_review.get("model") or llm.get("model", "")),
                    1 if llm_review.get("used") else 0,
                    json_dumps(llm_context),
                    json_dumps(llm_review),
                ),
            )

    def record_learning(
        self,
        run_id: str,
        entry_date: str,
        learning_type: str,
        basis: str,
        summary: str,
        evidence: dict[str, Any] | None = None,
        confidence: float = 0.0,
        status: str = "active",
        source: str = "manual",
    ) -> None:
        self.initialize()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO learning_records (
                    run_id, entry_date, learning_type, basis, summary, evidence_json,
                    confidence, status, source, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    entry_date,
                    learning_type,
                    basis,
                    summary,
                    json_dumps(evidence or {}),
                    float(confidence),
                    status,
                    source,
                    now_iso(),
                ),
            )

    def get_run(self, run_id: str) -> dict[str, Any]:
        self.initialize()
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM review_runs WHERE run_id = ?", (run_id,)).fetchone()
        return self._row_to_dict(row)

    def decision_history(self, limit: int = 50) -> list[dict[str, Any]]:
        self.initialize()
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM decision_records ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def decisions_missing_outcomes(self, outcome_date: str, horizon: str = "review_to_review", limit: int = 250) -> list[dict[str, Any]]:
        self.initialize()
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT d.* FROM decision_records d
                WHERE d.run_date < ?
                  AND NOT EXISTS (
                    SELECT 1 FROM outcome_records o
                    WHERE o.run_id = d.run_id
                      AND o.ticker = d.ticker
                      AND o.outcome_date = ?
                      AND o.horizon = ?
                  )
                ORDER BY d.id DESC
                LIMIT ?
                """,
                (outcome_date, outcome_date, horizon, limit),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def record_outcome(
        self,
        decision: dict[str, Any],
        outcome_date: str,
        horizon: str,
        realized_return_pct: float,
        benchmark_return_pct: float,
        target_hit: bool,
        payload: dict[str, Any],
    ) -> None:
        self.initialize()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO outcome_records (
                    decision_id, run_id, ticker, outcome_date, horizon,
                    realized_return_pct, benchmark_return_pct, target_hit,
                    payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision.get("id"),
                    str(decision.get("run_id", "")),
                    str(decision.get("ticker", "")),
                    outcome_date,
                    horizon,
                    float(realized_return_pct),
                    float(benchmark_return_pct),
                    1 if target_hit else 0,
                    json_dumps(payload),
                    now_iso(),
                ),
            )

    def recent_outcomes(self, limit: int = 30) -> list[dict[str, Any]]:
        self.initialize()
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM outcome_records ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def recent_journal_entries(self, limit: int = 30, include_recommendations: bool = True) -> list[dict[str, Any]]:
        self.initialize()
        where_clause = ""
        if not include_recommendations:
            where_clause = "WHERE entry_type != 'recommendation' AND category != 'intuition_placeholder'"
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM journal_entries {where_clause} ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def recent_learnings(self, limit: int = 12) -> list[dict[str, Any]]:
        self.initialize()
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM learning_records
                WHERE status = 'active'
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def context_snapshots(self, run_id: str) -> list[dict[str, Any]]:
        self.initialize()
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM llm_context_snapshots WHERE run_id = ? ORDER BY id DESC",
                (run_id,),
            ).fetchall()
        snapshots = []
        for row in rows:
            item = self._row_to_dict(row)
            item["context"] = json_loads(item.pop("context_json", ""), {})
            item["response"] = json_loads(item.pop("response_json", ""), {})
            snapshots.append(item)
        return snapshots

    def build_memory(self, learning_limit: int = 10, journal_limit: int = 12, decision_limit: int = 20) -> dict[str, Any]:
        return {
            "recent_learnings": self.recent_learnings(limit=learning_limit),
            "recent_journal_entries": self.recent_journal_entries(limit=journal_limit, include_recommendations=False),
            "recent_decisions": self.decision_history(limit=decision_limit),
            "recent_outcomes": self.recent_outcomes(limit=decision_limit),
        }

    def _insert_llm_outputs(
        self,
        conn: sqlite3.Connection,
        run_id: str,
        entry_date: str,
        llm_review: dict[str, Any],
        created_at: str,
    ) -> None:
        result = llm_review.get("result") if isinstance(llm_review.get("result"), dict) else {}
        if not isinstance(result, dict):
            return
        for entry in result.get("journal_entries", []) or []:
            if not isinstance(entry, dict):
                continue
            linked = entry.get("linked_tickers") or []
            ticker = ",".join(str(item) for item in linked) if isinstance(linked, list) else str(linked)
            self._insert_journal_entry(
                conn,
                run_id=run_id,
                entry_date=entry_date,
                entry_type=str(entry.get("entry_type", "llm_note")),
                basis=str(entry.get("basis", "evidence")),
                category=str(entry.get("category", "llm_review")),
                summary=str(entry.get("summary", "")),
                details=str(entry.get("details", "")),
                ticker=ticker,
                confidence=float(entry.get("confidence", 0.0)),
                source="llm",
                payload=entry,
                created_at=created_at,
            )
        for learning in result.get("learning_records", []) or []:
            if not isinstance(learning, dict):
                continue
            conn.execute(
                """
                INSERT INTO learning_records (
                    run_id, entry_date, learning_type, basis, summary, evidence_json,
                    confidence, status, source, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    entry_date,
                    str(learning.get("learning_type", "general")),
                    str(learning.get("basis", "evidence")),
                    str(learning.get("summary", "")),
                    json_dumps(learning.get("evidence", {})),
                    float(learning.get("confidence", 0.0)),
                    str(learning.get("status", "active")),
                    "llm",
                    created_at,
                ),
            )

    def _insert_journal_entry(
        self,
        conn: sqlite3.Connection,
        run_id: str,
        entry_date: str,
        entry_type: str,
        basis: str,
        category: str,
        summary: str,
        details: str,
        ticker: str,
        confidence: float,
        source: str,
        payload: dict[str, Any],
        created_at: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO journal_entries (
                run_id, entry_date, entry_type, basis, category, summary, details,
                ticker, confidence, source, payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                entry_date,
                entry_type,
                basis,
                category,
                summary,
                details,
                ticker,
                float(confidence),
                source,
                json_dumps(payload),
                created_at,
            ),
        )

    def _row_to_dict(self, row: sqlite3.Row | None) -> dict[str, Any]:
        if row is None:
            return {}
        item = dict(row)
        for source, target in [
            ("payload_json", "payload"),
            ("recommendation_json", "recommendation"),
            ("evidence_json", "evidence"),
        ]:
            if source in item:
                item[target] = json_loads(item.pop(source), {})
        return item

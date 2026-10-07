"""CHECK canônico de system_integration_credentials — única fonte no redeploy."""

from __future__ import annotations

from pathlib import Path

CANONICAL_PROVIDERS = (
    "google_login_cadu",
    "google_login_centralx",
    "google_workspace",
    "google_calendar",
    "higgsfield",
    "openrouter",
    "openai",
    "typesafe",
    "firecrawl",
    "dify",
    "dify_cadu_chat",
    "brevo",
    "d4sign",
    "screenshotone",
)

SQL_PATH = Path(__file__).with_name("integration_provider_check.sql")


def provider_in_check_constraint(cursor, provider: str) -> bool:
    cursor.execute(
        """
        SELECT pg_get_constraintdef(oid) AS definition
          FROM pg_constraint
         WHERE conname = 'system_integration_credentials_provider_check'
        """
    )
    definition = (cursor.fetchone() or {}).get("definition") or ""
    return f"'{provider}'" in definition


def apply_provider_check(cursor) -> None:
    cursor.execute(SQL_PATH.read_text(encoding="utf-8"))


def ensure_provider_in_check(cursor, provider: str) -> None:
    if not provider_in_check_constraint(cursor, provider):
        apply_provider_check(cursor)


def assert_known_providers(cursor) -> None:
    cursor.execute("SELECT provider FROM system_integration_credentials ORDER BY 1")
    rows = [row["provider"] if isinstance(row, dict) else row[0] for row in cursor.fetchall()]
    unknown = [provider for provider in rows if provider not in CANONICAL_PROVIDERS]
    if unknown:
        raise RuntimeError(
            "Providers em system_integration_credentials fora da lista canônica: "
            + ", ".join(unknown)
            + ". Corrija ou amplie CANONICAL_PROVIDERS antes do deploy."
        )

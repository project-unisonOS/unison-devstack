import os


def test_no_sqlite_in_prod():
    """Prevent prod configs from pointing to SQLite."""
    env = os.getenv("ENVIRONMENT", "").lower()
    if env != "prod":
        return
    storage_url = os.getenv("STORAGE_DATABASE_URL", "")
    context_url = os.getenv("UNISON_CONTEXT_DATABASE_URL", "")
    assert not storage_url.startswith("sqlite"), "STORAGE_DATABASE_URL cannot be sqlite in prod"
    assert not context_url.startswith("sqlite"), "UNISON_CONTEXT_DATABASE_URL cannot be sqlite in prod"

"""Settings behaviour that other modules rely on."""

from cartiq_api.config import Settings, get_settings


def test_cors_origins_split_and_trimmed():
    settings = Settings(API_CORS_ORIGINS="http://a.test, http://b.test ,")
    assert settings.cors_origins == ["http://a.test", "http://b.test"]


def test_sqlalchemy_url_uses_psycopg3_and_drops_query_params():
    settings = Settings(DATABASE_URL="postgresql://u:p@h:5433/db?schema=public")
    assert settings.sqlalchemy_url == "postgresql+psycopg://u:p@h:5433/db"


def test_non_postgres_url_is_passed_through():
    settings = Settings(DATABASE_URL="sqlite:///tmp/x.db")
    assert settings.sqlalchemy_url == "sqlite:///tmp/x.db"


def test_settings_are_cached():
    assert get_settings() is get_settings()


def test_assignment_salt_default_matches_shared_vectors(assignment_vectors):
    # A mismatch here would silently invalidate every experiment.
    assert Settings().flag_hash_salt == assignment_vectors["salt"]

from pathlib import Path

from app.core.config import Settings, get_existing_env_files


def test_get_existing_env_files_prefers_available_files(
    monkeypatch,
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    example_file = tmp_path / ".env.example"
    example_file.write_text("APP_NAME=Fallback App\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    assert get_existing_env_files() == (".env.example",)

    env_file.write_text("APP_NAME=Primary App\n", encoding="utf-8")

    assert get_existing_env_files() == (".env", ".env.example")


def test_settings_load_from_example_when_env_is_missing(
    tmp_path: Path,
) -> None:
    example_file = tmp_path / ".env.example"
    example_file.write_text("APP_NAME=Fallback App\n", encoding="utf-8")

    settings = Settings(_env_file=(tmp_path / ".env", example_file))

    assert settings.app_name == "Fallback App"


def test_production_settings_reject_placeholder_secrets() -> None:
    try:
        Settings(
            app_env="production",
            secret_key="replace-with-local-dev-secret-key",
            admin_token="replace-with-local-dev-admin-token",
            _env_file=None,
        )
    except ValueError as exc:
        assert "SECRET_KEY, ADMIN_TOKEN" in str(exc)
    else:
        raise AssertionError("Production placeholder secrets were accepted")


def test_production_settings_accept_custom_secrets() -> None:
    settings = Settings(
        app_env="production",
        secret_key="portfolio-secret-key",
        admin_token="portfolio-admin-token",
        _env_file=None,
    )

    assert settings.app_env == "production"

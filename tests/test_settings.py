from pathlib import Path

from app.core.config import Settings, get_existing_env_files


def test_get_existing_env_files_ignores_example_template(
    monkeypatch,
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    example_file = tmp_path / ".env.example"
    example_file.write_text("APP_NAME=Fallback App\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    assert get_existing_env_files() == ()

    env_file.write_text("APP_NAME=Primary App\n", encoding="utf-8")

    assert get_existing_env_files() == (".env",)


def test_default_seed_on_startup_is_disabled() -> None:
    settings = Settings(_env_file=None)

    assert settings.seed_on_startup is False


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


def test_production_settings_reject_placeholder_secret_key() -> None:
    try:
        Settings(
            app_env="production",
            secret_key="replace-with-local-dev-secret-key",
            admin_token="portfolio-admin-token",
            _env_file=None,
        )
    except ValueError as exc:
        assert "SECRET_KEY" in str(exc)
    else:
        raise AssertionError("Production placeholder SECRET_KEY was accepted")


def test_production_settings_reject_placeholder_admin_token() -> None:
    try:
        Settings(
            app_env="production",
            secret_key="portfolio-secret-key",
            admin_token="replace-with-local-dev-admin-token",
            _env_file=None,
        )
    except ValueError as exc:
        assert "ADMIN_TOKEN" in str(exc)
    else:
        raise AssertionError("Production placeholder ADMIN_TOKEN was accepted")


def test_production_settings_accept_custom_secrets() -> None:
    settings = Settings(
        app_env="production",
        secret_key="portfolio-secret-key",
        admin_token="portfolio-admin-token",
        _env_file=None,
    )

    assert settings.app_env == "production"

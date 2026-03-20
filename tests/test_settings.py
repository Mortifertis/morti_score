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

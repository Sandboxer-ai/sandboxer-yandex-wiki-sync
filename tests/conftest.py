"""Общие фикстуры для тестов."""

from unittest.mock import MagicMock

import pytest

from sandboxer.wiki_sync.core.config import Settings, SyncSettings, WikiSettings


@pytest.fixture
def mock_api():
    """Мок WikiAPI."""
    api = MagicMock()
    api.token = "test_token"
    api.org_id = "123456"
    api.api_url = "https://api.wiki.test/v1"
    api.timeout = 60
    return api


@pytest.fixture
def settings():
    """Тестовые настройки."""
    return Settings(
        token="test_token",
        wiki=WikiSettings(
            org_id="123",
            base_slug="users/test",
            docs_dir="docs",
        ),
        sync=SyncSettings(
            ignore=["*.draft.md", "_*"],
            strip_title=True,
            timeout=60,
        ),
    )


@pytest.fixture
def docs_dir(tmp_path):
    """Временная директория для документов."""
    docs = tmp_path / "docs"
    docs.mkdir()
    return docs


@pytest.fixture
def sample_markdown():
    """Пример Markdown контента."""
    return """# Тестовая страница

Это тестовый контент.

## Подзаголовок

Ещё текст.
"""


@pytest.fixture
def config_file(tmp_path):
    """Создать временный файл конфигурации."""
    config_content = """
[wiki]
org_id = "123456"
base_slug = "users/test/project"
docs_dir = "docs"

[sync]
ignore = ["*.draft.md"]
strip_title = true
timeout = 60
"""
    config_path = tmp_path / ".wiki-sync.toml"
    config_path.write_text(config_content)
    return config_path


@pytest.fixture
def env_token(monkeypatch):
    """Установить токен в переменные окружения."""
    monkeypatch.setenv("WIKI_SYNC_TOKEN", "test_env_token")
    yield "test_env_token"
    # Cleanup происходит автоматически через monkeypatch


@pytest.fixture
def clean_env(monkeypatch):
    """Очистить переменные окружения wiki-sync."""
    monkeypatch.delenv("WIKI_SYNC_TOKEN", raising=False)
    monkeypatch.delenv("WIKI_SYNC_ORG_ID", raising=False)


@pytest.fixture
def mock_page_info():
    """Мок информации о странице."""
    page = MagicMock()
    page.id = 123
    page.slug = "users/test/page"
    page.title = "Test Page"
    page.page_type = "wysiwyg"
    return page


@pytest.fixture
def mock_page_content():
    """Мок контента страницы."""
    from datetime import UTC, datetime

    page = MagicMock()
    page.id = 123
    page.slug = "users/test/page"
    page.title = "Test Page"
    page.content = "This is test content."
    page.modified_at = datetime(2025, 12, 28, 10, 0, 0, tzinfo=UTC)
    return page

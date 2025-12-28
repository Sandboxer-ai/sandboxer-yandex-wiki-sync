"""Тесты для WikiSync."""

from unittest.mock import MagicMock

import pytest

from sandboxer.wiki_sync.core.config import Settings, SyncSettings, WikiSettings
from sandboxer.wiki_sync.core.sync import WikiSync


@pytest.fixture
def mock_api():
    """Мок WikiAPI."""
    return MagicMock()


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
            ignore=["*.draft.md"],
            strip_title=True,
        ),
    )


@pytest.fixture
def sync(mock_api, settings, tmp_path):
    """Создать WikiSync с временной директорией."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    return WikiSync(
        api=mock_api,
        docs_dir=docs_dir,
        base_slug="users/test",
        settings=settings,
    )


class TestWikiSync:
    """Тесты для WikiSync."""

    def test_path_to_slug_simple(self, sync, tmp_path):
        """Простое преобразование пути в slug."""
        docs_dir = tmp_path / "docs"
        file_path = docs_dir / "page.md"
        file_path.touch()

        slug = sync._path_to_slug(file_path)
        assert slug == "users/test/page"

    def test_path_to_slug_nested(self, sync, tmp_path):
        """Вложенный путь."""
        docs_dir = tmp_path / "docs"
        subdir = docs_dir / "folder"
        subdir.mkdir()
        file_path = subdir / "page.md"
        file_path.touch()

        slug = sync._path_to_slug(file_path)
        assert slug == "users/test/folder/page"

    def test_path_to_slug_index(self, sync, tmp_path):
        """index.md → родительская директория."""
        docs_dir = tmp_path / "docs"
        subdir = docs_dir / "folder"
        subdir.mkdir()
        file_path = subdir / "index.md"
        file_path.touch()

        slug = sync._path_to_slug(file_path)
        assert slug == "users/test/folder"

    def test_path_to_slug_root_index(self, sync, tmp_path):
        """index.md в корне → базовый slug."""
        docs_dir = tmp_path / "docs"
        file_path = docs_dir / "index.md"
        file_path.touch()

        slug = sync._path_to_slug(file_path)
        assert slug == "users/test"

    def test_slug_to_path_simple(self, sync, tmp_path):
        """Простое преобразование slug в путь."""
        path = sync._slug_to_path("users/test/page")
        expected = tmp_path / "docs" / "page.md"
        assert path == expected

    def test_slug_to_path_base(self, sync, tmp_path):
        """Базовый slug → index.md."""
        path = sync._slug_to_path("users/test")
        expected = tmp_path / "docs" / "index.md"
        assert path == expected

    def test_is_ignored(self, sync, tmp_path):
        """Проверка игнорирования файлов."""
        docs_dir = tmp_path / "docs"

        assert sync._is_ignored(docs_dir / "readme.draft.md") is True
        assert sync._is_ignored(docs_dir / "page.md") is False

    def test_extract_title_from_heading(self, sync):
        """Извлечение заголовка из # heading."""
        content = "# My Title\n\nContent here"
        title = sync._extract_title(content, "default")
        assert title == "My Title"

    def test_extract_title_default(self, sync):
        """Заголовок по умолчанию если нет #."""
        content = "No heading here"
        title = sync._extract_title(content, "my-file-name")
        assert title == "My File Name"

    def test_strip_title(self, sync):
        """Удаление # заголовка из контента."""
        content = "# Title\n\nContent"
        stripped = sync._strip_title(content)
        assert stripped == "Content"

    def test_strip_title_no_heading(self, sync):
        """Без заголовка — контент без изменений."""
        content = "Just content"
        stripped = sync._strip_title(content)
        assert stripped == "Just content"

    def test_strip_title_empty_lines(self, sync):
        """Пропуск пустых строк перед заголовком."""
        content = "\n\n# Title\n\nContent"
        stripped = sync._strip_title(content)
        assert stripped == "Content"


class TestWikiSyncGetStatus:
    """Тесты для get_status."""

    def test_new_file(self, sync, mock_api, tmp_path):
        """Новый файл без страницы в Wiki."""
        docs_dir = tmp_path / "docs"
        file_path = docs_dir / "new-page.md"
        file_path.write_text("# New Page\n\nContent")

        mock_api.get_page_info.return_value = None

        result = sync.get_status()

        assert len(result.new) == 1
        assert result.new[0].slug == "users/test/new-page"

    def test_synced_file(self, sync, mock_api, tmp_path):
        """Синхронизированный файл."""
        docs_dir = tmp_path / "docs"
        file_path = docs_dir / "synced.md"
        file_path.write_text("# Synced\n\nContent")

        mock_page = MagicMock()
        mock_page.id = 1
        mock_page.title = "Synced"
        mock_page.content = "Content"  # Без заголовка — так хранится в Wiki
        mock_page.modified_at = None
        mock_api.get_page_info.return_value = mock_page

        result = sync.get_status()

        assert len(result.synced) == 1


class TestWikiSyncPush:
    """Тесты для push операций."""

    def test_push_new_file(self, sync, mock_api, tmp_path):
        """Загрузка нового файла."""
        from sandboxer.wiki_sync.core.models import FileStatus, SyncStatus

        docs_dir = tmp_path / "docs"
        file_path = docs_dir / "new.md"
        file_path.write_text("# New Page\n\nContent")

        mock_api.get_page.return_value = None
        mock_new_page = MagicMock()
        mock_new_page.id = 999
        mock_api.create_page.return_value = mock_new_page

        fs = FileStatus(
            slug="users/test/new",
            file_path=file_path,
            status=SyncStatus.NEW,
        )

        result = sync.push_file(fs)

        assert result is True
        mock_api.create_page.assert_called_once_with(
            "users/test/new",
            "New Page",
            "Content",
        )

    def test_push_existing_file(self, sync, mock_api, tmp_path):
        """Обновление существующего файла."""
        from sandboxer.wiki_sync.core.models import FileStatus, SyncStatus

        docs_dir = tmp_path / "docs"
        file_path = docs_dir / "existing.md"
        file_path.write_text("# Updated\n\nNew content")

        mock_page = MagicMock()
        mock_page.id = 123
        mock_api.get_page.return_value = mock_page
        mock_api.update_page.return_value = mock_page

        fs = FileStatus(
            slug="users/test/existing",
            file_path=file_path,
            status=SyncStatus.MODIFIED,
        )

        result = sync.push_file(fs)

        assert result is True
        mock_api.update_page.assert_called_once_with(
            123,
            "Updated",
            "New content",
        )

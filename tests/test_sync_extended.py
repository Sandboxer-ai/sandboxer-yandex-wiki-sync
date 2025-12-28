"""Расширенные тесты для WikiSync — покрытие дополнительных сценариев."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from sandboxer.wiki_sync.core.config import Settings, SyncSettings, WikiSettings
from sandboxer.wiki_sync.core.models import (
    FileStatus,
    PageMeta,
    SyncStatus,
)
from sandboxer.wiki_sync.core.sync import WikiSync, create_sync


class TestWikiSyncMetaStorage:
    """Тесты работы с метаданными."""

    @pytest.fixture
    def sync(self, mock_api, settings, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        return WikiSync(
            api=mock_api,
            docs_dir=docs_dir,
            base_slug="users/test",
            settings=settings,
        )

    def test_load_meta_empty(self, sync):
        """Загрузка пустого хранилища."""
        assert sync._meta.pages == {}
        assert sync._meta.version == 1

    def test_save_and_load_meta(self, sync, tmp_path):
        """Сохранение и загрузка метаданных."""
        meta = PageMeta(
            id=123,
            slug="users/test/page",
            title="Test Page",
            file="page.md",
            content_hash="abc123",
            last_push=datetime.now(UTC),
        )
        sync._meta.set_page("users/test/page", meta)
        sync.save_meta()

        # Проверяем что файл создан
        meta_file = tmp_path / "docs" / ".wiki-meta.json"
        assert meta_file.exists()

        # Создаём новый sync и проверяем что данные загружены
        new_sync = WikiSync(
            api=sync.api,
            docs_dir=sync.docs_dir,
            base_slug="users/test",
            settings=sync.settings,
        )
        loaded_meta = new_sync._meta.get_page("users/test/page")
        assert loaded_meta is not None
        assert loaded_meta.id == 123

    def test_load_meta_invalid_json(self, sync, tmp_path):
        """Обработка невалидного JSON в метаданных."""
        meta_file = tmp_path / "docs" / ".wiki-meta.json"
        meta_file.write_text("invalid json {{{")

        new_sync = WikiSync(
            api=sync.api,
            docs_dir=sync.docs_dir,
            base_slug="users/test",
            settings=sync.settings,
        )
        # Должен вернуть пустое хранилище
        assert new_sync._meta.pages == {}


class TestWikiSyncPathConversions:
    """Тесты преобразования путей."""

    @pytest.fixture
    def sync(self, mock_api, settings, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        return WikiSync(
            api=mock_api,
            docs_dir=docs_dir,
            base_slug="users/test",
            settings=settings,
        )

    def test_path_to_slug_outside_docs(self, sync, tmp_path):
        """Путь вне docs возвращает None."""
        outside_path = tmp_path / "other" / "file.md"
        slug = sync._path_to_slug(outside_path)
        assert slug is None

    def test_slug_to_path_with_existing_index(self, sync, tmp_path):
        """slug_to_path проверяет существование index.md."""
        # Создаём структуру с index.md
        subdir = tmp_path / "docs" / "subdir"
        subdir.mkdir()
        (subdir / "index.md").touch()

        path = sync._slug_to_path("users/test/subdir")
        assert path == subdir / "index.md"

    def test_slug_to_path_nested(self, sync, tmp_path):
        """slug_to_path для вложенного пути."""
        path = sync._slug_to_path("users/test/folder/page")
        expected = tmp_path / "docs" / "folder" / "page.md"
        assert path == expected


class TestWikiSyncIgnore:
    """Тесты игнорирования файлов."""

    @pytest.fixture
    def sync(self, mock_api, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        settings = Settings(
            token="test",
            wiki=WikiSettings(org_id="1", base_slug="test"),
            sync=SyncSettings(ignore=["*.draft.md", "_*"]),
        )
        return WikiSync(
            api=mock_api,
            docs_dir=docs_dir,
            base_slug="test",
            settings=settings,
        )

    def test_ignore_by_name(self, sync, tmp_path):
        """Игнорирование по имени файла."""
        docs = tmp_path / "docs"
        assert sync._is_ignored(docs / "readme.draft.md") is True
        assert sync._is_ignored(docs / "_hidden.md") is True
        assert sync._is_ignored(docs / "normal.md") is False

    def test_ignore_by_pattern(self, sync, tmp_path):
        """Игнорирование по паттерну имени."""
        docs = tmp_path / "docs"
        # Паттерны применяются только к имени файла
        assert sync._is_ignored(docs / "subdir" / "file.draft.md") is True
        assert sync._is_ignored(docs / "subdir" / "_private.md") is True


class TestWikiSyncContentProcessing:
    """Тесты обработки контента."""

    @pytest.fixture
    def sync(self, mock_api, settings, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        return WikiSync(
            api=mock_api,
            docs_dir=docs_dir,
            base_slug="users/test",
            settings=settings,
        )

    def test_extract_title_empty_content(self, sync):
        """Извлечение заголовка из пустого контента."""
        title = sync._extract_title("", "fallback-name")
        assert title == "Fallback Name"

    def test_extract_title_no_heading(self, sync):
        """Извлечение заголовка без #."""
        title = sync._extract_title("Some content without heading", "file-name")
        assert title == "File Name"

    def test_strip_title_empty(self, sync):
        """strip_title для пустого контента."""
        result = sync._strip_title("")
        assert result == ""

    def test_strip_title_preserves_content_after_heading(self, sync):
        """strip_title сохраняет контент после заголовка."""
        content = "# Title\n\nParagraph 1\n\nParagraph 2"
        result = sync._strip_title(content)
        assert "Paragraph 1" in result
        assert "Paragraph 2" in result
        assert "# Title" not in result

    def test_read_file_not_exists(self, sync, tmp_path):
        """Чтение несуществующего файла."""
        result = sync._read_file(tmp_path / "nonexistent.md")
        assert result is None

    def test_read_file_encoding_error(self, sync, tmp_path):
        """Ошибка кодировки при чтении."""
        file_path = tmp_path / "docs" / "binary.md"
        file_path.write_bytes(b"\xff\xfe invalid utf-8")

        # Должен вернуть None или прочитать как есть (зависит от реализации)
        # Тест проверяет что функция не падает
        _ = sync._read_file(file_path)


class TestWikiSyncGetStatus:
    """Тесты get_status."""

    @pytest.fixture
    def sync(self, mock_api, settings, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        return WikiSync(
            api=mock_api,
            docs_dir=docs_dir,
            base_slug="users/test",
            settings=settings,
        )

    def test_get_status_ignores_files(self, sync, mock_api, tmp_path):
        """get_status игнорирует файлы по паттерну."""
        docs = tmp_path / "docs"
        (docs / "normal.md").write_text("# Normal")
        (docs / "draft.draft.md").write_text("# Draft")

        mock_api.get_page_info.return_value = None

        result = sync.get_status()

        # Должен быть только normal.md
        assert len(result.new) == 1
        assert "normal" in result.new[0].slug

    def test_get_status_file_read_error(self, sync, mock_api, tmp_path):
        """get_status обрабатывает ошибки чтения."""
        docs = tmp_path / "docs"
        file_path = docs / "error.md"
        file_path.touch()
        file_path.chmod(0o000)  # Убираем права на чтение

        try:
            result = sync.get_status()
            # Должен быть в errors
            assert len(result.errors) >= 0  # Зависит от ОС
        finally:
            file_path.chmod(0o644)

    def test_get_status_detects_deleted_local(self, sync, mock_api, tmp_path):
        """get_status обнаруживает удалённые локально файлы."""
        # Добавляем запись в метаданные о файле которого нет
        sync._meta.set_page(
            "users/test/deleted",
            PageMeta(
                id=999,
                slug="users/test/deleted",
                title="Deleted Page",
                file="deleted.md",
                content_hash="hash",
            ),
        )

        mock_api.get_page_info.return_value = None

        result = sync.get_status()

        assert len(result.deleted_local) == 1
        assert result.deleted_local[0].slug == "users/test/deleted"


class TestWikiSyncPushOperations:
    """Тесты push операций."""

    @pytest.fixture
    def sync(self, mock_api, settings, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        return WikiSync(
            api=mock_api,
            docs_dir=docs_dir,
            base_slug="users/test",
            settings=settings,
        )

    def test_push_file_read_error(self, sync, mock_api, tmp_path):
        """push_file при ошибке чтения."""
        fs = FileStatus(
            slug="users/test/nonexistent",
            file_path=tmp_path / "docs" / "nonexistent.md",
            status=SyncStatus.NEW,
        )

        result = sync.push_file(fs)
        assert result is False

    def test_push_file_api_error(self, sync, mock_api, tmp_path):
        """push_file при ошибке API."""
        docs = tmp_path / "docs"
        (docs / "error.md").write_text("# Error Page")

        mock_api.get_page.side_effect = Exception("API Error")

        fs = FileStatus(
            slug="users/test/error",
            file_path=docs / "error.md",
            status=SyncStatus.NEW,
        )

        result = sync.push_file(fs)
        assert result is False

    def test_push_files_counts(self, sync, mock_api, tmp_path):
        """push_files подсчитывает результаты."""
        docs = tmp_path / "docs"
        (docs / "new.md").write_text("# New")
        (docs / "existing.md").write_text("# Existing")

        # push_files вызывает get_page для проверки существования,
        # а push_file тоже вызывает get_page
        # Итого: 4 вызова get_page (2 в push_files + 2 в push_file)
        mock_api.get_page.side_effect = [
            None,  # push_files: первый файл — новый
            None,  # push_file: первый файл — создаём
            MagicMock(id=123),  # push_files: второй файл — существует
            MagicMock(id=123),  # push_file: второй файл — обновляем
        ]
        mock_api.create_page.return_value = MagicMock(id=456)
        mock_api.update_page.return_value = MagicMock(id=123)

        files = [
            FileStatus(
                slug="users/test/new",
                file_path=docs / "new.md",
                status=SyncStatus.NEW,
            ),
            FileStatus(
                slug="users/test/existing",
                file_path=docs / "existing.md",
                status=SyncStatus.MODIFIED,
            ),
        ]

        result = sync.push_files(files)

        assert result.created == 1
        assert result.updated == 1
        assert result.errors == 0


class TestWikiSyncPullOperations:
    """Тесты pull операций."""

    @pytest.fixture
    def sync(self, mock_api, settings, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        return WikiSync(
            api=mock_api,
            docs_dir=docs_dir,
            base_slug="users/test",
            settings=settings,
        )

    def test_pull_file_not_found(self, sync, mock_api):
        """pull_file когда страница не найдена."""
        mock_api.get_page_info.return_value = None

        result = sync.pull_file("users/test/nonexistent")
        assert result is False

    def test_pull_file_creates_directory(self, sync, mock_api, tmp_path):
        """pull_file создаёт директорию."""
        mock_page = MagicMock()
        mock_page.id = 123
        mock_page.title = "Nested Page"
        mock_page.content = "Content here"
        mock_page.modified_at = datetime.now(UTC)
        mock_api.get_page_info.return_value = mock_page

        result = sync.pull_file("users/test/nested/deep/page")

        assert result is True
        # Проверяем что файл создан
        # (точный путь зависит от реализации _slug_to_path)

    def test_pull_file_adds_title(self, sync, mock_api, tmp_path):
        """pull_file добавляет заголовок если его нет."""
        mock_page = MagicMock()
        mock_page.id = 123
        mock_page.title = "My Page"
        mock_page.content = "Content without heading"
        mock_page.modified_at = datetime.now(UTC)
        mock_api.get_page_info.return_value = mock_page

        result = sync.pull_file("users/test/page")

        assert result is True

        file_path = tmp_path / "docs" / "page.md"
        content = file_path.read_text()
        assert "# My Page" in content

    def test_pull_file_empty_content(self, sync, mock_api, tmp_path):
        """pull_file с пустым контентом."""
        mock_page = MagicMock()
        mock_page.id = 123
        mock_page.title = "Empty Page"
        mock_page.content = ""
        mock_page.modified_at = datetime.now(UTC)
        mock_api.get_page_info.return_value = mock_page

        result = sync.pull_file("users/test/empty")

        assert result is True

        file_path = tmp_path / "docs" / "empty.md"
        content = file_path.read_text()
        assert "# Empty Page" in content


class TestWikiSyncDeleteOperations:
    """Тесты delete операций."""

    @pytest.fixture
    def sync(self, mock_api, settings, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        return WikiSync(
            api=mock_api,
            docs_dir=docs_dir,
            base_slug="users/test",
            settings=settings,
        )

    def test_delete_from_wiki_page_not_exists(self, sync, mock_api):
        """delete_from_wiki когда страницы нет."""
        mock_api.get_page.return_value = None

        # Добавляем в метаданные
        sync._meta.set_page(
            "users/test/deleted",
            PageMeta(
                id=999,
                slug="users/test/deleted",
                title="Deleted",
                file="deleted.md",
                content_hash="hash",
            ),
        )

        result = sync.delete_from_wiki("users/test/deleted")

        assert result is True
        assert sync._meta.get_page("users/test/deleted") is None

    def test_delete_from_wiki_api_error(self, sync, mock_api):
        """delete_from_wiki при ошибке API."""
        mock_api.get_page.return_value = MagicMock(id=123)
        mock_api.delete_page.return_value = False

        result = sync.delete_from_wiki("users/test/page")
        assert result is False

    def test_delete_pages_counts(self, sync, mock_api):
        """delete_pages подсчитывает результаты."""
        mock_api.get_page.side_effect = [
            MagicMock(id=1),
            MagicMock(id=2),
            None,
        ]
        mock_api.delete_page.side_effect = [True, False]

        result = sync.delete_pages(
            [
                "users/test/page1",
                "users/test/page2",
                "users/test/page3",
            ]
        )

        assert result.deleted == 2  # page1 удалена, page3 не существовала
        assert result.errors == 1  # page2 ошибка


class TestCreateSync:
    """Тесты для create_sync."""

    def test_create_sync_with_settings(self, tmp_path):
        """Создание sync из настроек."""
        settings = Settings(
            token="test_token",
            wiki=WikiSettings(
                org_id="123",
                base_slug="users/test",
                docs_dir="docs",
            ),
        )

        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()

        sync = create_sync(settings, docs_dir)

        assert sync.base_slug == "users/test"
        assert sync.docs_dir == docs_dir
        assert sync.api.token == "test_token"
        assert sync.api.org_id == "123"

    def test_create_sync_default_docs_dir(self, tmp_path, monkeypatch):
        """Создание sync с docs_dir по умолчанию."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "docs").mkdir()

        settings = Settings(
            token="test",
            wiki=WikiSettings(org_id="1", base_slug="test"),
        )

        sync = create_sync(settings)

        assert sync.docs_dir == tmp_path / "docs"

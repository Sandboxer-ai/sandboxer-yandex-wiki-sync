"""Тесты для Pydantic моделей."""

from datetime import UTC, datetime
from pathlib import Path

from sandboxer.wiki_sync.core.models import (
    DeleteResult,
    FileStatus,
    MetaStorage,
    PageMeta,
    SyncResult,
    SyncStatus,
    UploadResult,
)


class TestPageMeta:
    """Тесты для PageMeta."""

    def test_create(self):
        """Создание PageMeta."""
        meta = PageMeta(
            id=123,
            slug="users/test/page",
            title="Test Page",
            file="page.md",
            content_hash="abc123",
        )
        assert meta.id == 123
        assert meta.slug == "users/test/page"
        assert meta.title == "Test Page"
        assert meta.file == "page.md"
        assert meta.content_hash == "abc123"
        assert meta.last_push is None
        assert meta.last_pull is None

    def test_with_timestamps(self):
        """PageMeta с временными метками."""
        now = datetime.now(UTC)
        meta = PageMeta(
            id=1,
            slug="test",
            title="Test",
            file="test.md",
            content_hash="hash",
            last_push=now,
        )
        assert meta.last_push == now


class TestMetaStorage:
    """Тесты для MetaStorage."""

    def test_empty(self):
        """Пустое хранилище."""
        storage = MetaStorage()
        assert storage.version == 1
        assert storage.pages == {}

    def test_get_page_not_found(self):
        """Получение несуществующей страницы."""
        storage = MetaStorage()
        assert storage.get_page("nonexistent") is None

    def test_set_and_get_page(self):
        """Установка и получение страницы."""
        storage = MetaStorage()
        meta = PageMeta(
            id=1,
            slug="test",
            title="Test",
            file="test.md",
            content_hash="hash",
        )
        storage.set_page("test", meta)
        assert storage.get_page("test") == meta

    def test_remove_page(self):
        """Удаление страницы."""
        storage = MetaStorage()
        meta = PageMeta(
            id=1,
            slug="test",
            title="Test",
            file="test.md",
            content_hash="hash",
        )
        storage.set_page("test", meta)
        assert storage.remove_page("test") is True
        assert storage.get_page("test") is None

    def test_remove_nonexistent(self):
        """Удаление несуществующей страницы."""
        storage = MetaStorage()
        assert storage.remove_page("nonexistent") is False


class TestSyncResult:
    """Тесты для SyncResult."""

    def test_empty(self):
        """Пустой результат."""
        result = SyncResult()
        assert result.total_files == 0
        assert not result.has_changes
        assert not result.has_conflicts
        assert result.uploadable_files == []

    def test_has_changes(self):
        """Есть изменения."""
        result = SyncResult(modified=[FileStatus(slug="test", file_path=Path("test.md"), status=SyncStatus.MODIFIED)])
        assert result.has_changes

    def test_has_conflicts(self):
        """Есть конфликты."""
        result = SyncResult(conflict=[FileStatus(slug="test", file_path=Path("test.md"), status=SyncStatus.CONFLICT)])
        assert result.has_conflicts

    def test_uploadable_files(self):
        """Файлы для загрузки."""
        modified = FileStatus(slug="m", file_path=Path("m.md"), status=SyncStatus.MODIFIED)
        new = FileStatus(slug="n", file_path=Path("n.md"), status=SyncStatus.NEW)
        result = SyncResult(modified=[modified], new=[new])
        assert result.uploadable_files == [modified, new]


class TestUploadResult:
    """Тесты для UploadResult."""

    def test_success(self):
        """Успешная загрузка."""
        result = UploadResult(created=1, updated=2)
        assert result.success
        assert result.total_processed == 3

    def test_with_errors(self):
        """Загрузка с ошибками."""
        result = UploadResult(created=1, errors=1)
        assert not result.success
        assert result.total_processed == 2


class TestDeleteResult:
    """Тесты для DeleteResult."""

    def test_success(self):
        """Успешное удаление."""
        result = DeleteResult(deleted=5)
        assert result.success

    def test_with_errors(self):
        """Удаление с ошибками."""
        result = DeleteResult(deleted=3, errors=2)
        assert not result.success

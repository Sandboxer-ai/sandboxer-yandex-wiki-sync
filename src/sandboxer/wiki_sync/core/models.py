"""Pydantic модели для wiki-sync."""

from datetime import datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class SyncStatus(str, Enum):
    """Статус синхронизации файла."""

    SYNCED = "synced"  # Синхронизирован
    MODIFIED = "modified"  # Изменён локально
    NEW = "new"  # Новый локально
    CONFLICT = "conflict"  # Конфликт (изменён и там, и тут)
    REMOTE_MODIFIED = "remote_modified"  # Изменён в Wiki
    DELETED_LOCAL = "deleted_local"  # Удалён локально, есть в Wiki
    ERROR = "error"  # Ошибка чтения


class PageInfo(BaseModel):
    """Информация о странице Wiki."""

    id: int
    slug: str
    title: str
    page_type: str = "wysiwyg"


class PageContent(BaseModel):
    """Контент страницы Wiki."""

    id: int
    slug: str
    title: str
    content: str = ""
    modified_at: datetime | None = None


class PageMeta(BaseModel):
    """Метаданные страницы для локального хранения."""

    id: int
    slug: str
    title: str
    file: str  # Относительный путь к файлу
    content_hash: str
    last_push: datetime | None = None
    last_pull: datetime | None = None


class MetaStorage(BaseModel):
    """Хранилище метаданных (.wiki-meta.json)."""

    version: int = 1
    pages: dict[str, PageMeta] = Field(default_factory=dict)

    def get_page(self, slug: str) -> PageMeta | None:
        """Получить метаданные страницы по slug."""
        return self.pages.get(slug)

    def set_page(self, slug: str, meta: PageMeta) -> None:
        """Установить метаданные страницы."""
        self.pages[slug] = meta

    def remove_page(self, slug: str) -> bool:
        """Удалить метаданные страницы."""
        if slug in self.pages:
            del self.pages[slug]
            return True
        return False


class FileStatus(BaseModel):
    """Статус файла при синхронизации."""

    slug: str
    file_path: Path
    status: SyncStatus
    title: str = ""
    wiki_modified: datetime | None = None
    error_message: str | None = None


class SyncResult(BaseModel):
    """Результат синхронизации."""

    synced: list[FileStatus] = Field(default_factory=list)
    modified: list[FileStatus] = Field(default_factory=list)
    new: list[FileStatus] = Field(default_factory=list)
    conflict: list[FileStatus] = Field(default_factory=list)
    remote_modified: list[FileStatus] = Field(default_factory=list)
    deleted_local: list[FileStatus] = Field(default_factory=list)
    errors: list[FileStatus] = Field(default_factory=list)

    @property
    def total_files(self) -> int:
        """Общее количество файлов."""
        return len(self.synced) + len(self.modified) + len(self.new) + len(self.conflict) + len(self.remote_modified)

    @property
    def has_changes(self) -> bool:
        """Есть ли изменения для синхронизации."""
        return bool(self.modified or self.new or self.conflict or self.remote_modified or self.deleted_local)

    @property
    def has_conflicts(self) -> bool:
        """Есть ли конфликты."""
        return bool(self.conflict)

    @property
    def uploadable_files(self) -> list[FileStatus]:
        """Файлы, которые можно загрузить в Wiki."""
        return self.modified + self.new


class UploadResult(BaseModel):
    """Результат загрузки файлов."""

    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0

    @property
    def success(self) -> bool:
        """Все файлы загружены успешно."""
        return self.errors == 0

    @property
    def total_processed(self) -> int:
        """Общее количество обработанных файлов."""
        return self.created + self.updated + self.skipped + self.errors


class DeleteResult(BaseModel):
    """Результат удаления страниц."""

    deleted: int = 0
    errors: int = 0

    @property
    def success(self) -> bool:
        """Все страницы удалены успешно."""
        return self.errors == 0

"""Логика синхронизации с Yandex Wiki."""

import fnmatch
import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from ..utils.hashing import hash_content
from .api import WikiAPI
from .config import META_FILE_NAME, Settings
from .errors import FileError
from .models import (
    DeleteResult,
    FileStatus,
    MetaStorage,
    PageMeta,
    SyncResult,
    SyncStatus,
    UploadResult,
)

logger = logging.getLogger(__name__)


class WikiSync:
    """Синхронизатор локальных файлов с Yandex Wiki.

    Attributes:
        api: Клиент WikiAPI.
        docs_dir: Путь к директории с документами.
        base_slug: Базовый slug раздела Wiki.
        settings: Настройки синхронизации.
    """

    def __init__(
        self,
        api: WikiAPI,
        docs_dir: Path,
        base_slug: str,
        settings: Settings,
    ) -> None:
        """Инициализировать синхронизатор.

        Args:
            api: Клиент WikiAPI.
            docs_dir: Путь к директории с документами.
            base_slug: Базовый slug раздела Wiki.
            settings: Настройки приложения.
        """
        self.api = api
        self.docs_dir = Path(docs_dir)
        self.base_slug = base_slug.strip("/")
        self.settings = settings

        self._meta_file = self.docs_dir / META_FILE_NAME
        self._meta = self._load_meta()
        self._wiki_cache: dict[str, str | None] = {}

    def _load_meta(self) -> MetaStorage:
        """Загрузить метаданные из файла."""
        if not self._meta_file.exists():
            return MetaStorage()

        try:
            data = json.loads(self._meta_file.read_text(encoding="utf-8"))
            return MetaStorage.model_validate(data)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("Ошибка загрузки метаданных: %s", e)
            return MetaStorage()

    def save_meta(self) -> None:
        """Сохранить метаданные в файл."""
        try:
            self._meta_file.write_text(
                self._meta.model_dump_json(indent=2),
                encoding="utf-8",
            )
        except OSError as e:
            logger.warning("Ошибка сохранения метаданных: %s", e)

    def _path_to_slug(self, file_path: Path) -> str | None:
        """Преобразовать путь файла в slug Wiki.

        Args:
            file_path: Путь к .md файлу.

        Returns:
            Slug или None если файл вне docs_dir.
        """
        try:
            relative = file_path.relative_to(self.docs_dir)
        except ValueError:
            return None

        parts = list(relative.parts)
        parts[-1] = parts[-1].replace(".md", "")

        # index.md → родительская директория
        if parts[-1] == "index":
            parts = parts[:-1]

        if not parts:
            return self.base_slug

        return f"{self.base_slug}/{'/'.join(parts)}"

    def _slug_to_path(self, slug: str) -> Path:
        """Преобразовать slug Wiki в путь файла.

        Args:
            slug: Slug страницы Wiki.

        Returns:
            Путь к файлу.
        """
        if slug.startswith(self.base_slug):
            relative = slug[len(self.base_slug) :].lstrip("/")
        else:
            relative = slug

        if not relative:
            return self.docs_dir / "index.md"

        # Проверяем существующую папку с index.md
        index_path = self.docs_dir / relative / "index.md"
        if index_path.exists():
            return index_path

        # Иначе файл напрямую
        parts = relative.split("/")
        if len(parts) > 1:
            return self.docs_dir / "/".join(parts[:-1]) / f"{parts[-1]}.md"
        return self.docs_dir / f"{parts[0]}.md"

    def _is_ignored(self, file_path: Path) -> bool:
        """Проверить, должен ли файл игнорироваться.

        Args:
            file_path: Путь к файлу.

        Returns:
            True если файл должен игнорироваться.
        """
        for pattern in self.settings.sync.ignore:
            if fnmatch.fnmatch(file_path.name, pattern):
                return True
            if fnmatch.fnmatch(str(file_path), pattern):
                return True
        return False

    def _extract_title(self, content: str, default: str) -> str:
        """Извлечь заголовок # из контента.

        Args:
            content: Содержимое файла.
            default: Заголовок по умолчанию.

        Returns:
            Заголовок страницы.
        """
        if content:
            for line in content.strip().split("\n"):
                if line.startswith("# "):
                    return line[2:].strip()
        # Форматируем default: file-name → File Name
        return default.replace("-", " ").replace("_", " ").title()

    def _strip_title(self, content: str) -> str:
        """Убрать первый # заголовок из контента.

        Args:
            content: Содержимое файла.

        Returns:
            Контент без первого заголовка.
        """
        if not content:
            return ""

        lines = content.split("\n")
        i = 0

        # Пропускаем пустые строки
        while i < len(lines) and not lines[i].strip():
            i += 1

        # Если первая непустая строка — заголовок, убираем
        if i < len(lines) and lines[i].startswith("# "):
            i += 1
            # Пропускаем пустые строки после заголовка
            while i < len(lines) and not lines[i].strip():
                i += 1
            return "\n".join(lines[i:])

        return content

    def _read_file(self, file_path: Path) -> str | None:
        """Безопасно прочитать содержимое файла.

        Args:
            file_path: Путь к файлу.

        Returns:
            Содержимое или None при ошибке.
        """
        try:
            return file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            logger.warning("Ошибка чтения файла %s: %s", file_path, e)
            return None

    def _get_wiki_content(self, slug: str) -> str | None:
        """Получить контент из Wiki (с кешированием).

        Args:
            slug: Slug страницы.

        Returns:
            Контент или None если страница не существует.
        """
        if slug in self._wiki_cache:
            return self._wiki_cache[slug]

        page_content = self.api.get_page_info(slug)
        if not page_content:
            self._wiki_cache[slug] = None
            return None

        content = page_content.content
        self._wiki_cache[slug] = content
        return content

    def _content_differs(self, local_content: str, wiki_content: str | None) -> bool:
        """Проверить, отличается ли контент.

        Args:
            local_content: Локальный контент.
            wiki_content: Контент из Wiki.

        Returns:
            True если контент отличается.
        """
        if wiki_content is None:
            return True

        # Локальный контент без заголовка (так мы его отправляем в Wiki)
        local_stripped = self._strip_title(local_content) if self.settings.sync.strip_title else local_content

        return hash_content(local_stripped) != hash_content(wiki_content)

    def _utc_now(self) -> str:
        """Получить текущее время в UTC ISO формате."""
        return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    def get_status(self) -> SyncResult:
        """Получить статус синхронизации.

        Returns:
            SyncResult с информацией о всех файлах.
        """
        result = SyncResult()

        # Очищаем кеш
        self._wiki_cache = {}

        # Собираем локальные .md файлы
        local_files: dict[str, Path] = {}
        for file_path in self.docs_dir.rglob("*.md"):
            if self._is_ignored(file_path):
                continue

            slug = self._path_to_slug(file_path)
            if slug:
                local_files[slug] = file_path

        # Проверяем каждый файл
        for slug, file_path in local_files.items():
            local_content = self._read_file(file_path)

            if local_content is None:
                result.errors.append(
                    FileStatus(
                        slug=slug,
                        file_path=file_path,
                        status=SyncStatus.ERROR,
                        error_message="Ошибка чтения файла",
                    )
                )
                continue

            page_content = self.api.get_page_info(slug)

            if page_content is None:
                # Страницы нет в Wiki — новая
                result.new.append(
                    FileStatus(
                        slug=slug,
                        file_path=file_path,
                        status=SyncStatus.NEW,
                        title=self._extract_title(local_content, file_path.stem),
                    )
                )
            else:
                wiki_content = page_content.content
                wiki_modified = page_content.modified_at
                local_differs = self._content_differs(local_content, wiki_content)

                # Проверяем, изменена ли Wiki после нашего последнего push
                meta = self._meta.get_page(slug)
                last_push = meta.last_push if meta else None
                wiki_changed_after_push = False

                if last_push and wiki_modified:
                    wiki_changed_after_push = wiki_modified > last_push

                if local_differs and wiki_changed_after_push:
                    # Конфликт: изменено и там, и тут
                    result.conflict.append(
                        FileStatus(
                            slug=slug,
                            file_path=file_path,
                            status=SyncStatus.CONFLICT,
                            title=page_content.title,
                            wiki_modified=wiki_modified,
                        )
                    )
                elif local_differs:
                    # Локально изменено, Wiki не трогали
                    result.modified.append(
                        FileStatus(
                            slug=slug,
                            file_path=file_path,
                            status=SyncStatus.MODIFIED,
                            title=page_content.title,
                        )
                    )
                elif wiki_changed_after_push:
                    # Wiki изменена, локально нет
                    result.remote_modified.append(
                        FileStatus(
                            slug=slug,
                            file_path=file_path,
                            status=SyncStatus.REMOTE_MODIFIED,
                            title=page_content.title,
                            wiki_modified=wiki_modified,
                        )
                    )
                else:
                    # Всё синхронизировано
                    result.synced.append(
                        FileStatus(
                            slug=slug,
                            file_path=file_path,
                            status=SyncStatus.SYNCED,
                            title=page_content.title,
                        )
                    )
                    # Обновляем метаданные если нужно
                    if slug not in self._meta.pages:
                        self._meta.set_page(
                            slug,
                            PageMeta(
                                id=page_content.id,
                                slug=slug,
                                title=page_content.title,
                                file=str(file_path.relative_to(self.docs_dir)),
                                content_hash=hash_content(local_content),
                            ),
                        )

        # Удалены локально — есть в мета, но нет файла
        for slug, meta in list(self._meta.pages.items()):
            file_path = self.docs_dir / meta.file
            if not file_path.exists():
                result.deleted_local.append(
                    FileStatus(
                        slug=slug,
                        file_path=file_path,
                        status=SyncStatus.DELETED_LOCAL,
                        title=meta.title,
                    )
                )

        return result

    def push_file(self, file_status: FileStatus) -> bool:
        """Загрузить файл в Wiki.

        Args:
            file_status: Статус файла для загрузки.

        Returns:
            True если успешно.
        """
        local_content = self._read_file(file_status.file_path)
        if local_content is None:
            return False

        title = self._extract_title(local_content, file_status.file_path.stem)
        content_for_wiki = self._strip_title(local_content) if self.settings.sync.strip_title else local_content

        try:
            page = self.api.get_page(file_status.slug)

            if page:
                # Обновляем существующую
                self.api.update_page(page.id, title, content_for_wiki)
                page_id = page.id
            else:
                # Создаём новую
                new_page = self.api.create_page(file_status.slug, title, content_for_wiki)
                page_id = new_page.id

            # Обновляем метаданные
            self._meta.set_page(
                file_status.slug,
                PageMeta(
                    id=page_id,
                    slug=file_status.slug,
                    title=title,
                    file=str(file_status.file_path.relative_to(self.docs_dir)),
                    content_hash=hash_content(local_content),
                    last_push=datetime.now(UTC),
                ),
            )

            # Обновляем кеш
            self._wiki_cache[file_status.slug] = content_for_wiki

            return True

        except Exception as e:
            logger.error("Ошибка загрузки %s: %s", file_status.slug, e)
            return False

    def push_files(self, files: list[FileStatus]) -> UploadResult:
        """Загрузить несколько файлов в Wiki.

        Args:
            files: Список файлов для загрузки.

        Returns:
            UploadResult с результатами.
        """
        result = UploadResult()

        for file_status in files:
            # Проверяем существует ли страница
            page = self.api.get_page(file_status.slug)
            is_new = page is None

            if self.push_file(file_status):
                if is_new:
                    result.created += 1
                else:
                    result.updated += 1
            else:
                result.errors += 1

        self.save_meta()
        return result

    def pull_file(self, slug: str) -> bool:
        """Скачать страницу из Wiki в локальный файл.

        Args:
            slug: Slug страницы.

        Returns:
            True если успешно.
        """
        page_content = self.api.get_page_info(slug)
        if not page_content:
            return False

        content = page_content.content
        title = page_content.title

        # Добавляем заголовок если его нет в контенте
        if content and not content.strip().startswith("# "):
            content = f"# {title}\n\n{content}"
        elif not content:
            content = f"# {title}\n"

        file_path = self._slug_to_path(slug)

        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
        except OSError as e:
            raise FileError(str(file_path), "записи", str(e)) from e

        # Обновляем метаданные
        self._meta.set_page(
            slug,
            PageMeta(
                id=page_content.id,
                slug=slug,
                title=title,
                file=str(file_path.relative_to(self.docs_dir)),
                content_hash=hash_content(content),
                last_push=page_content.modified_at,  # Синхронизируем с временем Wiki
            ),
        )
        self.save_meta()

        return True

    def delete_from_wiki(self, slug: str) -> bool:
        """Удалить страницу из Wiki.

        Args:
            slug: Slug страницы.

        Returns:
            True если успешно.
        """
        page = self.api.get_page(slug)
        if not page:
            # Страницы нет — удаляем из метаданных
            self._meta.remove_page(slug)
            return True

        if self.api.delete_page(page.id):
            self._meta.remove_page(slug)
            return True

        return False

    def delete_pages(self, slugs: list[str]) -> DeleteResult:
        """Удалить несколько страниц из Wiki.

        Args:
            slugs: Список slug'ов для удаления.

        Returns:
            DeleteResult с результатами.
        """
        result = DeleteResult()

        for slug in slugs:
            if self.delete_from_wiki(slug):
                result.deleted += 1
            else:
                result.errors += 1

        self.save_meta()
        return result


def create_sync(settings: Settings, docs_dir: Path | None = None) -> WikiSync:
    """Создать экземпляр WikiSync из настроек.

    Args:
        settings: Настройки приложения.
        docs_dir: Путь к директории с документами (опционально).

    Returns:
        Экземпляр WikiSync.
    """
    if docs_dir is None:
        docs_dir = Path.cwd() / settings.wiki.docs_dir

    api = WikiAPI(
        token=settings.token,
        org_id=settings.wiki.org_id,
        api_url=settings.wiki.api_url,
        timeout=settings.sync.timeout,
    )

    return WikiSync(
        api=api,
        docs_dir=docs_dir,
        base_slug=settings.wiki.base_slug,
        settings=settings,
    )

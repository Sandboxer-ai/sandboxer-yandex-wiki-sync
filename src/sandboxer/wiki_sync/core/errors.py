"""Иерархия исключений wiki-sync."""

from typing import Any


class WikiSyncError(Exception):
    """Базовое исключение для всех ошибок wiki-sync.

    Attributes:
        message: Сообщение об ошибке.
        details: Дополнительные детали ошибки.
        exit_code: Код выхода для CLI.
    """

    exit_code: int = 1

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def __str__(self) -> str:
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({details_str})"
        return self.message


class ConfigError(WikiSyncError):
    """Ошибка конфигурации.

    Возникает когда:
    - Файл конфигурации не найден
    - Файл конфигурации невалиден
    - Отсутствуют обязательные параметры (например, токен)
    """

    exit_code: int = 2


class ApiError(WikiSyncError):
    """Ошибка API Yandex Wiki.

    Attributes:
        status_code: HTTP статус код ответа.
        error_code: Код ошибки из API.
    """

    exit_code: int = 3

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        details = details or {}
        if status_code:
            details["status_code"] = status_code
        if error_code:
            details["error_code"] = error_code
        super().__init__(message, details)
        self.status_code = status_code
        self.error_code = error_code


class AuthenticationError(ApiError):
    """Ошибка аутентификации.

    Возникает когда токен недействителен или истёк.
    """

    def __init__(self, message: str = "Ошибка аутентификации: проверьте токен") -> None:
        super().__init__(message, status_code=401)


class NotFoundError(ApiError):
    """Страница не найдена.

    Attributes:
        slug: Slug страницы, которая не найдена.
    """

    def __init__(self, slug: str) -> None:
        super().__init__(
            f"Страница не найдена: {slug}",
            status_code=404,
            details={"slug": slug},
        )
        self.slug = slug


class ConflictError(WikiSyncError):
    """Конфликт синхронизации.

    Возникает когда файл изменён и локально, и в Wiki.

    Attributes:
        slug: Slug страницы с конфликтом.
        local_file: Путь к локальному файлу.
        wiki_modified: Время последнего изменения в Wiki.
    """

    exit_code: int = 4

    def __init__(
        self,
        slug: str,
        local_file: str,
        wiki_modified: str | None = None,
    ) -> None:
        message = f"Конфликт: {local_file} изменён и локально, и в Wiki"
        details = {
            "slug": slug,
            "local_file": local_file,
        }
        if wiki_modified:
            details["wiki_modified"] = wiki_modified
        super().__init__(message, details)
        self.slug = slug
        self.local_file = local_file
        self.wiki_modified = wiki_modified


class FileError(WikiSyncError):
    """Ошибка работы с файлами.

    Возникает при проблемах чтения/записи файлов.
    """

    def __init__(self, path: str, operation: str, reason: str) -> None:
        message = f"Ошибка {operation} файла {path}: {reason}"
        super().__init__(message, details={"path": path, "operation": operation})
        self.path = path
        self.operation = operation


class ValidationError(WikiSyncError):
    """Ошибка валидации данных.

    Возникает когда данные не проходят валидацию Pydantic.
    """

    exit_code: int = 2

    def __init__(self, message: str, errors: list[dict[str, Any]] | None = None) -> None:
        details = {"errors": errors} if errors else {}
        super().__init__(message, details)
        self.errors = errors or []

"""Тесты для модуля ошибок."""

import pytest

from sandboxer.wiki_sync.core.errors import (
    ApiError,
    AuthenticationError,
    ConfigError,
    ConflictError,
    FileError,
    NotFoundError,
    ValidationError,
    WikiSyncError,
)


class TestWikiSyncError:
    """Тесты для базового исключения WikiSyncError."""

    def test_basic_error(self):
        """Базовая ошибка с сообщением."""
        error = WikiSyncError("Something went wrong")
        assert error.message == "Something went wrong"
        assert error.details == {}
        assert error.exit_code == 1
        assert str(error) == "Something went wrong"

    def test_error_with_details(self):
        """Ошибка с дополнительными деталями."""
        error = WikiSyncError("Error occurred", details={"file": "test.md", "line": 42})
        assert error.details == {"file": "test.md", "line": 42}
        assert "file=test.md" in str(error)
        assert "line=42" in str(error)

    def test_inherits_from_exception(self):
        """Наследуется от Exception."""
        error = WikiSyncError("Test")
        assert isinstance(error, Exception)


class TestConfigError:
    """Тесты для ConfigError."""

    def test_exit_code(self):
        """Правильный код выхода."""
        error = ConfigError("Config not found")
        assert error.exit_code == 2

    def test_inherits_from_base(self):
        """Наследуется от WikiSyncError."""
        error = ConfigError("Test")
        assert isinstance(error, WikiSyncError)


class TestApiError:
    """Тесты для ApiError."""

    def test_basic_api_error(self):
        """Базовая ошибка API."""
        error = ApiError("API request failed")
        assert error.message == "API request failed"
        assert error.status_code is None
        assert error.error_code is None
        assert error.exit_code == 3

    def test_with_status_code(self):
        """Ошибка с HTTP статус кодом."""
        error = ApiError("Server error", status_code=500)
        assert error.status_code == 500
        assert error.details["status_code"] == 500

    def test_with_error_code(self):
        """Ошибка с кодом ошибки API."""
        error = ApiError("Rate limited", error_code="RATE_LIMIT_EXCEEDED")
        assert error.error_code == "RATE_LIMIT_EXCEEDED"
        assert error.details["error_code"] == "RATE_LIMIT_EXCEEDED"

    def test_full_error(self):
        """Полная ошибка со всеми параметрами."""
        error = ApiError(
            "Not allowed",
            status_code=403,
            error_code="FORBIDDEN",
            details={"resource": "/pages/123"},
        )
        assert error.status_code == 403
        assert error.error_code == "FORBIDDEN"
        assert error.details["resource"] == "/pages/123"


class TestAuthenticationError:
    """Тесты для AuthenticationError."""

    def test_default_message(self):
        """Сообщение по умолчанию."""
        error = AuthenticationError()
        assert "аутентификации" in error.message
        assert error.status_code == 401

    def test_custom_message(self):
        """Кастомное сообщение."""
        error = AuthenticationError("Token expired")
        assert error.message == "Token expired"

    def test_inherits_from_api_error(self):
        """Наследуется от ApiError."""
        error = AuthenticationError()
        assert isinstance(error, ApiError)


class TestNotFoundError:
    """Тесты для NotFoundError."""

    def test_creates_with_slug(self):
        """Создаётся со slug."""
        error = NotFoundError("users/test/page")
        assert error.slug == "users/test/page"
        assert error.status_code == 404
        assert "users/test/page" in error.message
        assert error.details["slug"] == "users/test/page"

    def test_inherits_from_api_error(self):
        """Наследуется от ApiError."""
        error = NotFoundError("test")
        assert isinstance(error, ApiError)


class TestConflictError:
    """Тесты для ConflictError."""

    def test_basic_conflict(self):
        """Базовый конфликт."""
        error = ConflictError(
            slug="users/test/page",
            local_file="docs/page.md",
        )
        assert error.slug == "users/test/page"
        assert error.local_file == "docs/page.md"
        assert error.wiki_modified is None
        assert error.exit_code == 4

    def test_with_wiki_modified(self):
        """Конфликт с временем модификации Wiki."""
        error = ConflictError(
            slug="users/test/page",
            local_file="docs/page.md",
            wiki_modified="2025-12-28T10:00:00Z",
        )
        assert error.wiki_modified == "2025-12-28T10:00:00Z"
        assert error.details["wiki_modified"] == "2025-12-28T10:00:00Z"

    def test_message_contains_info(self):
        """Сообщение содержит информацию о конфликте."""
        error = ConflictError(
            slug="users/test/page",
            local_file="docs/page.md",
        )
        assert "docs/page.md" in error.message
        assert "конфликт" in error.message.lower()


class TestFileError:
    """Тесты для FileError."""

    def test_creates_with_details(self):
        """Создаётся с деталями."""
        error = FileError(
            path="/path/to/file.md",
            operation="чтения",
            reason="Permission denied",
        )
        assert error.path == "/path/to/file.md"
        assert error.operation == "чтения"
        assert "/path/to/file.md" in error.message
        assert "чтения" in error.message
        assert "Permission denied" in error.message

    def test_details_stored(self):
        """Детали сохраняются."""
        error = FileError(
            path="test.md",
            operation="записи",
            reason="Disk full",
        )
        assert error.details["path"] == "test.md"
        assert error.details["operation"] == "записи"


class TestValidationError:
    """Тесты для ValidationError."""

    def test_exit_code(self):
        """Правильный код выхода."""
        error = ValidationError("Invalid data")
        assert error.exit_code == 2

    def test_with_errors_list(self):
        """С списком ошибок валидации."""
        errors_list = [
            {"loc": ["wiki", "org_id"], "msg": "field required"},
            {"loc": ["token"], "msg": "field required"},
        ]
        error = ValidationError("Validation failed", errors=errors_list)
        assert error.errors == errors_list
        assert error.details["errors"] == errors_list

    def test_empty_errors(self):
        """Без списка ошибок."""
        error = ValidationError("Invalid")
        assert error.errors == []


class TestExceptionHierarchy:
    """Тесты иерархии исключений."""

    def test_catch_all_with_base(self):
        """Можно поймать все ошибки через базовый класс."""
        errors = [
            WikiSyncError("base"),
            ConfigError("config"),
            ApiError("api"),
            AuthenticationError(),
            NotFoundError("slug"),
            ConflictError("slug", "file"),
            FileError("path", "op", "reason"),
            ValidationError("validation"),
        ]

        for error in errors:
            try:
                raise error
            except WikiSyncError as e:
                assert e is error

    def test_specific_catch(self):
        """Можно поймать специфичные ошибки."""
        with pytest.raises(AuthenticationError):
            raise AuthenticationError()

        with pytest.raises(NotFoundError):
            raise NotFoundError("test")

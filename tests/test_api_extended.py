"""Расширенные тесты для WikiAPI — покрытие error paths."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from sandboxer.wiki_sync.core.api import WikiAPI
from sandboxer.wiki_sync.core.errors import ApiError, AuthenticationError, NotFoundError


class TestWikiAPIErrors:
    """Тесты обработки ошибок в WikiAPI."""

    @pytest.fixture
    def api(self):
        """Создать экземпляр API."""
        return WikiAPI(
            token="test_token",
            org_id="123456",
            api_url="https://api.wiki.test/v1",
        )

    @patch("sandboxer.wiki_sync.core.api.requests.Session.request")
    def test_request_timeout(self, mock_request, api):
        """Таймаут запроса."""
        mock_request.side_effect = requests.exceptions.Timeout("Connection timed out")

        with pytest.raises(ApiError) as exc_info:
            api.get_page("test")

        assert "Таймаут" in exc_info.value.message

    @patch("sandboxer.wiki_sync.core.api.requests.Session.request")
    def test_request_connection_error(self, mock_request, api):
        """Ошибка соединения."""
        mock_request.side_effect = requests.exceptions.ConnectionError("Connection refused")

        with pytest.raises(ApiError) as exc_info:
            api.get_page("test")

        assert "соединения" in exc_info.value.message

    @patch("sandboxer.wiki_sync.core.api.requests.Session.request")
    def test_request_generic_error(self, mock_request, api):
        """Общая ошибка запроса."""
        mock_request.side_effect = requests.exceptions.RequestException("Unknown error")

        with pytest.raises(ApiError) as exc_info:
            api.get_page("test")

        assert "Ошибка запроса" in exc_info.value.message

    @patch("sandboxer.wiki_sync.core.api.requests.Session.request")
    def test_forbidden_error(self, mock_request, api):
        """Доступ запрещён (403)."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_request.return_value = mock_response

        with pytest.raises(ApiError) as exc_info:
            api.get_page("test")

        assert exc_info.value.status_code == 403 or "запрещён" in exc_info.value.message

    @patch("sandboxer.wiki_sync.core.api.requests.Session.request")
    def test_get_page_api_error_in_body(self, mock_request, api):
        """Ошибка API в теле ответа (не NOT_FOUND)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "error_code": "INTERNAL_ERROR",
            "message": "Something went wrong",
            "debug_message": "Database connection failed",
        }
        mock_request.return_value = mock_response

        with pytest.raises(ApiError) as exc_info:
            api.get_page("test")

        assert exc_info.value.error_code == "INTERNAL_ERROR"

    @patch("sandboxer.wiki_sync.core.api.requests.Session.request")
    def test_get_page_non_200_error(self, mock_request, api):
        """Ошибка с HTTP статусом не 200/404."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {
            "message": "Internal server error",
            "error_code": "SERVER_ERROR",
        }
        mock_request.return_value = mock_response

        with pytest.raises(ApiError) as exc_info:
            api.get_page("test")

        assert exc_info.value.status_code == 500


class TestWikiAPIGetPageContent:
    """Тесты для get_page_content."""

    @pytest.fixture
    def api(self):
        return WikiAPI(token="test", org_id="123")

    @patch("sandboxer.wiki_sync.core.api.requests.Session.request")
    def test_get_page_content_success(self, mock_request, api):
        """Успешное получение контента страницы."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 123,
            "slug": "users/test/page",
            "title": "Test Page",
            "content": "Page content here",
            "attributes": {
                "modified_at": "2025-12-28T15:24:07.430Z",
            },
        }
        mock_request.return_value = mock_response

        result = api.get_page_content(123)

        assert result is not None
        assert result.id == 123
        assert result.content == "Page content here"
        assert result.modified_at is not None

    @patch("sandboxer.wiki_sync.core.api.requests.Session.request")
    def test_get_page_content_not_found(self, mock_request, api):
        """Страница не найдена."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_request.return_value = mock_response

        result = api.get_page_content(999)
        assert result is None

    @patch("sandboxer.wiki_sync.core.api.requests.Session.request")
    def test_get_page_content_non_200(self, mock_request, api):
        """Ошибка при получении контента."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_request.return_value = mock_response

        result = api.get_page_content(123)
        assert result is None

    @patch("sandboxer.wiki_sync.core.api.requests.Session.request")
    def test_get_page_content_invalid_date(self, mock_request, api):
        """Некорректная дата модификации."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 123,
            "slug": "test",
            "title": "Test",
            "content": "Content",
            "attributes": {
                "modified_at": "invalid-date",
            },
        }
        mock_request.return_value = mock_response

        result = api.get_page_content(123)
        assert result is not None
        assert result.modified_at is None

    @patch("sandboxer.wiki_sync.core.api.requests.Session.request")
    def test_get_page_content_no_attributes(self, mock_request, api):
        """Ответ без атрибутов."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 123,
            "slug": "test",
            "title": "Test",
            "content": "Content",
        }
        mock_request.return_value = mock_response

        result = api.get_page_content(123)
        assert result is not None
        assert result.modified_at is None


class TestWikiAPIPageInfo:
    """Тесты для get_page_info."""

    @pytest.fixture
    def api(self):
        return WikiAPI(token="test", org_id="123")

    @patch.object(WikiAPI, "get_page")
    @patch.object(WikiAPI, "get_page_content")
    def test_get_page_info_success(self, mock_content, mock_page, api):
        """Успешное получение полной информации."""
        mock_page.return_value = MagicMock(id=123)
        mock_content.return_value = MagicMock(
            id=123,
            slug="test",
            title="Test",
            content="Content",
        )

        result = api.get_page_info("test")

        assert result is not None
        mock_page.assert_called_once_with("test")
        mock_content.assert_called_once_with(123)

    @patch.object(WikiAPI, "get_page")
    def test_get_page_info_page_not_found(self, mock_page, api):
        """Страница не найдена."""
        mock_page.return_value = None

        result = api.get_page_info("nonexistent")
        assert result is None


class TestWikiAPICreatePage:
    """Тесты для create_page."""

    @pytest.fixture
    def api(self):
        return WikiAPI(token="test", org_id="123")

    @patch("sandboxer.wiki_sync.core.api.requests.Session.request")
    def test_create_page_error(self, mock_request, api):
        """Ошибка создания страницы."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "message": "Invalid slug",
            "error_code": "INVALID_SLUG",
        }
        mock_request.return_value = mock_response

        with pytest.raises(ApiError) as exc_info:
            api.create_page("invalid slug", "Title", "Content")

        assert "Invalid slug" in exc_info.value.message


class TestWikiAPIUpdatePage:
    """Тесты для update_page."""

    @pytest.fixture
    def api(self):
        return WikiAPI(token="test", org_id="123")

    @patch("sandboxer.wiki_sync.core.api.requests.Session.request")
    def test_update_page_not_found(self, mock_request, api):
        """Обновление несуществующей страницы."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_request.return_value = mock_response

        with pytest.raises(NotFoundError):
            api.update_page(999, "Title", "Content")

    @patch("sandboxer.wiki_sync.core.api.requests.Session.request")
    def test_update_page_error(self, mock_request, api):
        """Ошибка обновления страницы."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {
            "message": "Server error",
            "error_code": "INTERNAL_ERROR",
        }
        mock_request.return_value = mock_response

        with pytest.raises(ApiError):
            api.update_page(123, "Title", "Content")


class TestWikiAPIDeletePage:
    """Тесты для delete_page."""

    @pytest.fixture
    def api(self):
        return WikiAPI(token="test", org_id="123")

    @patch("sandboxer.wiki_sync.core.api.requests.Session.request")
    def test_delete_page_200(self, mock_request, api):
        """Успешное удаление (200)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        result = api.delete_page(123)
        assert result is True

    @patch("sandboxer.wiki_sync.core.api.requests.Session.request")
    def test_delete_page_error(self, mock_request, api):
        """Ошибка удаления страницы."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {
            "message": "Cannot delete",
        }
        mock_request.return_value = mock_response

        with pytest.raises(ApiError):
            api.delete_page(123)


class TestWikiAPICheckConnection:
    """Тесты для check_connection."""

    @pytest.fixture
    def api(self):
        return WikiAPI(token="test", org_id="123")

    @patch.object(WikiAPI, "get_page")
    def test_check_connection_success(self, mock_get_page, api):
        """Успешная проверка соединения."""
        mock_get_page.return_value = None  # Страница не найдена — OK

        result = api.check_connection()
        assert result is True

    @patch.object(WikiAPI, "get_page")
    def test_check_connection_auth_error(self, mock_get_page, api):
        """Ошибка авторизации при проверке."""
        mock_get_page.side_effect = AuthenticationError()

        with pytest.raises(AuthenticationError):
            api.check_connection()

    @patch.object(WikiAPI, "get_page")
    def test_check_connection_api_error(self, mock_get_page, api):
        """Ошибка API при проверке."""
        mock_get_page.side_effect = ApiError("Connection failed")

        with pytest.raises(ApiError):
            api.check_connection()

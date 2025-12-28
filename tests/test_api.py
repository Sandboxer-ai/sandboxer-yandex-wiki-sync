"""Тесты для WikiAPI клиента."""

from unittest.mock import MagicMock, patch

import pytest

from sandboxer.wiki_sync.core.api import WikiAPI
from sandboxer.wiki_sync.core.errors import AuthenticationError


class TestWikiAPI:
    """Тесты для WikiAPI."""

    @pytest.fixture
    def api(self):
        """Создать экземпляр API."""
        return WikiAPI(
            token="test_token",
            org_id="123456",
            api_url="https://api.wiki.test/v1",
        )

    def test_init(self, api):
        """Инициализация клиента."""
        assert api.token == "test_token"
        assert api.org_id == "123456"
        assert api.api_url == "https://api.wiki.test/v1"
        assert api.timeout == 60

    def test_init_strips_trailing_slash(self):
        """URL без завершающего слэша."""
        api = WikiAPI(
            token="test",
            org_id="123",
            api_url="https://api.wiki.test/v1/",
        )
        assert api.api_url == "https://api.wiki.test/v1"

    @patch("sandboxer.wiki_sync.core.api.requests.Session.request")
    def test_get_page_success(self, mock_request, api):
        """Успешное получение страницы."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 123,
            "slug": "users/test/page",
            "title": "Test Page",
            "page_type": "wysiwyg",
        }
        mock_request.return_value = mock_response

        page = api.get_page("users/test/page")

        assert page is not None
        assert page.id == 123
        assert page.slug == "users/test/page"
        assert page.title == "Test Page"

    @patch("sandboxer.wiki_sync.core.api.requests.Session.request")
    def test_get_page_not_found(self, mock_request, api):
        """Страница не найдена."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_request.return_value = mock_response

        page = api.get_page("nonexistent")
        assert page is None

    @patch("sandboxer.wiki_sync.core.api.requests.Session.request")
    def test_get_page_not_found_in_body(self, mock_request, api):
        """NOT_FOUND в теле ответа."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "error_code": "NOT_FOUND",
            "message": "Page not found",
        }
        mock_request.return_value = mock_response

        page = api.get_page("nonexistent")
        assert page is None

    @patch("sandboxer.wiki_sync.core.api.requests.Session.request")
    def test_authentication_error(self, mock_request, api):
        """Ошибка аутентификации."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_request.return_value = mock_response

        with pytest.raises(AuthenticationError):
            api.get_page("test")

    @patch("sandboxer.wiki_sync.core.api.requests.Session.request")
    def test_create_page(self, mock_request, api):
        """Создание страницы."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "id": 456,
            "slug": "users/test/new",
            "title": "New Page",
            "page_type": "wysiwyg",
        }
        mock_request.return_value = mock_response

        page = api.create_page("users/test/new", "New Page", "Content")

        assert page.id == 456
        assert page.title == "New Page"
        mock_request.assert_called_once()

    @patch("sandboxer.wiki_sync.core.api.requests.Session.request")
    def test_update_page(self, mock_request, api):
        """Обновление страницы."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 123,
            "slug": "users/test/page",
            "title": "Updated Title",
            "page_type": "wysiwyg",
        }
        mock_request.return_value = mock_response

        page = api.update_page(123, "Updated Title", "New content")

        assert page.title == "Updated Title"

    @patch("sandboxer.wiki_sync.core.api.requests.Session.request")
    def test_delete_page_success(self, mock_request, api):
        """Успешное удаление страницы."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_request.return_value = mock_response

        result = api.delete_page(123)
        assert result is True

    @patch("sandboxer.wiki_sync.core.api.requests.Session.request")
    def test_delete_page_not_found(self, mock_request, api):
        """Удаление несуществующей страницы."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_request.return_value = mock_response

        result = api.delete_page(999)
        assert result is False

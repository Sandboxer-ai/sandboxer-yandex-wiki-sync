"""HTTP клиент для Yandex Wiki API."""

import logging
from datetime import datetime
from typing import Any

import requests

from .errors import ApiError, AuthenticationError, NotFoundError
from .models import PageContent, PageInfo

logger = logging.getLogger(__name__)


class WikiAPI:
    """Клиент для работы с Yandex Wiki API.

    Attributes:
        api_url: Базовый URL API.
        token: OAuth токен.
        org_id: ID организации.
        timeout: Таймаут запросов в секундах.
    """

    def __init__(
        self,
        token: str,
        org_id: str,
        api_url: str = "https://api.wiki.yandex.net/v1",
        timeout: int = 60,
    ) -> None:
        """Инициализировать клиент.

        Args:
            token: OAuth токен Yandex.
            org_id: ID организации.
            api_url: Базовый URL API.
            timeout: Таймаут запросов в секундах.
        """
        self.api_url = api_url.rstrip("/")
        self.token = token
        self.org_id = org_id
        self.timeout = timeout

        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"OAuth {token}",
                "X-Org-Id": org_id,
                "Content-Type": "application/json",
            }
        )

    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> requests.Response:
        """Выполнить HTTP запрос к API.

        Args:
            method: HTTP метод (GET, POST, DELETE).
            endpoint: Путь к эндпоинту (например, /pages).
            params: Query параметры.
            json: JSON тело запроса.

        Returns:
            Объект Response.

        Raises:
            AuthenticationError: При ошибке аутентификации.
            ApiError: При других ошибках API.
        """
        url = f"{self.api_url}{endpoint}"
        logger.debug("API %s %s params=%s", method, url, params)

        try:
            response = self._session.request(
                method=method,
                url=url,
                params=params,
                json=json,
                timeout=self.timeout,
            )
        except requests.exceptions.Timeout as e:
            raise ApiError(f"Таймаут запроса к {url}") from e
        except requests.exceptions.ConnectionError as e:
            raise ApiError(f"Ошибка соединения с {url}") from e
        except requests.exceptions.RequestException as e:
            raise ApiError(f"Ошибка запроса: {e}") from e

        # Обработка ошибок
        if response.status_code == 401:
            raise AuthenticationError()
        if response.status_code == 403:
            raise ApiError("Доступ запрещён", status_code=403)

        return response

    def get_page(self, slug: str) -> PageInfo | None:
        """Получить информацию о странице по slug.

        Args:
            slug: Slug страницы (например, users/username/page).

        Returns:
            PageInfo или None если страница не найдена.
        """
        response = self._request("GET", "/pages", params={"slug": slug})

        if response.status_code == 404:
            return None

        if response.status_code != 200:
            data = response.json()
            raise ApiError(
                data.get("message", "Неизвестная ошибка"),
                status_code=response.status_code,
                error_code=data.get("error_code"),
            )

        data = response.json()

        # Если API вернул ошибку в теле ответа
        if "error_code" in data:
            if data["error_code"] == "NOT_FOUND":
                return None
            raise ApiError(
                data.get("debug_message", data.get("message", "Ошибка API")),
                error_code=data["error_code"],
            )

        return PageInfo(
            id=data["id"],
            slug=data["slug"],
            title=data["title"],
            page_type=data.get("page_type", "wysiwyg"),
        )

    def get_page_content(self, page_id: int) -> PageContent | None:
        """Получить контент страницы по ID.

        Args:
            page_id: ID страницы.

        Returns:
            PageContent или None.
        """
        response = self._request(
            "GET",
            f"/pages/{page_id}",
            params={"fields": "content,attributes"},
        )

        if response.status_code == 404:
            return None

        if response.status_code != 200:
            return None

        data = response.json()

        # Парсим время модификации
        modified_at = None
        if "attributes" in data and "modified_at" in data["attributes"]:
            try:
                modified_str = data["attributes"]["modified_at"]
                # Формат: 2025-12-28T15:24:07.430Z
                modified_at = datetime.fromisoformat(modified_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        return PageContent(
            id=data["id"],
            slug=data["slug"],
            title=data["title"],
            content=data.get("content", ""),
            modified_at=modified_at,
        )

    def get_page_info(self, slug: str) -> PageContent | None:
        """Получить полную информацию о странице (включая контент и время модификации).

        Args:
            slug: Slug страницы.

        Returns:
            PageContent или None.
        """
        page = self.get_page(slug)
        if not page:
            return None

        return self.get_page_content(page.id)

    def create_page(self, slug: str, title: str, content: str) -> PageInfo:
        """Создать новую страницу.

        Args:
            slug: Slug новой страницы.
            title: Заголовок страницы.
            content: Содержимое страницы (Markdown).

        Returns:
            PageInfo созданной страницы.

        Raises:
            ApiError: При ошибке создания.
        """
        response = self._request(
            "POST",
            "/pages",
            json={
                "slug": slug,
                "title": title,
                "content": content,
                "page_type": "wysiwyg",
            },
        )

        if response.status_code not in (200, 201):
            data = response.json()
            raise ApiError(
                data.get("message", f"Ошибка создания страницы {slug}"),
                status_code=response.status_code,
                error_code=data.get("error_code"),
            )

        data = response.json()
        return PageInfo(
            id=data["id"],
            slug=data["slug"],
            title=data["title"],
            page_type=data.get("page_type", "wysiwyg"),
        )

    def update_page(self, page_id: int, title: str, content: str) -> PageInfo:
        """Обновить существующую страницу.

        Args:
            page_id: ID страницы.
            title: Новый заголовок.
            content: Новое содержимое.

        Returns:
            PageInfo обновлённой страницы.

        Raises:
            NotFoundError: Если страница не найдена.
            ApiError: При других ошибках.
        """
        response = self._request(
            "POST",
            f"/pages/{page_id}",
            json={
                "title": title,
                "content": content,
            },
        )

        if response.status_code == 404:
            raise NotFoundError(f"page_id={page_id}")

        if response.status_code not in (200, 201):
            data = response.json()
            raise ApiError(
                data.get("message", f"Ошибка обновления страницы {page_id}"),
                status_code=response.status_code,
                error_code=data.get("error_code"),
            )

        data = response.json()
        return PageInfo(
            id=data["id"],
            slug=data["slug"],
            title=data["title"],
            page_type=data.get("page_type", "wysiwyg"),
        )

    def delete_page(self, page_id: int) -> bool:
        """Удалить страницу.

        Args:
            page_id: ID страницы.

        Returns:
            True если успешно, False если страница не найдена.

        Raises:
            ApiError: При других ошибках.
        """
        response = self._request("DELETE", f"/pages/{page_id}")

        if response.status_code in (200, 204):
            return True
        if response.status_code == 404:
            return False

        data = response.json()
        raise ApiError(
            data.get("message", f"Ошибка удаления страницы {page_id}"),
            status_code=response.status_code,
            error_code=data.get("error_code"),
        )

    def check_connection(self) -> bool:
        """Проверить соединение с API.

        Returns:
            True если соединение работает.

        Raises:
            AuthenticationError: При неверном токене.
            ApiError: При других ошибках.
        """
        # Пробуем получить несуществующую страницу — это проверит авторизацию
        try:
            self.get_page("__test_connection__")
            return True
        except NotFoundError:
            # Страница не найдена — это нормально, авторизация работает
            return True
        except AuthenticationError:
            raise
        except ApiError:
            raise

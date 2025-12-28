"""Конфигурация wiki-sync с использованием pydantic-settings."""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Константы
DEFAULT_API_URL = "https://api.wiki.yandex.net/v1"
DEFAULT_TIMEOUT = 60
CONFIG_FILE_NAME = ".wiki-sync.toml"
META_FILE_NAME = ".wiki-meta.json"
GLOBAL_CONFIG_DIR = Path.home() / ".config" / "wiki-sync"


class WikiSettings(BaseModel):
    """Настройки Wiki API."""

    org_id: str = Field(description="ID организации в Yandex Wiki")
    base_slug: str = Field(description="Базовый slug раздела Wiki")
    docs_dir: str = Field(default="docs", description="Папка с документами")
    api_url: str = Field(default=DEFAULT_API_URL, description="URL API")

    @field_validator("base_slug")
    @classmethod
    def validate_base_slug(cls, v: str) -> str:
        """Убрать начальный и конечный слэш."""
        return v.strip("/")

    @field_validator("docs_dir")
    @classmethod
    def validate_docs_dir(cls, v: str) -> str:
        """Убрать начальный и конечный слэш."""
        return v.strip("/")


class SyncSettings(BaseModel):
    """Настройки синхронизации."""

    ignore: list[str] = Field(default_factory=list, description="Игнорируемые паттерны")
    strip_title: bool = Field(default=True, description="Убирать # заголовок при push")
    timeout: int = Field(default=DEFAULT_TIMEOUT, description="Таймаут запросов (сек)")


class Settings(BaseSettings):
    """Главные настройки приложения.

    Порядок загрузки (от низшего приоритета к высшему):
    1. Значения по умолчанию
    2. Глобальный конфиг ~/.config/wiki-sync/config.toml
    3. Локальный конфиг .wiki-sync.toml
    4. .env файл
    5. Переменные окружения WIKI_SYNC_*
    6. CLI аргументы (передаются при создании экземпляра)
    """

    model_config = SettingsConfigDict(
        env_prefix="WIKI_SYNC_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # pydantic-settings 2.12+: частичное обновление вложенных моделей
        nested_model_default_partial_update=True,
    )

    token: str = Field(description="OAuth токен Yandex")
    wiki: WikiSettings
    sync: SyncSettings = Field(default_factory=SyncSettings)

    @classmethod
    def from_file(cls, config_path: Path | None = None, **overrides: Any) -> "Settings":
        """Загрузить настройки из файла.

        Args:
            config_path: Путь к файлу конфигурации.
            **overrides: Переопределения параметров.

        Returns:
            Экземпляр Settings.
        """
        import tomllib

        # Собираем данные из файлов
        data: dict[str, Any] = {}

        # 1. Глобальный конфиг
        global_config = GLOBAL_CONFIG_DIR / "config.toml"
        if global_config.exists():
            with global_config.open("rb") as f:
                data.update(tomllib.load(f))

        # 2. Локальный конфиг
        local_config = config_path or Path.cwd() / CONFIG_FILE_NAME
        if local_config.exists():
            with local_config.open("rb") as f:
                data.update(tomllib.load(f))

        # 3. Применяем переопределения
        data.update(overrides)

        return cls(**data)


def find_config_file(start_path: Path | None = None) -> Path | None:
    """Найти файл конфигурации в текущей или родительских директориях.

    Args:
        start_path: Начальная директория для поиска.

    Returns:
        Путь к файлу конфигурации или None.
    """
    current = start_path or Path.cwd()

    # Ищем вверх по дереву каталогов
    for parent in [current, *current.parents]:
        config_file = parent / CONFIG_FILE_NAME
        if config_file.exists():
            return config_file

    return None


def get_docs_dir(settings: Settings, base_path: Path | None = None) -> Path:
    """Получить путь к директории с документами.

    Args:
        settings: Настройки приложения.
        base_path: Базовый путь (по умолчанию — текущая директория).

    Returns:
        Абсолютный путь к директории с документами.
    """
    base = base_path or Path.cwd()
    docs_path = base / settings.wiki.docs_dir

    # Создаём директорию если не существует
    docs_path.mkdir(parents=True, exist_ok=True)

    return docs_path


def get_meta_file_path(docs_dir: Path) -> Path:
    """Получить путь к файлу метаданных.

    Args:
        docs_dir: Директория с документами.

    Returns:
        Путь к файлу метаданных.
    """
    return docs_dir / META_FILE_NAME


def create_default_config(
    org_id: str,
    base_slug: str,
    docs_dir: str = "docs",
    output_path: Path | None = None,
) -> Path:
    """Создать файл конфигурации по умолчанию.

    Args:
        org_id: ID организации.
        base_slug: Базовый slug раздела.
        docs_dir: Папка с документами.
        output_path: Путь для сохранения (по умолчанию — .wiki-sync.toml).

    Returns:
        Путь к созданному файлу.
    """
    config_content = f'''[wiki]
org_id = "{org_id}"
base_slug = "{base_slug}"
docs_dir = "{docs_dir}"

[sync]
ignore = ["*.draft.md", "_*"]
strip_title = true
timeout = 60
'''

    output = output_path or Path.cwd() / CONFIG_FILE_NAME
    output.write_text(config_content)

    return output

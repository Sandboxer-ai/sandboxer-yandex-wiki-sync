"""Тесты для модуля конфигурации."""

from sandboxer.wiki_sync.core.config import (
    CONFIG_FILE_NAME,
    Settings,
    SyncSettings,
    WikiSettings,
    create_default_config,
    find_config_file,
    get_docs_dir,
    get_meta_file_path,
)


class TestWikiSettings:
    """Тесты для WikiSettings."""

    def test_create_minimal(self):
        """Создание с минимальными параметрами."""
        settings = WikiSettings(org_id="123", base_slug="users/test")
        assert settings.org_id == "123"
        assert settings.base_slug == "users/test"
        assert settings.docs_dir == "docs"

    def test_base_slug_strips_slashes(self):
        """base_slug очищается от слешей."""
        settings = WikiSettings(org_id="123", base_slug="/users/test/")
        assert settings.base_slug == "users/test"

    def test_docs_dir_strips_slashes(self):
        """docs_dir очищается от слешей."""
        settings = WikiSettings(org_id="123", base_slug="test", docs_dir="/docs/")
        assert settings.docs_dir == "docs"


class TestSyncSettings:
    """Тесты для SyncSettings."""

    def test_defaults(self):
        """Значения по умолчанию."""
        settings = SyncSettings()
        assert settings.ignore == []
        assert settings.strip_title is True
        assert settings.timeout == 60

    def test_custom_values(self):
        """Кастомные значения."""
        settings = SyncSettings(
            ignore=["*.draft.md"],
            strip_title=False,
            timeout=30,
        )
        assert settings.ignore == ["*.draft.md"]
        assert settings.strip_title is False
        assert settings.timeout == 30


class TestSettings:
    """Тесты для Settings."""

    def test_create_full(self):
        """Создание полной конфигурации."""
        settings = Settings(
            token="test_token",
            wiki=WikiSettings(org_id="123", base_slug="users/test"),
            sync=SyncSettings(ignore=["*.tmp"]),
        )
        assert settings.token == "test_token"
        assert settings.wiki.org_id == "123"
        assert settings.sync.ignore == ["*.tmp"]

    def test_from_file_local_config(self, tmp_path):
        """Загрузка из локального файла."""
        config_content = """
[wiki]
org_id = "456"
base_slug = "projects/docs"
docs_dir = "documentation"

[sync]
ignore = ["*.bak"]
strip_title = false
timeout = 120
"""
        config_file = tmp_path / CONFIG_FILE_NAME
        config_file.write_text(config_content)

        settings = Settings.from_file(config_file, token="my_token")

        assert settings.token == "my_token"
        assert settings.wiki.org_id == "456"
        assert settings.wiki.base_slug == "projects/docs"
        assert settings.wiki.docs_dir == "documentation"
        assert settings.sync.ignore == ["*.bak"]
        assert settings.sync.strip_title is False
        assert settings.sync.timeout == 120

    def test_from_file_with_overrides(self, tmp_path):
        """Переопределение параметров."""
        config_content = """
[wiki]
org_id = "123"
base_slug = "test"
"""
        config_file = tmp_path / CONFIG_FILE_NAME
        config_file.write_text(config_content)

        settings = Settings.from_file(config_file, token="override_token")

        assert settings.token == "override_token"


class TestFindConfigFile:
    """Тесты для find_config_file."""

    def test_find_in_current_dir(self, tmp_path):
        """Находит конфиг в текущей директории."""
        config_file = tmp_path / CONFIG_FILE_NAME
        config_file.write_text("[wiki]\norg_id = '1'")

        found = find_config_file(tmp_path)
        assert found == config_file

    def test_find_in_parent_dir(self, tmp_path):
        """Находит конфиг в родительской директории."""
        config_file = tmp_path / CONFIG_FILE_NAME
        config_file.write_text("[wiki]\norg_id = '1'")

        subdir = tmp_path / "subdir" / "deep"
        subdir.mkdir(parents=True)

        found = find_config_file(subdir)
        assert found == config_file

    def test_not_found(self, tmp_path):
        """Возвращает None если конфиг не найден."""
        subdir = tmp_path / "empty"
        subdir.mkdir()

        found = find_config_file(subdir)
        assert found is None


class TestGetDocsDir:
    """Тесты для get_docs_dir."""

    def test_creates_directory(self, tmp_path):
        """Создаёт директорию если не существует."""
        settings = Settings(
            token="test",
            wiki=WikiSettings(org_id="1", base_slug="test", docs_dir="my_docs"),
        )

        docs_dir = get_docs_dir(settings, tmp_path)

        assert docs_dir == tmp_path / "my_docs"
        assert docs_dir.exists()

    def test_existing_directory(self, tmp_path):
        """Работает с существующей директорией."""
        (tmp_path / "docs").mkdir()

        settings = Settings(
            token="test",
            wiki=WikiSettings(org_id="1", base_slug="test"),
        )

        docs_dir = get_docs_dir(settings, tmp_path)

        assert docs_dir == tmp_path / "docs"
        assert docs_dir.exists()


class TestGetMetaFilePath:
    """Тесты для get_meta_file_path."""

    def test_returns_correct_path(self, tmp_path):
        """Возвращает правильный путь к meta файлу."""
        meta_path = get_meta_file_path(tmp_path)
        assert meta_path == tmp_path / ".wiki-meta.json"


class TestCreateDefaultConfig:
    """Тесты для create_default_config."""

    def test_creates_config(self, tmp_path):
        """Создаёт файл конфигурации."""
        output_path = tmp_path / CONFIG_FILE_NAME

        result = create_default_config(
            org_id="789",
            base_slug="users/dev/project",
            docs_dir="wiki",
            output_path=output_path,
        )

        assert result == output_path
        assert output_path.exists()

        content = output_path.read_text()
        assert 'org_id = "789"' in content
        assert 'base_slug = "users/dev/project"' in content
        assert 'docs_dir = "wiki"' in content

    def test_default_output_path(self, tmp_path, monkeypatch):
        """Использует текущую директорию по умолчанию."""
        monkeypatch.chdir(tmp_path)

        result = create_default_config(
            org_id="123",
            base_slug="test",
        )

        assert result == tmp_path / CONFIG_FILE_NAME
        assert result.exists()

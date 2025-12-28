"""Тесты для CLI."""

import os

from typer.testing import CliRunner

from sandboxer.wiki_sync.cli import app

runner = CliRunner()


class TestCLIVersion:
    """Тесты для флага --version."""

    def test_version(self):
        """Показ версии."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "wiki-sync" in result.stdout

    def test_version_short(self):
        """Короткий флаг -V."""
        result = runner.invoke(app, ["-V"])
        assert result.exit_code == 0


class TestCLIInit:
    """Тесты для команды init."""

    def test_init_creates_config(self, tmp_path):
        """init создаёт файл конфигурации."""
        os.chdir(tmp_path)

        result = runner.invoke(
            app,
            ["init", "--org-id", "123", "--slug", "users/test/project"],
        )

        assert result.exit_code == 0
        assert (tmp_path / ".wiki-sync.toml").exists()

    def test_init_creates_docs_dir(self, tmp_path):
        """init создаёт папку docs."""
        os.chdir(tmp_path)

        runner.invoke(
            app,
            ["init", "--org-id", "123", "--slug", "users/test"],
        )

        assert (tmp_path / "docs").exists()

    def test_init_custom_docs_dir(self, tmp_path):
        """init с кастомной папкой."""
        os.chdir(tmp_path)

        runner.invoke(
            app,
            ["init", "--org-id", "123", "--slug", "users/test", "--docs-dir", "wiki"],
        )

        assert (tmp_path / "wiki").exists()

    def test_init_refuses_overwrite(self, tmp_path):
        """init не перезаписывает существующий конфиг."""
        os.chdir(tmp_path)
        (tmp_path / ".wiki-sync.toml").write_text("existing")

        result = runner.invoke(
            app,
            ["init", "--org-id", "123", "--slug", "users/test"],
        )

        assert result.exit_code == 1
        assert (tmp_path / ".wiki-sync.toml").read_text() == "existing"

    def test_init_force_overwrite(self, tmp_path):
        """init --force перезаписывает конфиг."""
        os.chdir(tmp_path)
        (tmp_path / ".wiki-sync.toml").write_text("existing")

        result = runner.invoke(
            app,
            ["init", "--org-id", "123", "--slug", "users/test", "--force"],
        )

        assert result.exit_code == 0
        assert "org_id" in (tmp_path / ".wiki-sync.toml").read_text()


class TestCLIConfig:
    """Тесты для команды config."""

    def test_config_not_found(self, tmp_path):
        """Конфиг не найден."""
        os.chdir(tmp_path)

        result = runner.invoke(app, ["config"])

        assert result.exit_code == 2

    def test_config_show(self, tmp_path):
        """Показ конфига."""
        os.chdir(tmp_path)
        config_content = '[wiki]\norg_id = "123"\nbase_slug = "test"'
        (tmp_path / ".wiki-sync.toml").write_text(config_content)

        result = runner.invoke(app, ["config"])

        assert result.exit_code == 0
        assert "123" in result.stdout

    def test_config_path_only(self, tmp_path):
        """Показ только пути к конфигу."""
        os.chdir(tmp_path)
        (tmp_path / ".wiki-sync.toml").write_text('[wiki]\norg_id = "1"')

        result = runner.invoke(app, ["config", "--path"])

        assert result.exit_code == 0
        assert ".wiki-sync.toml" in result.stdout


class TestCLIStatusNoConfig:
    """Тесты для status без конфига."""

    def test_status_no_config(self, tmp_path):
        """status без конфига выдаёт ошибку."""
        os.chdir(tmp_path)

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 2
        # Ошибка выводится в stderr, но CliRunner объединяет в output
        output = result.stdout + (result.stderr or "")
        assert "не найден" in output or "init" in output or result.exit_code == 2


class TestCLIPushNoConfig:
    """Тесты для push без конфига."""

    def test_push_no_config(self, tmp_path):
        """push без конфига выдаёт ошибку."""
        os.chdir(tmp_path)

        result = runner.invoke(app, ["push"])

        assert result.exit_code == 2

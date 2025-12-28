"""CLI интерфейс wiki-sync на базе Typer."""

import json
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError as PydanticValidationError
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from . import __version__
from .core import (
    CONFIG_FILE_NAME,
    ConfigError,
    Settings,
    SyncResult,
    SyncStatus,
    WikiSyncError,
    create_default_config,
    create_sync,
    find_config_file,
    get_docs_dir,
)

# Настройка
console = Console()
err_console = Console(stderr=True)

app = typer.Typer(
    name="wiki-sync",
    help="Синхронизация локальных Markdown-файлов с Yandex Wiki",
    add_completion=True,
    no_args_is_help=False,
)

# Глобальные переменные для обработки сигналов
_sync_instance = None


def _signal_handler(_sig: int, _frame: object) -> None:
    """Обработка Ctrl+C."""
    console.print("\n\n[yellow]⚠️ Прерывание...[/yellow]")
    if _sync_instance:
        _sync_instance.save_meta()
        console.print("[dim]💾 Метаданные сохранены[/dim]")
    console.print("[dim]👋 До свидания![/dim]")
    sys.exit(0)


def _setup_logging(verbose: int, quiet: bool) -> None:
    """Настроить логирование."""
    if quiet:
        level = logging.ERROR
    elif verbose == 0:
        level = logging.WARNING
    elif verbose == 1:
        level = logging.INFO
    else:
        level = logging.DEBUG

    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s",
    )


def _get_settings(
    config_path: Path | None = None,
    token: str | None = None,
) -> Settings:
    """Получить настройки приложения."""
    # Ищем файл конфигурации
    if config_path is None:
        config_path = find_config_file()

    if config_path is None:
        raise ConfigError(f"Файл конфигурации {CONFIG_FILE_NAME} не найден.\nСоздайте его командой: wiki-sync init")

    # Получаем токен
    env_token = os.environ.get("WIKI_SYNC_TOKEN")
    final_token = token or env_token

    if not final_token:
        raise ConfigError(
            "Токен не указан.\n"
            "Установите переменную окружения: export WIKI_SYNC_TOKEN='y0_...'\n"
            "Или передайте через --token"
        )

    try:
        return Settings.from_file(config_path, token=final_token)
    except PydanticValidationError as e:
        raise ConfigError(f"Ошибка конфигурации: {e}") from e


def _print_status(result: SyncResult) -> None:
    """Вывести статус синхронизации."""
    if result.synced:
        console.print(f"[green]✅ Синхронизировано:[/green] {len(result.synced)} файлов")

    if result.errors:
        console.print(f"\n[red]❌ ОШИБКИ ЧТЕНИЯ:[/red] {len(result.errors)}")
        for fs in result.errors[:5]:
            console.print(f"   • {fs.file_path.name}: {fs.error_message}")
        if len(result.errors) > 5:
            console.print(f"   [dim]... и ещё {len(result.errors) - 5}[/dim]")

    if result.conflict:
        console.print(f"\n[yellow]⚠️  КОНФЛИКТЫ:[/yellow] {len(result.conflict)}")
        for fs in result.conflict[:5]:
            wiki_time = fs.wiki_modified.strftime("%Y-%m-%d %H:%M") if fs.wiki_modified else "?"
            console.print(f"   • {fs.file_path.name} [dim](Wiki: {wiki_time})[/dim]")
        if len(result.conflict) > 5:
            console.print(f"   [dim]... и ещё {len(result.conflict) - 5}[/dim]")

    if result.remote_modified:
        console.print(f"\n[cyan]📥 ИЗМЕНЕНО В WIKI:[/cyan] {len(result.remote_modified)}")
        for fs in result.remote_modified[:5]:
            wiki_time = fs.wiki_modified.strftime("%Y-%m-%d %H:%M") if fs.wiki_modified else "?"
            console.print(f"   • {fs.file_path.name} [dim](Wiki: {wiki_time})[/dim]")
        if len(result.remote_modified) > 5:
            console.print(f"   [dim]... и ещё {len(result.remote_modified) - 5}[/dim]")

    if result.modified:
        console.print(f"\n[blue]📝 ИЗМЕНЕНО ЛОКАЛЬНО:[/blue] {len(result.modified)}")
        for fs in result.modified[:10]:
            console.print(f"   • {fs.file_path.name}")
        if len(result.modified) > 10:
            console.print(f"   [dim]... и ещё {len(result.modified) - 10}[/dim]")

    if result.new:
        console.print(f"\n[green]🆕 НОВЫЕ ФАЙЛЫ:[/green] {len(result.new)}")
        for fs in result.new[:10]:
            console.print(f"   • {fs.file_path.name}")
        if len(result.new) > 10:
            console.print(f"   [dim]... и ещё {len(result.new) - 10}[/dim]")

    if result.deleted_local:
        console.print(f"\n[red]🗑️ УДАЛЕНЫ ЛОКАЛЬНО:[/red] {len(result.deleted_local)}")
        for fs in result.deleted_local[:5]:
            console.print(f"   • {fs.title}")
        if len(result.deleted_local) > 5:
            console.print(f"   [dim]... и ещё {len(result.deleted_local) - 5}[/dim]")

    if not result.has_changes:
        console.print("\n[green]✨ Всё синхронизировано![/green]")


def _interactive_mode() -> None:
    """Интерактивный режим с меню."""
    global _sync_instance

    signal.signal(signal.SIGINT, _signal_handler)

    # Проверяем наличие конфига
    config_path = find_config_file()
    if config_path is None:
        console.print(
            Panel.fit(
                "[yellow]📋 Конфигурация не найдена[/yellow]\n\n"
                f"Создайте файл {CONFIG_FILE_NAME} командой:\n"
                "[cyan]wiki-sync init[/cyan]",
                title="wiki-sync",
                border_style="yellow",
            )
        )
        raise typer.Exit(2)

    # Проверяем токен
    token = os.environ.get("WIKI_SYNC_TOKEN")
    if not token:
        console.print(
            Panel.fit(
                "[yellow]🔑 Токен не найден[/yellow]\n\n"
                "Установите переменную окружения:\n"
                "[cyan]export WIKI_SYNC_TOKEN='y0_...'[/cyan]",
                title="wiki-sync",
                border_style="yellow",
            )
        )
        raise typer.Exit(2)

    try:
        settings = Settings.from_file(config_path, token=token)
        docs_dir = get_docs_dir(settings)
        sync = create_sync(settings, docs_dir)
        _sync_instance = sync
    except WikiSyncError as e:
        err_console.print(f"[red]❌ {e.message}[/red]")
        raise typer.Exit(e.exit_code) from None

    while True:
        console.clear()
        console.print(
            Panel.fit(
                f"[bold]wiki-sync[/bold] v{__version__}\n"
                f"[dim]Wiki:[/dim] {settings.wiki.base_slug}\n"
                f"[dim]Docs:[/dim] {docs_dir}",
                border_style="blue",
            )
        )

        # Получаем статус
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task("Анализ...", total=None)
            result = sync.get_status()

        # Выводим статус
        _print_status(result)
        console.print()

        # Меню действий
        actions: list[tuple[str, str]] = []

        if result.new or result.modified:
            count = len(result.new) + len(result.modified)
            actions.append(("p", f"📤 Push — загрузить {count} файлов в Wiki"))

        if result.remote_modified:
            actions.append(("l", f"📥 Pull — скачать {len(result.remote_modified)} изменений из Wiki"))

        if result.conflict:
            actions.append(("c", f"⚠️ Конфликты — разрешить {len(result.conflict)} конфликтов"))

        if result.deleted_local:
            actions.append(("d", f"🗑️ Delete — удалить {len(result.deleted_local)} страниц из Wiki"))

        actions.append(("r", "🔄 Refresh — обновить статус"))
        actions.append(("q", "👋 Quit — выход"))

        console.print("[bold]Действия:[/bold]")
        for key, description in actions:
            console.print(f"  [{key}] {description}")

        console.print()
        choice = typer.prompt("Выберите действие", default="q").lower().strip()

        if choice == "q":
            console.print("[dim]👋 До свидания![/dim]")
            break

        elif choice == "r":
            continue  # Refresh — просто перезапускаем цикл

        elif choice == "p" and (result.new or result.modified):
            files = result.uploadable_files
            console.print(f"\n[blue]📤 Загрузка {len(files)} файлов...[/blue]")

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Загрузка...", total=len(files))
                for fs in files:
                    progress.update(task, description=f"[dim]{fs.file_path.name}[/dim]")
                    sync.push_file(fs)
                    progress.advance(task)

            sync.save_meta()
            console.print("[green]✅ Загрузка завершена[/green]")
            typer.prompt("\nНажмите Enter для продолжения", default="")

        elif choice == "l" and result.remote_modified:
            console.print(f"\n[blue]📥 Скачивание {len(result.remote_modified)} файлов...[/blue]")
            for fs in result.remote_modified:
                if sync.pull_file(fs.slug):
                    console.print(f"  [green]✅[/green] {fs.file_path.name}")
                else:
                    console.print(f"  [red]❌[/red] {fs.file_path.name}")
            typer.prompt("\nНажмите Enter для продолжения", default="")

        elif choice == "c" and result.conflict:
            console.print("\n[yellow]⚠️ Разрешение конфликтов[/yellow]")
            for fs in result.conflict:
                console.print(f"\n  Конфликт: [bold]{fs.file_path.name}[/bold]")
                wiki_time = fs.wiki_modified.strftime("%Y-%m-%d %H:%M") if fs.wiki_modified else "?"
                console.print(f"  Wiki изменена: {wiki_time}")
                console.print("    [l] Оставить локальную версию (перезаписать Wiki)")
                console.print("    [w] Скачать версию из Wiki (перезаписать локально)")
                console.print("    [s] Пропустить")

                action = typer.prompt("Действие", default="s").lower().strip()
                if action == "l":
                    sync.push_file(fs)
                    console.print("    [green]✅ Локальная версия загружена в Wiki[/green]")
                elif action == "w":
                    sync.pull_file(fs.slug)
                    console.print("    [green]✅ Версия из Wiki скачана[/green]")
                else:
                    console.print("    [dim]⏭️ Пропущено[/dim]")

            sync.save_meta()
            typer.prompt("\nНажмите Enter для продолжения", default="")

        elif choice == "d" and result.deleted_local:
            console.print(f"\n[yellow]⚠️ Удаление {len(result.deleted_local)} страниц из Wiki[/yellow]")
            for fs in result.deleted_local:
                console.print(f"  • {fs.title}")

            if typer.confirm("Удалить?", default=False):
                slugs = [fs.slug for fs in result.deleted_local]
                delete_result = sync.delete_pages(slugs)
                console.print(f"[green]✅ Удалено: {delete_result.deleted}[/green]")
            else:
                console.print("[dim]Отменено[/dim]")

            typer.prompt("\nНажмите Enter для продолжения", default="")

        else:
            console.print("[yellow]Неизвестное действие[/yellow]")
            typer.prompt("\nНажмите Enter для продолжения", default="")


# === CALLBACK (глобальные опции) ===


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option("--version", "-V", help="Показать версию и выйти"),
    ] = False,
    verbose: Annotated[
        int,
        typer.Option("--verbose", "-v", count=True, help="Уровень подробности (-v, -vv)"),
    ] = 0,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Минимальный вывод"),
    ] = False,
) -> None:
    """Синхронизация локальных Markdown-файлов с Yandex Wiki."""
    _setup_logging(verbose, quiet)

    if version:
        console.print(f"wiki-sync {__version__}")
        raise typer.Exit()

    # Если команда не указана — интерактивный режим
    if ctx.invoked_subcommand is None:
        _interactive_mode()


# === КОМАНДА INIT ===


@app.command()
def init(
    org_id: Annotated[
        str | None,
        typer.Option("--org-id", "-o", help="ID организации"),
    ] = None,
    slug: Annotated[
        str | None,
        typer.Option("--slug", "-s", help="Базовый slug раздела Wiki"),
    ] = None,
    docs_dir: Annotated[
        str,
        typer.Option("--docs-dir", "-d", help="Папка с документами"),
    ] = "docs",
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Перезаписать существующий конфиг"),
    ] = False,
) -> None:
    """Создать файл конфигурации .wiki-sync.toml."""
    config_file = Path.cwd() / CONFIG_FILE_NAME

    if config_file.exists() and not force:
        console.print(f"[yellow]⚠️ Файл {CONFIG_FILE_NAME} уже существует.[/yellow]")
        console.print("Используйте --force для перезаписи.")
        raise typer.Exit(1)

    # Интерактивный режим если параметры не указаны
    if not org_id:
        org_id = typer.prompt("ID организации", default="")
        if not org_id:
            err_console.print("[red]❌ ID организации обязателен[/red]")
            raise typer.Exit(2)

    if not slug:
        slug = typer.prompt("Базовый slug раздела Wiki (например: users/username/project)")
        if not slug:
            err_console.print("[red]❌ Slug обязателен[/red]")
            raise typer.Exit(2)

    # Создаём конфиг
    config_path = create_default_config(org_id, slug, docs_dir)
    console.print(f"[green]✅ Создан файл:[/green] {config_path}")

    # Создаём папку docs если не существует
    docs_path = Path.cwd() / docs_dir
    if not docs_path.exists():
        docs_path.mkdir(parents=True)
        console.print(f"[green]✅ Создана папка:[/green] {docs_path}")

    console.print()
    console.print("[dim]Следующие шаги:[/dim]")
    console.print("1. Установите токен: [cyan]export WIKI_SYNC_TOKEN='y0_...'[/cyan]")
    console.print("2. Проверьте статус: [cyan]wiki-sync status[/cyan]")


# === КОМАНДА STATUS ===


@app.command()
def status(
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Путь к файлу конфигурации"),
    ] = None,
    token: Annotated[
        str | None,
        typer.Option("--token", "-t", help="OAuth токен"),
    ] = None,
    output_json: Annotated[
        bool,
        typer.Option("--json", "-j", help="Вывод в формате JSON"),
    ] = False,
) -> None:
    """Показать статус синхронизации."""
    global _sync_instance

    try:
        settings = _get_settings(config, token)
        docs_dir = get_docs_dir(settings)
        sync = create_sync(settings, docs_dir)
        _sync_instance = sync

        signal.signal(signal.SIGINT, _signal_handler)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task("Анализ файлов...", total=None)
            result = sync.get_status()

        if output_json:
            # JSON вывод для CI/CD
            data = {
                "synced": len(result.synced),
                "modified": len(result.modified),
                "new": len(result.new),
                "conflict": len(result.conflict),
                "remote_modified": len(result.remote_modified),
                "deleted_local": len(result.deleted_local),
                "errors": len(result.errors),
            }
            console.print(json.dumps(data, indent=2))
        else:
            _print_status(result)

        # Exit code
        if result.has_conflicts:
            raise typer.Exit(4)

    except WikiSyncError as e:
        err_console.print(f"[red]❌ {e.message}[/red]")
        raise typer.Exit(e.exit_code) from None


# === КОМАНДА PUSH ===


@app.command()
def push(
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Путь к файлу конфигурации"),
    ] = None,
    token: Annotated[
        str | None,
        typer.Option("--token", "-t", help="OAuth токен"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "-n", help="Показать что будет загружено"),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Игнорировать конфликты"),
    ] = False,
) -> None:
    """Загрузить изменения в Wiki."""
    global _sync_instance

    try:
        settings = _get_settings(config, token)
        docs_dir = get_docs_dir(settings)
        sync = create_sync(settings, docs_dir)
        _sync_instance = sync

        signal.signal(signal.SIGINT, _signal_handler)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task("Анализ файлов...", total=None)
            result = sync.get_status()

        # Проверяем конфликты
        if result.has_conflicts and not force:
            console.print(f"[yellow]⚠️ КОНФЛИКТЫ:[/yellow] {len(result.conflict)} файлов")
            for fs in result.conflict:
                console.print(f"   • {fs.file_path.name}")
            console.print()
            console.print("[dim]Используйте --force для принудительной загрузки[/dim]")
            console.print("[dim]Или разрешите конфликты вручную[/dim]")
            raise typer.Exit(4)

        # Собираем файлы для загрузки
        files = result.uploadable_files
        if force:
            files.extend(result.conflict)

        if not files:
            console.print("[green]✅ Нет изменений для загрузки[/green]")
            raise typer.Exit(0)

        if dry_run:
            console.print(f"[cyan]📋 Будет загружено {len(files)} файлов:[/cyan]")
            for fs in files:
                status_icon = "🆕" if fs.status == SyncStatus.NEW else "📝"
                console.print(f"   {status_icon} {fs.file_path.name}")
            raise typer.Exit(0)

        # Загружаем
        console.print(f"[blue]📤 Загрузка {len(files)} файлов...[/blue]")

        created = 0
        updated = 0
        errors = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Загрузка...", total=len(files))

            for fs in files:
                progress.update(task, description=f"[dim]{fs.file_path.name}[/dim]")
                is_new = fs.status == SyncStatus.NEW
                if sync.push_file(fs):
                    if is_new:
                        created += 1
                    else:
                        updated += 1
                else:
                    errors += 1
                progress.advance(task)

        sync.save_meta()

        console.print()
        console.print(
            f"[green]✅ Создано:[/green] {created}, [blue]✏️ Обновлено:[/blue] {updated}, [red]❌ Ошибок:[/red] {errors}"
        )

        if errors > 0:
            raise typer.Exit(1)

    except WikiSyncError as e:
        err_console.print(f"[red]❌ {e.message}[/red]")
        raise typer.Exit(e.exit_code) from None


# === КОМАНДА PULL ===


@app.command()
def pull(
    slug: Annotated[
        str | None,
        typer.Argument(help="Slug страницы для скачивания (опционально)"),
    ] = None,
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Путь к файлу конфигурации"),
    ] = None,
    token: Annotated[
        str | None,
        typer.Option("--token", "-t", help="OAuth токен"),
    ] = None,
) -> None:
    """Скачать изменения из Wiki."""
    global _sync_instance

    try:
        settings = _get_settings(config, token)
        docs_dir = get_docs_dir(settings)
        sync = create_sync(settings, docs_dir)
        _sync_instance = sync

        signal.signal(signal.SIGINT, _signal_handler)

        if slug:
            # Скачиваем конкретную страницу
            full_slug = slug
            if not slug.startswith(settings.wiki.base_slug):
                full_slug = f"{settings.wiki.base_slug}/{slug}"

            console.print(f"[blue]📥 Скачивание {full_slug}...[/blue]")

            if sync.pull_file(full_slug):
                console.print("[green]✅ Страница скачана[/green]")
            else:
                err_console.print("[red]❌ Страница не найдена[/red]")
                raise typer.Exit(1)
        else:
            # Скачиваем все изменённые в Wiki
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                progress.add_task("Анализ файлов...", total=None)
                result = sync.get_status()

            if not result.remote_modified:
                console.print("[green]✅ Нет изменений в Wiki для скачивания[/green]")
                raise typer.Exit(0)

            console.print(f"[blue]📥 Скачивание {len(result.remote_modified)} файлов...[/blue]")

            success = 0
            errors = 0
            for fs in result.remote_modified:
                if sync.pull_file(fs.slug):
                    console.print(f"   [green]✅[/green] {fs.file_path.name}")
                    success += 1
                else:
                    console.print(f"   [red]❌[/red] {fs.file_path.name}")
                    errors += 1

            console.print()
            console.print(f"[green]✅ Скачано:[/green] {success}, [red]❌ Ошибок:[/red] {errors}")

            if errors > 0:
                raise typer.Exit(1)

    except WikiSyncError as e:
        err_console.print(f"[red]❌ {e.message}[/red]")
        raise typer.Exit(e.exit_code) from None


# === КОМАНДА CONFIG ===


@app.command("config")
def show_config(
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Путь к файлу конфигурации"),
    ] = None,
    path_only: Annotated[
        bool,
        typer.Option("--path", "-p", help="Показать только путь к конфигу"),
    ] = False,
) -> None:
    """Показать текущую конфигурацию."""
    config_file = config or find_config_file()

    if config_file is None:
        err_console.print(f"[red]❌ Файл {CONFIG_FILE_NAME} не найден[/red]")
        raise typer.Exit(2)

    if path_only:
        console.print(str(config_file))
        raise typer.Exit(0)

    console.print(f"[dim]Файл:[/dim] {config_file}")
    console.print()

    # Читаем и выводим содержимое
    content = config_file.read_text()
    console.print(Panel(content, title=CONFIG_FILE_NAME, border_style="dim"))


# === КОМАНДА DELETE ===


@app.command()
def delete(
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Путь к файлу конфигурации"),
    ] = None,
    token: Annotated[
        str | None,
        typer.Option("--token", "-t", help="OAuth токен"),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Удалить без подтверждения"),
    ] = False,
) -> None:
    """Удалить из Wiki страницы, которые удалены локально."""
    global _sync_instance

    try:
        settings = _get_settings(config, token)
        docs_dir = get_docs_dir(settings)
        sync = create_sync(settings, docs_dir)
        _sync_instance = sync

        signal.signal(signal.SIGINT, _signal_handler)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            progress.add_task("Анализ файлов...", total=None)
            result = sync.get_status()

        if not result.deleted_local:
            console.print("[green]✅ Нет страниц для удаления[/green]")
            raise typer.Exit(0)

        console.print(f"[yellow]⚠️ Будет удалено {len(result.deleted_local)} страниц из Wiki:[/yellow]")
        for fs in result.deleted_local:
            console.print(f"   • {fs.title}")

        if not force:
            confirm = typer.confirm("\nУдалить?", default=False)
            if not confirm:
                console.print("[dim]Отменено[/dim]")
                raise typer.Exit(0)

        slugs = [fs.slug for fs in result.deleted_local]
        delete_result = sync.delete_pages(slugs)

        console.print()
        console.print(
            f"[green]✅ Удалено:[/green] {delete_result.deleted}, [red]❌ Ошибок:[/red] {delete_result.errors}"
        )

        if delete_result.errors > 0:
            raise typer.Exit(1)

    except WikiSyncError as e:
        err_console.print(f"[red]❌ {e.message}[/red]")
        raise typer.Exit(e.exit_code) from None


if __name__ == "__main__":
    app()

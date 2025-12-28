# Changelog

Все значимые изменения в проекте документируются в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
проект следует [Semantic Versioning](https://semver.org/lang/ru/).

## [Unreleased]

## [0.1.2] - 2024-12-28

### Fixed

- **CLI**: Исправлено отображение букв действий в интерактивном меню
  - Теперь `[p]`, `[r]`, `[q]` и другие буквы корректно отображаются
  - Промпт динамически показывает только доступные действия

## [0.1.1] - 2024-12-28

### Fixed

- **CI**: Исправлена конфигурация `pip-audit` для корректного сканирования зависимостей
- **Build**: Исправлена установка `twine` в CI через `uvx`

## [0.1.0] - 2024-12-28

### Added

- 🚀 **CLI инструмент** для синхронизации локальных Markdown-файлов с Yandex Wiki
  - Команда `init` — инициализация конфигурации проекта
  - Команда `status` — просмотр статуса синхронизации
  - Команда `push` — загрузка локальных изменений в Wiki
  - Команда `pull` — скачивание изменений из Wiki
  - Команда `delete` — удаление страниц из Wiki
  - Команда `config` — просмотр конфигурации
- 🎨 **Интерактивный режим** с меню при запуске без аргументов
- 🔄 **Двусторонняя синхронизация** с отслеживанием изменений по хешу контента
- ⚠️ **Обнаружение конфликтов** — когда файл изменён и локально, и в Wiki
- 📁 **Поддержка вложенных папок** с автоматическим созданием структуры в Wiki
- 🔧 **Конфигурация через TOML** — файл `.wiki-sync.toml`
- 🔑 **Безопасное хранение токена** через переменные окружения
- 📊 **JSON вывод** для интеграции с CI/CD (`--json` флаг)
- 🎯 **Dry-run режим** для предпросмотра изменений (`--dry-run` флаг)
- 📝 **Игнорирование файлов** по паттернам (`.gitignore`-style)
- ✨ **Красивый UI** с прогресс-барами и цветным выводом (Rich)

### Technical

- Python 3.11-3.14 support
- Type hints throughout the codebase (`py.typed`)
- Pydantic v2 for configuration and data validation
- Typer + Rich for CLI
- Comprehensive test suite with pytest
- CI/CD с GitHub Actions
- Документация на MkDocs + GitHub Pages

[Unreleased]: https://github.com/Sandboxer-ai/sandboxer-yandex-wiki-sync/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/Sandboxer-ai/sandboxer-yandex-wiki-sync/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/Sandboxer-ai/sandboxer-yandex-wiki-sync/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Sandboxer-ai/sandboxer-yandex-wiki-sync/releases/tag/v0.1.0

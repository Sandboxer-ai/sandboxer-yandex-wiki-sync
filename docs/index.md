# sandboxer-yandex-wiki-sync

CLI-инструмент для двусторонней синхронизации локальной документации (Markdown) с Yandex Wiki.

## Возможности

- **Двусторонняя синхронизация**: `push` для загрузки, `pull` для скачивания
- **Отслеживание изменений**: синхронизация только изменённых файлов по хешу контента
- **Обнаружение конфликтов**: когда файл изменён и локально, и в Wiki
- **Вложенные папки**: автоматическое создание структуры в Wiki
- **Интерактивный режим**: меню при запуске без аргументов
- **JSON вывод**: для интеграции с CI/CD

## Установка

```bash
# pipx (рекомендуется)
pipx install sandboxer-yandex-wiki-sync

# pip
pip install sandboxer-yandex-wiki-sync

# uv
uv tool install sandboxer-yandex-wiki-sync
```

## Быстрый старт

```bash
# Инициализация
sb-wiki init

# Установка токена
export WIKI_SYNC_TOKEN="y0_your_oauth_token"

# Проверка статуса
sb-wiki status

# Загрузка в Wiki
sb-wiki push
```

## Навигация

- [Быстрый старт](quickstart.md) — подробная инструкция
- [API Reference](api/index.md) — документация для разработчиков


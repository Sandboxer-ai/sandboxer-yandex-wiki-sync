# Быстрый старт

## 1. Установка

```bash
pipx install sandboxer-yandex-wiki-sync
```

## 2. Инициализация

```bash
cd your-project
sb-wiki init
```

Введите:

- **Org ID**: ID организации (из URL Wiki: `.../wiki/org/<ID>/...`)
- **Slug**: базовый путь в Wiki (`users/dev/docs` или `projects/backend`)

Будет создан файл `.wiki-sync.toml`.

## 3. Получение токена

1. Перейдите на [Яндекс.OAuth](https://oauth.yandex.ru/)
2. Создайте приложение (Web services)
3. В правах выберите **Yandex Wiki API**
4. Получите токен

```bash
export WIKI_SYNC_TOKEN="y0_your_oauth_token"
```

!!! warning "Безопасность"
    Никогда не сохраняйте токен в конфигурационных файлах.

## 4. Использование

### Интерактивный режим

```bash
sb-wiki
```

### Команды

```bash
# Статус синхронизации
sb-wiki status

# Загрузить в Wiki
sb-wiki push

# Скачать из Wiki
sb-wiki pull

# Удалить страницу
sb-wiki delete path/to/page.md

# Показать конфигурацию
sb-wiki config
```

### Опции

```bash
# Предпросмотр без изменений
sb-wiki push --dry-run

# JSON вывод для CI/CD
sb-wiki status --json

# Подробный вывод
sb-wiki push -v
```

## 5. Конфигурация

Файл `.wiki-sync.toml`:

```toml
[wiki]
org_id = "123456"
base_slug = "users/dev/docs"
docs_dir = "docs"

[sync]
ignore = ["*.draft.md", "SECRET.md"]
strip_title = true
timeout = 60
```

## Программное использование

```python
from sandboxer.wiki_sync import WikiSync, Settings

settings = Settings.from_file()
sync = WikiSync(settings)

# Получить статус
statuses = sync.get_status()
for status in statuses:
    print(f"{status.path}: {status.status}")

# Загрузить файл
sync.push_file("docs/readme.md")
```


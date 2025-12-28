# API Reference

Документация для программного использования библиотеки.

## Основные классы

| Класс | Описание |
|-------|----------|
| [`WikiSync`](sync.md) | Основной класс для синхронизации |
| [`WikiAPI`](api.md) | HTTP-клиент для Yandex Wiki API |
| [`Settings`](config.md) | Конфигурация приложения |

## Модели данных

| Модель | Описание |
|--------|----------|
| [`FileStatus`](models.md#sandboxer.wiki_sync.core.models.FileStatus) | Статус синхронизации файла |
| [`SyncResult`](models.md#sandboxer.wiki_sync.core.models.SyncResult) | Результат операции синхронизации |
| [`PageInfo`](models.md#sandboxer.wiki_sync.core.models.PageInfo) | Информация о странице Wiki |

## Исключения

| Исключение | Описание |
|------------|----------|
| [`WikiSyncError`](errors.md#sandboxer.wiki_sync.core.errors.WikiSyncError) | Базовое исключение |
| [`ApiError`](errors.md#sandboxer.wiki_sync.core.errors.ApiError) | Ошибка API |
| [`ConfigError`](errors.md#sandboxer.wiki_sync.core.errors.ConfigError) | Ошибка конфигурации |
| [`ConflictError`](errors.md#sandboxer.wiki_sync.core.errors.ConflictError) | Конфликт версий |

## Пример

```python
from sandboxer.wiki_sync import WikiSync, Settings, WikiSyncError

try:
    settings = Settings.from_file()
    sync = WikiSync(settings)
    
    for status in sync.get_status():
        if status.status == "modified":
            sync.push_file(status.path)
            
except WikiSyncError as e:
    print(f"Ошибка: {e.message}")
```


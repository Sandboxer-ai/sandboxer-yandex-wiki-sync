"""Утилиты для хеширования контента."""

import hashlib


def hash_content(content: str | None) -> str:
    """Вычислить MD5 хеш нормализованного контента.

    Нормализация:
    - Убирает пробелы в конце строк
    - Убирает пустые строки в начале и конце

    Args:
        content: Строка для хеширования.

    Returns:
        MD5 хеш в hex формате.
    """
    if not content:
        return hashlib.md5(b"", usedforsecurity=False).hexdigest()

    # Нормализуем контент
    lines = content.strip().split("\n")
    normalized = "\n".join(line.rstrip() for line in lines)

    return hashlib.md5(normalized.encode("utf-8"), usedforsecurity=False).hexdigest()


def content_equal(content1: str | None, content2: str | None) -> bool:
    """Проверить равенство контента (с нормализацией).

    Args:
        content1: Первая строка.
        content2: Вторая строка.

    Returns:
        True если контент равен после нормализации.
    """
    return hash_content(content1) == hash_content(content2)

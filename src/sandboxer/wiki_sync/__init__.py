"""sandboxer-yandex-wiki-sync — синхронизация локальных Markdown-файлов с Yandex Wiki."""

import logging

try:
    from ._version import __version__
except ImportError:
    __version__ = "0.0.0.dev0"

from .core import (
    Settings,
    WikiAPI,
    WikiSync,
    WikiSyncError,
    create_sync,
)

# NullHandler предотвращает "No handlers could be found" warnings
# если пользователь не настроил логирование
logging.getLogger(__name__).addHandler(logging.NullHandler())

__all__ = [
    "Settings",
    "WikiAPI",
    "WikiSync",
    "WikiSyncError",
    "__version__",
    "create_sync",
]

"""Тесты для утилит хеширования."""

from sandboxer.wiki_sync.utils.hashing import content_equal, hash_content


class TestHashContent:
    """Тесты для hash_content."""

    def test_empty_string(self):
        """Пустая строка даёт стабильный хеш."""
        assert hash_content("") == hash_content("")

    def test_none_returns_empty_hash(self):
        """None обрабатывается как пустая строка."""
        assert hash_content(None) == hash_content("")

    def test_same_content_same_hash(self):
        """Одинаковый контент — одинаковый хеш."""
        content = "# Hello\n\nWorld"
        assert hash_content(content) == hash_content(content)

    def test_different_content_different_hash(self):
        """Разный контент — разный хеш."""
        assert hash_content("hello") != hash_content("world")

    def test_trailing_whitespace_normalized(self):
        """Пробелы в конце строк не влияют на хеш."""
        content1 = "hello   \nworld  "
        content2 = "hello\nworld"
        assert hash_content(content1) == hash_content(content2)

    def test_leading_trailing_newlines_normalized(self):
        """Пустые строки в начале и конце не влияют."""
        content1 = "\n\nhello\nworld\n\n"
        content2 = "hello\nworld"
        assert hash_content(content1) == hash_content(content2)

    def test_internal_content_preserved(self):
        """Внутреннее содержимое сохраняется."""
        content1 = "hello\n\nworld"
        content2 = "hello\nworld"
        assert hash_content(content1) != hash_content(content2)


class TestContentEqual:
    """Тесты для content_equal."""

    def test_equal_content(self):
        """Равный контент."""
        assert content_equal("hello", "hello")

    def test_not_equal_content(self):
        """Неравный контент."""
        assert not content_equal("hello", "world")

    def test_normalized_equal(self):
        """Равенство после нормализации."""
        assert content_equal("hello  \n", "hello\n")

    def test_both_none(self):
        """Оба None."""
        assert content_equal(None, None)

    def test_one_none(self):
        """Один None, другой пустой."""
        assert content_equal(None, "")

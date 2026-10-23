from unittest.mock import MagicMock, patch
from server.cache import purge_cached_ocr, purge_all_cached_ocr


def test_purge_cached_ocr_success():
    mock_redis = MagicMock()
    mock_redis.delete.return_value = 1
    with patch("server.cache.get_redis_client", return_value=mock_redis):
        assert purge_cached_ocr("abc123hash") is True
        mock_redis.delete.assert_called_once_with("ocr_cache:abc123hash")


def test_purge_cached_ocr_not_found():
    mock_redis = MagicMock()
    mock_redis.delete.return_value = 0
    with patch("server.cache.get_redis_client", return_value=mock_redis):
        assert purge_cached_ocr("missing_hash") is False


def test_purge_cached_ocr_no_client():
    with patch("server.cache.get_redis_client", return_value=None):
        assert purge_cached_ocr("any_hash") is False


def test_purge_all_cached_ocr():
    mock_redis = MagicMock()
    mock_redis.scan_iter.return_value = ["ocr_cache:hash1", "ocr_cache:hash2"]
    with patch("server.cache.get_redis_client", return_value=mock_redis):
        count = purge_all_cached_ocr()
        assert count == 2
        mock_redis.delete.assert_called_once_with("ocr_cache:hash1", "ocr_cache:hash2")


def test_purge_all_cached_ocr_empty():
    mock_redis = MagicMock()
    mock_redis.scan_iter.return_value = []
    with patch("server.cache.get_redis_client", return_value=mock_redis):
        count = purge_all_cached_ocr()
        assert count == 0
        mock_redis.delete.assert_not_called()

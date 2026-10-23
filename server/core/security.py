import re
import time
import urllib.parse
from collections import defaultdict


class RateLimiter:
    def __init__(self):
        self.requests = defaultdict(list)
        self.last_cleanup = time.time()

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> bool:
        now = time.time()
        if now - self.last_cleanup > 300:
            self._cleanup(now)
        history = self.requests[key]
        cutoff = now - window_seconds
        self.requests[key] = [t for t in history if t > cutoff]
        if len(self.requests[key]) >= max_requests:
            return False
        self.requests[key].append(now)
        return True

    def _cleanup(self, now: float):
        for k in list(self.requests.keys()):
            self.requests[k] = [t for t in self.requests[k] if t > now - 300]
            if not self.requests[k]:
                del self.requests[k]
        self.last_cleanup = now


rate_limiter = RateLimiter()


def format_content_disposition(disposition: str, filename: str) -> str:
    """Format RFC 5987 / RFC 6266 header allowing UTF-8 Thai filenames without crashing latin-1 encoder."""
    ascii_safe = re.sub(r"[^\x20-\x7e]", "_", filename)
    encoded = urllib.parse.quote(filename, encoding="utf-8")
    return f"{disposition}; filename=\"{ascii_safe}\"; filename*=UTF-8''{encoded}"

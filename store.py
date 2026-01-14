import time
import redis
from redis.exceptions import (
    RedisError,
    ConnectionError,
    TimeoutError,
)


class Store:
    def __init__(
        self,
        host="localhost",
        port=6379,
        db=0,
        retries=3,
        timeout=1,
    ):
        self.host = host
        self.port = port
        self.db = db
        self.retries = retries
        self.timeout = timeout
        self._client = None

    def _connect(self):
        if self._client is None:
            self._client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                socket_timeout=self.timeout,
                socket_connect_timeout=self.timeout,
                decode_responses=True,
            )

    def _execute(self, func, *args, **kwargs):
        for attempt in range(self.retries):
            try:
                self._connect()
                return func(*args, **kwargs)
            except (ConnectionError, TimeoutError, RedisError):
                self._client = None
                time.sleep(0.1)
        raise

    # === CACHE ===
    def cache_get(self, key):
        try:
            return self._execute(self._client.get, key)
        except Exception:
            return None

    def cache_set(self, key, value, timeout):
        try:
            self._execute(self._client.setex, key, timeout, value)
        except Exception:
            pass

    def get(self, key):
        return self._execute(self._client.get, key)

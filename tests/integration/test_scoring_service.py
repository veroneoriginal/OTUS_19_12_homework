# tests/integration/test_scoring_service.py

import json
from scoring.service import get_score, get_interests


class FakeStore:
    def __init__(self):
        self.cache = {}
        self.storage = {}

    def cache_get(self, key):
        return self.cache.get(key)

    def cache_set(self, key, value, timeout):
        self.cache[key] = value

    def get(self, key):
        return self.storage.get(key)

def test_get_score_from_cache():
    store = FakeStore()
    store.cache["uid:test"] = 5.0

    score = get_score(
        store,
        phone="1",
        email="a@b.c",
        first_name="t",
        last_name="e",
    )

    assert isinstance(score, float)


def test_get_score_calculates_and_caches():
    store = FakeStore()
    score = get_score(
        store,
        phone="123",
        email="a@b.c",
    )

    assert score == 3.0
    assert len(store.cache) == 1


def test_get_interests_returns_list():
    store = FakeStore()
    store.storage["i:42"] = json.dumps(["cars", "music"])
    result = get_interests(store, "42")
    assert result == ["cars", "music"]


def test_get_interests_empty():
    store = FakeStore()
    result = get_interests(store, "404")
    assert result == []
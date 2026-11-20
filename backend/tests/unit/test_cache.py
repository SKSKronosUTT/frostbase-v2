from app.core import cache


def test_memory_cache_set_get_delete(monkeypatch):
    monkeypatch.setattr(cache, "_cache", cache.MemoryTTLCache())
    cache.cache_set("demo", "valor", 60)
    assert cache.cache_get("demo") == "valor"

    cache.cache_delete("demo")
    assert cache.cache_get("demo") is None


def test_memory_cache_expires(monkeypatch):
    memory = cache.MemoryTTLCache()
    now = 1000.0
    monkeypatch.setattr(cache.time, "monotonic", lambda: now)
    memory.set("key", "value", 5)
    assert memory.get("key") == "value"

    now = 1006.0
    assert memory.get("key") is None


def test_memory_cache_clear_and_delete_prefix(monkeypatch):
    memory = cache.MemoryTTLCache()
    memory.set("a:1", "x", 60)
    memory.set("a:2", "y", 60)
    memory.set("b:1", "z", 60)
    memory.delete("a:")
    assert memory.get("a:1") is None
    assert memory.get("b:1") == "z"
    memory.clear()
    assert memory.get("b:1") is None


def test_cache_errors_do_not_raise(monkeypatch):
    class Broken:
        def get(self, key):
            raise RuntimeError("boom")

        def set(self, key, value, ttl):
            raise RuntimeError("boom")

        def delete(self, prefix):
            raise RuntimeError("boom")

        def clear(self):
            raise RuntimeError("boom")

    monkeypatch.setattr(cache, "_cache", Broken())
    assert cache.cache_get("x") is None
    cache.cache_set("x", "y", 1)
    cache.cache_delete("x")
    cache.reset_cache()

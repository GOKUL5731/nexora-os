"""
In-memory caching layer with TTL support
Used for caching frequent queries, LLM responses, and vision results
"""
import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass(slots=True)
class CacheEntry:
    value: Any
    timestamp: float
    ttl: float  # Time to live in seconds


class Cache:
    """Simple in-memory cache with TTL support"""
    
    def __init__(self, default_ttl: int = 300, max_size: int = 1000) -> None:
        self.default_ttl = default_ttl
        self.max_size = max_size
        self._cache: dict[str, CacheEntry] = {}
        self._hits = 0
        self._misses = 0
    
    def _generate_key(self, *args: Any, **kwargs: Any) -> str:
        """Generate a cache key from arguments"""
        key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
        return hashlib.sha256(key_data.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value from cache"""
        entry = self._cache.get(key)
        if entry is None:
            self._misses += 1
            return None
        
        # Check if entry has expired
        if time.time() - entry.timestamp > entry.ttl:
            del self._cache[key]
            self._misses += 1
            return None
        
        self._hits += 1
        return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Set a value in cache"""
        if ttl is None:
            ttl = self.default_ttl
        
        # Evict oldest entries if cache is full
        if len(self._cache) >= self.max_size and key not in self._cache:
            self._evict_oldest()
        
        self._cache[key] = CacheEntry(value, time.time(), ttl)
    
    def delete(self, key: str) -> bool:
        """Delete a value from cache"""
        if key in self._cache:
            del self._cache[key]
            return True
        return False
    
    def clear(self) -> None:
        """Clear all cache entries"""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
    
    def _evict_oldest(self) -> None:
        """Evict the oldest entry from cache"""
        if not self._cache:
            return
        
        oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k].timestamp)
        del self._cache[oldest_key]
    
    def cleanup_expired(self) -> int:
        """Remove all expired entries, return count of removed entries"""
        now = time.time()
        expired_keys = [
            key for key, entry in self._cache.items()
            if now - entry.timestamp > entry.ttl
        ]
        for key in expired_keys:
            del self._cache[key]
        return len(expired_keys)
    
    def stats(self) -> dict[str, Any]:
        """Get cache statistics"""
        total_requests = self._hits + self._misses
        hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0.0
        
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 2),
            "default_ttl": self.default_ttl,
        }
    
    def memoize(self, ttl: Optional[float] = None):
        """Decorator to memoize function results"""
        def decorator(func: Callable):
            def wrapper(*args, **kwargs):
                key = self._generate_key(func.__name__, *args, **kwargs)
                cached = self.get(key)
                if cached is not None:
                    return cached
                
                result = func(*args, **kwargs)
                self.set(key, result, ttl)
                return result
            return wrapper
        return decorator


# Global cache instances for different use cases
memory_cache = Cache(default_ttl=60, max_size=500)  # Cache memory queries for 1 minute
llm_cache = Cache(default_ttl=300, max_size=200)   # Cache LLM responses for 5 minutes
vision_cache = Cache(default_ttl=30, max_size=100)  # Cache vision results for 30 seconds

"""
Rate limiting module for API endpoints
Provides token bucket and sliding window rate limiting strategies
"""
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class RateLimitInfo:
    """Information about rate limit status"""
    allowed: bool
    remaining: int
    reset_time: float
    limit: int
    window: float


class TokenBucket:
    """Token bucket rate limiter"""
    
    def __init__(self, rate: float, capacity: int) -> None:
        """
        Initialize token bucket
        
        Args:
            rate: Tokens per second
            capacity: Maximum number of tokens
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last_update = time.time()
    
    def consume(self, tokens: int = 1) -> bool:
        """
        Consume tokens from the bucket
        
        Args:
            tokens: Number of tokens to consume
            
        Returns:
            True if tokens were consumed, False if not enough tokens
        """
        now = time.time()
        elapsed = now - self.last_update
        
        # Add tokens based on elapsed time
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_update = now
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
    
    def get_info(self) -> RateLimitInfo:
        """Get current rate limit information"""
        return RateLimitInfo(
            allowed=self.tokens >= 1,
            remaining=int(self.tokens),
            reset_time=self.last_update + (self.capacity - self.tokens) / self.rate,
            limit=int(self.capacity),
            window=self.capacity / self.rate
        )


class SlidingWindow:
    """Sliding window rate limiter"""
    
    def __init__(self, limit: int, window: float) -> None:
        """
        Initialize sliding window
        
        Args:
            limit: Maximum number of requests
            window: Time window in seconds
        """
        self.limit = limit
        self.window = window
        self.requests: deque[float] = deque()
    
    def allow(self) -> bool:
        """
        Check if request is allowed
        
        Returns:
            True if request is allowed, False otherwise
        """
        now = time.time()
        
        # Remove old requests outside the window
        while self.requests and now - self.requests[0] > self.window:
            self.requests.popleft()
        
        if len(self.requests) < self.limit:
            self.requests.append(now)
            return True
        return False
    
    def get_info(self) -> RateLimitInfo:
        """Get current rate limit information"""
        now = time.time()
        
        # Remove old requests outside the window
        while self.requests and now - self.requests[0] > self.window:
            self.requests.popleft()
        
        remaining = self.limit - len(self.requests)
        reset_time = self.requests[0] + self.window if self.requests else now
        
        return RateLimitInfo(
            allowed=remaining > 0,
            remaining=remaining,
            reset_time=reset_time,
            limit=self.limit,
            window=self.window
        )


class RateLimiter:
    """Rate limiter with multiple strategies"""
    
    def __init__(self, default_limit: int = 100, default_window: float = 60.0) -> None:
        """
        Initialize rate limiter
        
        Args:
            default_limit: Default request limit
            default_window: Default time window in seconds
        """
        self.default_limit = default_limit
        custom_window = default_window
        
        # Use sliding window by default
        self.buckets: defaultdict[str, SlidingWindow] = defaultdict(
            lambda: SlidingWindow(custom_window, custom_window)
        )
    
    def is_allowed(self, identifier: str, limit: Optional[int] = None, window: Optional[float] = None) -> bool:
        """
        Check if request is allowed for identifier
        
        Args:
            identifier: Unique identifier (e.g., IP address, API key)
            limit: Custom limit (optional)
            window: Custom window (optional)
            
        Returns:
            True if request is allowed, False otherwise
        """
        if limit is not None or window is not None:
            # Use custom settings
            key = f"{identifier}:{limit}:{window}"
            if key not in self.buckets:
                self.buckets[key] = SlidingWindow(limit or self.default_limit, window or 60.0)
            return self.buckets[key].allow()
        
        return self.buckets[identifier].allow()
    
    def get_info(self, identifier: str, limit: Optional[int] = None, window: Optional[float] = None) -> RateLimitInfo:
        """
        Get rate limit information for identifier
        
        Args:
            identifier: Unique identifier
            limit: Custom limit (optional)
            window: Custom window (optional)
            
        Returns:
            RateLimitInfo with current status
        """
        if limit is not None or window is not None:
            key = f"{identifier}:{limit}:{window}"
            if key not in self.buckets:
                self.buckets[key] = SlidingWindow(limit or self.default_limit, window or 60.0)
            return self.buckets[key].get_info()
        
        return self.buckets[identifier].get_info()
    
    def reset(self, identifier: str) -> None:
        """Reset rate limit for identifier"""
        if identifier in self.buckets:
            del self.buckets[identifier]
    
    def cleanup(self, max_age: float = 3600.0) -> int:
        """
        Clean up old rate limit entries
        
        Args:
            max_age: Maximum age in seconds
            
        Returns:
            Number of entries cleaned up
        """
        now = time.time()
        to_remove = []
        
        for key, bucket in self.buckets.items():
            info = bucket.get_info()
            if now - info.reset_time > max_age:
                to_remove.append(key)
        
        for key in to_remove:
            del self.buckets[key]
        
        return len(to_remove)


# Global rate limiter instance
global_rate_limiter = RateLimiter(default_limit=100, default_window=60.0)


def check_rate_limit(identifier: str, limit: int = 100, window: float = 60.0) -> tuple[bool, RateLimitInfo]:
    """
    Check rate limit for identifier
    
    Args:
        identifier: Unique identifier (e.g., IP address)
        limit: Request limit
        window: Time window in seconds
        
    Returns:
        Tuple of (is_allowed, rate_limit_info)
    """
    is_allowed = global_rate_limiter.is_allowed(identifier, limit, window)
    info = global_rate_limiter.get_info(identifier, limit, window)
    return is_allowed, info

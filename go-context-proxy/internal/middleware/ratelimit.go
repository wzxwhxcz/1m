package middleware

import (
	"net/http"
	"time"

	"github.com/wzxwhxcz/go-context-proxy/internal/storage"
)

// RateLimiter implements Redis-based sliding window rate limiting
type RateLimiter struct {
	redisStore  *storage.RedisStore
	windowSec   int
	maxRequests int
}

func NewRateLimiter(redisStore *storage.RedisStore, windowSec, maxRequests int) *RateLimiter {
	return &RateLimiter{
		redisStore:  redisStore,
		windowSec:   windowSec,
		maxRequests: maxRequests,
	}
}

func (rl *RateLimiter) Handler(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Skip rate limiting for health and metrics endpoints
		if r.URL.Path == "/health" || r.URL.Path == "/metrics" {
			next.ServeHTTP(w, r)
			return
		}

		// Get user ID from context (set by auth middleware)
		userID, ok := r.Context().Value("userID").(int)
		if !ok {
			http.Error(w, `{"error":"User not authenticated"}`, http.StatusUnauthorized)
			return
		}

		// Check rate limit using Redis sliding window
		allowed, err := rl.redisStore.CheckRateLimit(r.Context(), userID, rl.windowSec, rl.maxRequests)
		if err != nil {
			// Log error but allow request (fail-open for availability)
			next.ServeHTTP(w, r)
			return
		}

		if !allowed {
			// Get remaining quota for response header
			remaining, _ := rl.redisStore.GetRateLimitRemaining(r.Context(), userID, rl.windowSec, rl.maxRequests)
			
			w.Header().Set("X-RateLimit-Limit", string(rune(rl.maxRequests)))
			w.Header().Set("X-RateLimit-Remaining", string(rune(remaining)))
			w.Header().Set("X-RateLimit-Reset", string(rune(time.Now().Unix()+int64(rl.windowSec))))
			
			http.Error(w, `{"error":"Rate limit exceeded"}`, http.StatusTooManyRequests)
			return
		}

		next.ServeHTTP(w, r)
	})
}

// Mock version for testing without Redis
type MockRateLimiter struct {
	requests    map[int][]time.Time
	windowSec   int
	maxRequests int
}

func NewMockRateLimiter(windowSec, maxRequests int) *MockRateLimiter {
	return &MockRateLimiter{
		requests:    make(map[int][]time.Time),
		windowSec:   windowSec,
		maxRequests: maxRequests,
	}
}

func (rl *MockRateLimiter) Handler(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/health" || r.URL.Path == "/metrics" {
			next.ServeHTTP(w, r)
			return
		}

		userID, ok := r.Context().Value("userID").(int)
		if !ok {
			next.ServeHTTP(w, r)
			return
		}

		now := time.Now()
		windowStart := now.Add(-time.Duration(rl.windowSec) * time.Second)

		// Clean old requests
		var validRequests []time.Time
		for _, t := range rl.requests[userID] {
			if t.After(windowStart) {
				validRequests = append(validRequests, t)
			}
		}

		// Check limit
		if len(validRequests) >= rl.maxRequests {
			http.Error(w, `{"error":"Rate limit exceeded"}`, http.StatusTooManyRequests)
			return
		}

		// Add current request
		validRequests = append(validRequests, now)
		rl.requests[userID] = validRequests

		next.ServeHTTP(w, r)
	})
}

package middleware

import (
	"context"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/wzxwhxcz/go-context-proxy/internal/storage"
)

// AuthMiddleware validates Service Key using PostgreSQL + Redis cache
type AuthMiddleware struct {
	pgStore    *storage.PostgresStore
	redisStore *storage.RedisStore
}

func NewAuthMiddleware(pgStore *storage.PostgresStore, redisStore *storage.RedisStore) *AuthMiddleware {
	return &AuthMiddleware{
		pgStore:    pgStore,
		redisStore: redisStore,
	}
}

func (m *AuthMiddleware) Handler(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Skip auth for health and metrics endpoints
		if r.URL.Path == "/health" || r.URL.Path == "/metrics" {
			next.ServeHTTP(w, r)
			return
		}

		// Extract service key from URL path
		serviceKey := chi.URLParam(r, "serviceKey")
		if serviceKey == "" {
			http.Error(w, `{"error":"Missing service key"}`, http.StatusUnauthorized)
			return
		}

		ctx := r.Context()

		// Try Redis cache first
		var userID int
		var user *storage.User
		
		cachedUserID, err := m.redisStore.GetCachedUser(ctx, serviceKey)
		if err == nil {
			userID = cachedUserID
		} else {
			// Cache miss, query PostgreSQL
			user, err = m.pgStore.GetUserByServiceKey(ctx, serviceKey)
			if err != nil {
				http.Error(w, `{"error":"Invalid service key"}`, http.StatusUnauthorized)
				return
			}

			// Check if user is active
			if !user.IsActive {
				http.Error(w, `{"error":"User account disabled"}`, http.StatusForbidden)
				return
			}

			// Check quota
			if user.QuotaUsedToday >= user.QuotaDaily {
				http.Error(w, `{"error":"Daily quota exceeded"}`, http.StatusTooManyRequests)
				return
			}

			userID = user.ID

			// Cache user for 1 hour
			m.redisStore.CacheUser(ctx, serviceKey, userID, time.Hour)
		}

		// Add user info to context
		ctx = context.WithValue(ctx, "userID", userID)
		ctx = context.WithValue(ctx, "serviceKey", serviceKey)

		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

// Mock version for testing without DB
type MockUserStore struct {
	users map[string]int
}

func NewMockUserStore() *MockUserStore {
	return &MockUserStore{
		users: map[string]int{
			"sk-test123": 1,
			"sk-demo456": 2,
		},
	}
}

func (s *MockUserStore) ValidateServiceKey(ctx context.Context, serviceKey string) (int, bool) {
	userID, exists := s.users[serviceKey]
	return userID, exists
}

type MockAuthMiddleware struct {
	store *MockUserStore
}

func NewMockAuthMiddleware(store *MockUserStore) *MockAuthMiddleware {
	return &MockAuthMiddleware{store: store}
}

func (m *MockAuthMiddleware) Handler(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/health" || r.URL.Path == "/metrics" {
			next.ServeHTTP(w, r)
			return
		}

		serviceKey := chi.URLParam(r, "serviceKey")
		if serviceKey == "" {
			http.Error(w, `{"error":"Missing service key"}`, http.StatusUnauthorized)
			return
		}

		userID, isValid := m.store.ValidateServiceKey(r.Context(), serviceKey)
		if !isValid {
			http.Error(w, `{"error":"Invalid service key"}`, http.StatusUnauthorized)
			return
		}

		ctx := context.WithValue(r.Context(), "userID", userID)
		ctx = context.WithValue(ctx, "serviceKey", serviceKey)

		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

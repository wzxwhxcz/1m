package storage

import (
	"context"
	"fmt"
	"time"

	"github.com/go-redis/redis/v8"
)

type RedisStore struct {
	client *redis.Client
}

func NewRedisStore(addr, password string, db int) (*RedisStore, error) {
	client := redis.NewClient(&redis.Options{
		Addr:         addr,
		Password:     password,
		DB:           db,
		PoolSize:     10,
		MinIdleConns: 5,
	})

	// Test connection
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := client.Ping(ctx).Err(); err != nil {
		return nil, fmt.Errorf("failed to connect to redis: %w", err)
	}

	return &RedisStore{client: client}, nil
}

func (s *RedisStore) Close() error {
	return s.client.Close()
}

// Rate limiting using sliding window algorithm

func (s *RedisStore) CheckRateLimit(ctx context.Context, userID int, windowSec int, maxRequests int) (bool, error) {
	key := fmt.Sprintf("ratelimit:%d:%ds", userID, windowSec)
	now := time.Now().Unix()
	windowStart := now - int64(windowSec)

	// Use pipeline for atomic operations
	pipe := s.client.Pipeline()

	// Remove expired entries
	pipe.ZRemRangeByScore(ctx, key, "0", fmt.Sprintf("%d", windowStart))

	// Count entries in current window
	countCmd := pipe.ZCard(ctx, key)

	// Execute pipeline
	if _, err := pipe.Exec(ctx); err != nil {
		return false, fmt.Errorf("failed to check rate limit: %w", err)
	}

	count := countCmd.Val()

	// Check if limit exceeded
	if count >= int64(maxRequests) {
		return false, nil
	}

	// Add current request
	requestID := fmt.Sprintf("%d-%d", now, time.Now().UnixNano())
	if err := s.client.ZAdd(ctx, key, &redis.Z{
		Score:  float64(now),
		Member: requestID,
	}).Err(); err != nil {
		return false, fmt.Errorf("failed to add request to rate limit: %w", err)
	}

	// Set expiration (2x window for safety)
	s.client.Expire(ctx, key, time.Duration(windowSec*2)*time.Second)

	return true, nil
}

func (s *RedisStore) GetRateLimitRemaining(ctx context.Context, userID int, windowSec int, maxRequests int) (int, error) {
	key := fmt.Sprintf("ratelimit:%d:%ds", userID, windowSec)
	now := time.Now().Unix()
	windowStart := now - int64(windowSec)

	// Remove expired entries and count
	pipe := s.client.Pipeline()
	pipe.ZRemRangeByScore(ctx, key, "0", fmt.Sprintf("%d", windowStart))
	countCmd := pipe.ZCard(ctx, key)

	if _, err := pipe.Exec(ctx); err != nil {
		return 0, fmt.Errorf("failed to get rate limit remaining: %w", err)
	}

	count := int(countCmd.Val())
	remaining := maxRequests - count
	if remaining < 0 {
		remaining = 0
	}

	return remaining, nil
}

// User caching

func (s *RedisStore) CacheUser(ctx context.Context, serviceKey string, userID int, ttl time.Duration) error {
	key := fmt.Sprintf("user:cache:%s", serviceKey)
	if err := s.client.Set(ctx, key, userID, ttl).Err(); err != nil {
		return fmt.Errorf("failed to cache user: %w", err)
	}
	return nil
}

func (s *RedisStore) GetCachedUser(ctx context.Context, serviceKey string) (int, error) {
	key := fmt.Sprintf("user:cache:%s", serviceKey)
	val, err := s.client.Get(ctx, key).Int()
	if err == redis.Nil {
		return 0, fmt.Errorf("user not in cache")
	}
	if err != nil {
		return 0, fmt.Errorf("failed to get cached user: %w", err)
	}
	return val, nil
}

// Real-time statistics (1-minute windows)

func (s *RedisStore) IncrementStat(ctx context.Context, statName string) error {
	key := fmt.Sprintf("stats:%s:1m", statName)
	pipe := s.client.Pipeline()
	pipe.Incr(ctx, key)
	pipe.Expire(ctx, key, 2*time.Minute) // 2x for safety
	_, err := pipe.Exec(ctx)
	return err
}

func (s *RedisStore) GetStat(ctx context.Context, statName string) (int64, error) {
	key := fmt.Sprintf("stats:%s:1m", statName)
	val, err := s.client.Get(ctx, key).Int64()
	if err == redis.Nil {
		return 0, nil
	}
	return val, err
}

// Embedding cache (for Python recall service)

func (s *RedisStore) CacheEmbedding(ctx context.Context, text string, embedding []float32, ttl time.Duration) error {
	// Store as JSON or msgpack for efficiency
	// For simplicity, we'll skip implementation here as Python service handles this
	return nil
}

// Health check

func (s *RedisStore) Ping(ctx context.Context) error {
	return s.client.Ping(ctx).Err()
}

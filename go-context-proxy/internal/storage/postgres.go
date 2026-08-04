package storage

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	_ "github.com/lib/pq"
)

type User struct {
	ID            int       `json:"id"`
	ServiceKey    string    `json:"service_key"`
	Email         string    `json:"email"`
	Plan          string    `json:"plan"`
	QuotaDaily    int       `json:"quota_daily"`
	QuotaUsedToday int      `json:"quota_used_today"`
	IsActive      bool      `json:"is_active"`
	CreatedAt     time.Time `json:"created_at"`
	UpdatedAt     time.Time `json:"updated_at"`
}

type RequestLog struct {
	ID               int64     `json:"id"`
	UserID           *int      `json:"user_id"`
	ServiceKey       string    `json:"service_key"`
	UpstreamURL      string    `json:"upstream_url"`
	Method           string    `json:"method"`
	InputTokens      int       `json:"input_tokens"`
	OutputTokens     int       `json:"output_tokens"`
	RecallTriggered  bool      `json:"recall_triggered"`
	RecallLatencyMs  int       `json:"recall_latency_ms"`
	ProxyLatencyMs   int       `json:"proxy_latency_ms"`
	TotalLatencyMs   int       `json:"total_latency_ms"`
	Status           string    `json:"status"`
	StatusCode       int       `json:"status_code"`
	ErrorMessage     string    `json:"error_message"`
	CreatedAt        time.Time `json:"created_at"`
}

type PostgresStore struct {
	db *sql.DB
}

func NewPostgresStore(connectionString string) (*PostgresStore, error) {
	db, err := sql.Open("postgres", connectionString)
	if err != nil {
		return nil, fmt.Errorf("failed to open database: %w", err)
	}

	// Connection pool settings
	db.SetMaxOpenConns(25)
	db.SetMaxIdleConns(10)
	db.SetConnMaxLifetime(time.Hour)

	// Test connection
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := db.PingContext(ctx); err != nil {
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}

	return &PostgresStore{db: db}, nil
}

func (s *PostgresStore) Close() error {
	return s.db.Close()
}

// User operations

func (s *PostgresStore) GetUserByServiceKey(ctx context.Context, serviceKey string) (*User, error) {
	query := `
		SELECT id, service_key, email, plan, quota_daily, quota_used_today, 
		       is_active, created_at, updated_at
		FROM users
		WHERE service_key = $1
	`

	var user User
	err := s.db.QueryRowContext(ctx, query, serviceKey).Scan(
		&user.ID, &user.ServiceKey, &user.Email, &user.Plan,
		&user.QuotaDaily, &user.QuotaUsedToday, &user.IsActive,
		&user.CreatedAt, &user.UpdatedAt,
	)

	if err == sql.ErrNoRows {
		return nil, fmt.Errorf("user not found")
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get user: %w", err)
	}

	return &user, nil
}

func (s *PostgresStore) CreateUser(ctx context.Context, user *User) error {
	query := `
		INSERT INTO users (service_key, email, plan, quota_daily)
		VALUES ($1, $2, $3, $4)
		RETURNING id, created_at, updated_at
	`

	err := s.db.QueryRowContext(ctx, query,
		user.ServiceKey, user.Email, user.Plan, user.QuotaDaily,
	).Scan(&user.ID, &user.CreatedAt, &user.UpdatedAt)

	if err != nil {
		return fmt.Errorf("failed to create user: %w", err)
	}

	return nil
}

func (s *PostgresStore) UpdateUser(ctx context.Context, user *User) error {
	query := `
		UPDATE users
		SET email = $2, plan = $3, quota_daily = $4, is_active = $5
		WHERE id = $1
	`

	_, err := s.db.ExecContext(ctx, query,
		user.ID, user.Email, user.Plan, user.QuotaDaily, user.IsActive,
	)

	if err != nil {
		return fmt.Errorf("failed to update user: %w", err)
	}

	return nil
}

func (s *PostgresStore) IncrementQuota(ctx context.Context, userID int) error {
	query := `
		UPDATE users
		SET quota_used_today = quota_used_today + 1
		WHERE id = $1
	`

	_, err := s.db.ExecContext(ctx, query, userID)
	if err != nil {
		return fmt.Errorf("failed to increment quota: %w", err)
	}

	return nil
}

func (s *PostgresStore) ListUsers(ctx context.Context, limit, offset int) ([]*User, error) {
	query := `
		SELECT id, service_key, email, plan, quota_daily, quota_used_today,
		       is_active, created_at, updated_at
		FROM users
		ORDER BY created_at DESC
		LIMIT $1 OFFSET $2
	`

	rows, err := s.db.QueryContext(ctx, query, limit, offset)
	if err != nil {
		return nil, fmt.Errorf("failed to list users: %w", err)
	}
	defer rows.Close()

	var users []*User
	for rows.Next() {
		var user User
		err := rows.Scan(
			&user.ID, &user.ServiceKey, &user.Email, &user.Plan,
			&user.QuotaDaily, &user.QuotaUsedToday, &user.IsActive,
			&user.CreatedAt, &user.UpdatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan user: %w", err)
		}
		users = append(users, &user)
	}

	return users, nil
}

// Request log operations

func (s *PostgresStore) CreateRequestLog(ctx context.Context, log *RequestLog) error {
	query := `
		INSERT INTO request_logs (
			user_id, service_key, upstream_url, method, input_tokens, output_tokens,
			recall_triggered, recall_latency_ms, proxy_latency_ms, total_latency_ms,
			status, status_code, error_message
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
		RETURNING id, created_at
	`

	err := s.db.QueryRowContext(ctx, query,
		log.UserID, log.ServiceKey, log.UpstreamURL, log.Method,
		log.InputTokens, log.OutputTokens, log.RecallTriggered,
		log.RecallLatencyMs, log.ProxyLatencyMs, log.TotalLatencyMs,
		log.Status, log.StatusCode, log.ErrorMessage,
	).Scan(&log.ID, &log.CreatedAt)

	if err != nil {
		return fmt.Errorf("failed to create request log: %w", err)
	}

	return nil
}

func (s *PostgresStore) GetRequestLogs(ctx context.Context, userID *int, limit, offset int) ([]*RequestLog, error) {
	var query string
	var args []interface{}

	if userID != nil {
		query = `
			SELECT id, user_id, service_key, upstream_url, method, input_tokens, output_tokens,
			       recall_triggered, recall_latency_ms, proxy_latency_ms, total_latency_ms,
			       status, status_code, error_message, created_at
			FROM request_logs
			WHERE user_id = $1
			ORDER BY created_at DESC
			LIMIT $2 OFFSET $3
		`
		args = []interface{}{*userID, limit, offset}
	} else {
		query = `
			SELECT id, user_id, service_key, upstream_url, method, input_tokens, output_tokens,
			       recall_triggered, recall_latency_ms, proxy_latency_ms, total_latency_ms,
			       status, status_code, error_message, created_at
			FROM request_logs
			ORDER BY created_at DESC
			LIMIT $1 OFFSET $2
		`
		args = []interface{}{limit, offset}
	}

	rows, err := s.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("failed to get request logs: %w", err)
	}
	defer rows.Close()

	var logs []*RequestLog
	for rows.Next() {
		var log RequestLog
		err := rows.Scan(
			&log.ID, &log.UserID, &log.ServiceKey, &log.UpstreamURL, &log.Method,
			&log.InputTokens, &log.OutputTokens, &log.RecallTriggered,
			&log.RecallLatencyMs, &log.ProxyLatencyMs, &log.TotalLatencyMs,
			&log.Status, &log.StatusCode, &log.ErrorMessage, &log.CreatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan request log: %w", err)
		}
		logs = append(logs, &log)
	}

	return logs, nil
}

// Statistics

func (s *PostgresStore) GetDailyStats(ctx context.Context, date time.Time) (map[string]interface{}, error) {
	startOfDay := time.Date(date.Year(), date.Month(), date.Day(), 0, 0, 0, 0, date.Location())
	endOfDay := startOfDay.Add(24 * time.Hour)

	query := `
		SELECT 
			COUNT(*) as total_requests,
			COUNT(CASE WHEN status = 'success' THEN 1 END) as successful_requests,
			COUNT(CASE WHEN recall_triggered = true THEN 1 END) as recall_triggered_count,
			AVG(total_latency_ms) as avg_latency_ms,
			SUM(input_tokens) as total_input_tokens,
			SUM(output_tokens) as total_output_tokens
		FROM request_logs
		WHERE created_at >= $1 AND created_at < $2
	`

	var stats struct {
		TotalRequests         int
		SuccessfulRequests    int
		RecallTriggeredCount  int
		AvgLatencyMs          float64
		TotalInputTokens      int64
		TotalOutputTokens     int64
	}

	err := s.db.QueryRowContext(ctx, query, startOfDay, endOfDay).Scan(
		&stats.TotalRequests, &stats.SuccessfulRequests, &stats.RecallTriggeredCount,
		&stats.AvgLatencyMs, &stats.TotalInputTokens, &stats.TotalOutputTokens,
	)

	if err != nil {
		return nil, fmt.Errorf("failed to get daily stats: %w", err)
	}

	successRate := 0.0
	if stats.TotalRequests > 0 {
		successRate = float64(stats.SuccessfulRequests) / float64(stats.TotalRequests) * 100
	}

	return map[string]interface{}{
		"total_requests":           stats.TotalRequests,
		"successful_requests":      stats.SuccessfulRequests,
		"success_rate":             successRate,
		"recall_triggered_count":   stats.RecallTriggeredCount,
		"avg_latency_ms":           stats.AvgLatencyMs,
		"total_input_tokens":       stats.TotalInputTokens,
		"total_output_tokens":      stats.TotalOutputTokens,
	}, nil
}

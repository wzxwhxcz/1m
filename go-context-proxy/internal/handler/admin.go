package handler

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"strconv"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/golang-jwt/jwt/v5"
	"github.com/wzxwhxcz/go-context-proxy/internal/model"
	"github.com/wzxwhxcz/go-context-proxy/internal/storage"
	"golang.org/x/crypto/bcrypt"
)

var jwtSecret = []byte("context-proxy-secret-key-change-in-production")

type AdminHandler struct {
	pgStore *storage.PostgresStore
}

func NewAdminHandler(pgStore *storage.PostgresStore) *AdminHandler {
	return &AdminHandler{pgStore: pgStore}
}

// Login - 管理员登录
func (h *AdminHandler) Login(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Username string `json:"username"`
		Password string `json:"password"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		respondJSON(w, http.StatusBadRequest, map[string]string{"error": "Invalid request"})
		return
	}

	// 查询管理员
	var admin struct {
		ID           int
		Username     string
		PasswordHash string
	}

	query := `SELECT id, username, password_hash FROM admins WHERE username = $1`
	err := h.pgStore.DB.QueryRow(query, req.Username).Scan(&admin.ID, &admin.Username, &admin.PasswordHash)
	
	if err == sql.ErrNoRows {
		respondJSON(w, http.StatusUnauthorized, map[string]string{"error": "用户名或密码错误"})
		return
	}
	if err != nil {
		respondJSON(w, http.StatusInternalServerError, map[string]string{"error": "Database error"})
		return
	}

	// 验证密码
	if err := bcrypt.CompareHashAndPassword([]byte(admin.PasswordHash), []byte(req.Password)); err != nil {
		respondJSON(w, http.StatusUnauthorized, map[string]string{"error": "用户名或密码错误"})
		return
	}

	// 生成JWT
	token := jwt.NewWithClaims(jwt.SigningMethodHS256, jwt.MapClaims{
		"id":       admin.ID,
		"username": admin.Username,
		"exp":      time.Now().Add(24 * time.Hour).Unix(),
	})

	tokenString, err := token.SignedString(jwtSecret)
	if err != nil {
		respondJSON(w, http.StatusInternalServerError, map[string]string{"error": "Token generation failed"})
		return
	}

	respondJSON(w, http.StatusOK, map[string]interface{}{
		"token": tokenString,
		"user": map[string]interface{}{
			"id":       admin.ID,
			"username": admin.Username,
		},
	})
}

// ListUsers - 获取用户列表
func (h *AdminHandler) ListUsers(w http.ResponseWriter, r *http.Request) {
	page, _ := strconv.Atoi(r.URL.Query().Get("page"))
	pageSize, _ := strconv.Atoi(r.URL.Query().Get("page_size"))
	
	if page < 1 {
		page = 1
	}
	if pageSize < 1 || pageSize > 100 {
		pageSize = 20
	}

	offset := (page - 1) * pageSize

	// 查询用户列表
	query := `
		SELECT id, service_key, email, plan, quota_daily, quota_used_today, is_active, created_at, updated_at
		FROM users
		ORDER BY created_at DESC
		LIMIT $1 OFFSET $2
	`

	rows, err := h.pgStore.DB.Query(query, pageSize, offset)
	if err != nil {
		respondJSON(w, http.StatusInternalServerError, map[string]string{"error": "Database error"})
		return
	}
	defer rows.Close()

	users := []model.User{}
	for rows.Next() {
		var u model.User
		if err := rows.Scan(&u.ID, &u.ServiceKey, &u.Email, &u.Plan, &u.QuotaDaily, 
			&u.QuotaUsedToday, &u.IsActive, &u.CreatedAt, &u.UpdatedAt); err != nil {
			continue
		}
		users = append(users, u)
	}

	// 查询总数
	var total int
	h.pgStore.DB.QueryRow("SELECT COUNT(*) FROM users").Scan(&total)

	respondJSON(w, http.StatusOK, map[string]interface{}{
		"users": users,
		"total": total,
	})
}

// GetUser - 获取单个用户详情
func (h *AdminHandler) GetUser(w http.ResponseWriter, r *http.Request) {
	id, err := strconv.Atoi(chi.URLParam(r, "id"))
	if err != nil {
		respondJSON(w, http.StatusBadRequest, map[string]string{"error": "Invalid user ID"})
		return
	}

	var u model.User
	query := `
		SELECT id, service_key, email, plan, quota_daily, quota_used_today, is_active, created_at, updated_at
		FROM users WHERE id = $1
	`

	err = h.pgStore.DB.QueryRow(query, id).Scan(
		&u.ID, &u.ServiceKey, &u.Email, &u.Plan, &u.QuotaDaily,
		&u.QuotaUsedToday, &u.IsActive, &u.CreatedAt, &u.UpdatedAt)

	if err == sql.ErrNoRows {
		respondJSON(w, http.StatusNotFound, map[string]string{"error": "User not found"})
		return
	}
	if err != nil {
		respondJSON(w, http.StatusInternalServerError, map[string]string{"error": "Database error"})
		return
	}

	respondJSON(w, http.StatusOK, u)
}

// CreateUser - 创建用户
func (h *AdminHandler) CreateUser(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Email      string `json:"email"`
		Plan       string `json:"plan"`
		QuotaDaily int    `json:"quota_daily"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		respondJSON(w, http.StatusBadRequest, map[string]string{"error": "Invalid request"})
		return
	}

	// 生成 service key
	serviceKey := generateServiceKey()

	query := `
		INSERT INTO users (service_key, email, plan, quota_daily)
		VALUES ($1, $2, $3, $4)
		RETURNING id, service_key, email, plan, quota_daily, quota_used_today, is_active, created_at, updated_at
	`

	var u model.User
	err := h.pgStore.DB.QueryRow(query, serviceKey, req.Email, req.Plan, req.QuotaDaily).Scan(
		&u.ID, &u.ServiceKey, &u.Email, &u.Plan, &u.QuotaDaily,
		&u.QuotaUsedToday, &u.IsActive, &u.CreatedAt, &u.UpdatedAt)

	if err != nil {
		respondJSON(w, http.StatusInternalServerError, map[string]string{"error": "Failed to create user"})
		return
	}

	respondJSON(w, http.StatusCreated, u)
}

// UpdateUser - 更新用户
func (h *AdminHandler) UpdateUser(w http.ResponseWriter, r *http.Request) {
	id, err := strconv.Atoi(chi.URLParam(r, "id"))
	if err != nil {
		respondJSON(w, http.StatusBadRequest, map[string]string{"error": "Invalid user ID"})
		return
	}

	var req struct {
		Email      *string `json:"email"`
		Plan       *string `json:"plan"`
		QuotaDaily *int    `json:"quota_daily"`
		IsActive   *bool   `json:"is_active"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		respondJSON(w, http.StatusBadRequest, map[string]string{"error": "Invalid request"})
		return
	}

	query := `
		UPDATE users 
		SET email = COALESCE($1, email),
		    plan = COALESCE($2, plan),
		    quota_daily = COALESCE($3, quota_daily),
		    is_active = COALESCE($4, is_active),
		    updated_at = NOW()
		WHERE id = $5
		RETURNING id, service_key, email, plan, quota_daily, quota_used_today, is_active, created_at, updated_at
	`

	var u model.User
	err = h.pgStore.DB.QueryRow(query, req.Email, req.Plan, req.QuotaDaily, req.IsActive, id).Scan(
		&u.ID, &u.ServiceKey, &u.Email, &u.Plan, &u.QuotaDaily,
		&u.QuotaUsedToday, &u.IsActive, &u.CreatedAt, &u.UpdatedAt)

	if err == sql.ErrNoRows {
		respondJSON(w, http.StatusNotFound, map[string]string{"error": "User not found"})
		return
	}
	if err != nil {
		respondJSON(w, http.StatusInternalServerError, map[string]string{"error": "Failed to update user"})
		return
	}

	respondJSON(w, http.StatusOK, u)
}

// DeleteUser - 删除用户
func (h *AdminHandler) DeleteUser(w http.ResponseWriter, r *http.Request) {
	id, err := strconv.Atoi(chi.URLParam(r, "id"))
	if err != nil {
		respondJSON(w, http.StatusBadRequest, map[string]string{"error": "Invalid user ID"})
		return
	}

	result, err := h.pgStore.DB.Exec("DELETE FROM users WHERE id = $1", id)
	if err != nil {
		respondJSON(w, http.StatusInternalServerError, map[string]string{"error": "Failed to delete user"})
		return
	}

	rows, _ := result.RowsAffected()
	if rows == 0 {
		respondJSON(w, http.StatusNotFound, map[string]string{"error": "User not found"})
		return
	}

	respondJSON(w, http.StatusOK, map[string]string{"message": "User deleted"})
}

// DashboardStats - 仪表盘统计
func (h *AdminHandler) DashboardStats(w http.ResponseWriter, r *http.Request) {
	stats := make(map[string]interface{})

	// 今日请求数
	var todayRequests int
	h.pgStore.DB.QueryRow(`
		SELECT COUNT(*) FROM request_logs 
		WHERE DATE(created_at) = CURRENT_DATE
	`).Scan(&todayRequests)

	// 今日成功率
	var todaySuccess, todayTotal int
	h.pgStore.DB.QueryRow(`
		SELECT 
			COUNT(CASE WHEN status = 'success' THEN 1 END),
			COUNT(*)
		FROM request_logs 
		WHERE DATE(created_at) = CURRENT_DATE
	`).Scan(&todaySuccess, &todayTotal)

	successRate := 0.0
	if todayTotal > 0 {
		successRate = float64(todaySuccess) / float64(todayTotal) * 100
	}

	// 召回触发率
	var recallTriggered, totalRequests int
	h.pgStore.DB.QueryRow(`
		SELECT 
			COUNT(CASE WHEN recall_triggered = true THEN 1 END),
			COUNT(*)
		FROM request_logs 
		WHERE DATE(created_at) = CURRENT_DATE
	`).Scan(&recallTriggered, &totalRequests)

	recallRate := 0.0
	if totalRequests > 0 {
		recallRate = float64(recallTriggered) / float64(totalRequests) * 100
	}

	// P99延迟（近1小时）
	var p99Latency sql.NullInt64
	h.pgStore.DB.QueryRow(`
		SELECT PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY total_latency_ms)
		FROM request_logs
		WHERE created_at >= NOW() - INTERVAL '1 hour'
	`).Scan(&p99Latency)

	stats["today_requests"] = todayRequests
	stats["success_rate"] = successRate
	stats["recall_rate"] = recallRate
	stats["p99_latency"] = p99Latency.Int64

	respondJSON(w, http.StatusOK, stats)
}

// GetQPSData - 获取QPS数据
func (h *AdminHandler) GetQPSData(w http.ResponseWriter, r *http.Request) {
	minutes, _ := strconv.Atoi(r.URL.Query().Get("minutes"))
	if minutes < 1 || minutes > 1440 {
		minutes = 60
	}

	query := `
		SELECT 
			DATE_TRUNC('minute', created_at) as minute,
			COUNT(*) as qps
		FROM request_logs
		WHERE created_at >= NOW() - INTERVAL '1 minute' * $1
		GROUP BY minute
		ORDER BY minute
	`

	rows, err := h.pgStore.DB.Query(query, minutes)
	if err != nil {
		respondJSON(w, http.StatusInternalServerError, map[string]string{"error": "Database error"})
		return
	}
	defer rows.Close()

	data := []map[string]interface{}{}
	for rows.Next() {
		var minute time.Time
		var qps int
		if err := rows.Scan(&minute, &qps); err != nil {
			continue
		}
		data = append(data, map[string]interface{}{
			"time": minute.Unix(),
			"qps":  qps,
		})
	}

	respondJSON(w, http.StatusOK, data)
}

// GetTrendData - 获取趋势数据
func (h *AdminHandler) GetTrendData(w http.ResponseWriter, r *http.Request) {
	days, _ := strconv.Atoi(r.URL.Query().Get("days"))
	if days < 1 || days > 90 {
		days = 7
	}

	query := `
		SELECT 
			DATE(created_at) as day,
			COUNT(*) as total,
			COUNT(CASE WHEN status = 'success' THEN 1 END) as success
		FROM request_logs
		WHERE created_at >= CURRENT_DATE - INTERVAL '1 day' * $1
		GROUP BY day
		ORDER BY day
	`

	rows, err := h.pgStore.DB.Query(query, days)
	if err != nil {
		respondJSON(w, http.StatusInternalServerError, map[string]string{"error": "Database error"})
		return
	}
	defer rows.Close()

	data := []map[string]interface{}{}
	for rows.Next() {
		var day time.Time
		var total, success int
		if err := rows.Scan(&day, &total, &success); err != nil {
			continue
		}
		data = append(data, map[string]interface{}{
			"date":    day.Format("2006-01-02"),
			"total":   total,
			"success": success,
		})
	}

	respondJSON(w, http.StatusOK, data)
}

// ListLogs - 获取请求日志
func (h *AdminHandler) ListLogs(w http.ResponseWriter, r *http.Request) {
	userID, _ := strconv.Atoi(r.URL.Query().Get("user_id"))
	page, _ := strconv.Atoi(r.URL.Query().Get("page"))
	pageSize, _ := strconv.Atoi(r.URL.Query().Get("page_size"))

	if page < 1 {
		page = 1
	}
	if pageSize < 1 || pageSize > 100 {
		pageSize = 50
	}

	offset := (page - 1) * pageSize

	query := `
		SELECT id, user_id, upstream_url, input_tokens, output_tokens,
		       recall_triggered, recall_latency_ms, total_latency_ms, status, error_message, created_at
		FROM request_logs
		WHERE ($1 = 0 OR user_id = $1)
		ORDER BY created_at DESC
		LIMIT $2 OFFSET $3
	`

	rows, err := h.pgStore.DB.Query(query, userID, pageSize, offset)
	if err != nil {
		respondJSON(w, http.StatusInternalServerError, map[string]string{"error": "Database error"})
		return
	}
	defer rows.Close()

	logs := []map[string]interface{}{}
	for rows.Next() {
		var log struct {
			ID               int
			UserID           int
			UpstreamURL      string
			InputTokens      int
			OutputTokens     int
			RecallTriggered  bool
			RecallLatencyMs  sql.NullInt64
			TotalLatencyMs   int
			Status           string
			ErrorMessage     sql.NullString
			CreatedAt        time.Time
		}

		if err := rows.Scan(&log.ID, &log.UserID, &log.UpstreamURL, &log.InputTokens, &log.OutputTokens,
			&log.RecallTriggered, &log.RecallLatencyMs, &log.TotalLatencyMs, &log.Status, &log.ErrorMessage, &log.CreatedAt); err != nil {
			continue
		}

		logs = append(logs, map[string]interface{}{
			"id":                log.ID,
			"user_id":           log.UserID,
			"upstream_url":      log.UpstreamURL,
			"input_tokens":      log.InputTokens,
			"output_tokens":     log.OutputTokens,
			"recall_triggered":  log.RecallTriggered,
			"recall_latency_ms": log.RecallLatencyMs.Int64,
			"total_latency_ms":  log.TotalLatencyMs,
			"status":            log.Status,
			"error_message":     log.ErrorMessage.String,
			"created_at":        log.CreatedAt.Unix(),
		})
	}

	// 查询总数
	var total int
	countQuery := "SELECT COUNT(*) FROM request_logs WHERE ($1 = 0 OR user_id = $1)"
	h.pgStore.DB.QueryRow(countQuery, userID).Scan(&total)

	respondJSON(w, http.StatusOK, map[string]interface{}{
		"logs":  logs,
		"total": total,
	})
}

// Helper functions
func respondJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

func generateServiceKey() string {
	const charset = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
	b := make([]byte, 32)
	for i := range b {
		b[i] = charset[time.Now().UnixNano()%int64(len(charset))]
	}
	return "sk-" + string(b)
}

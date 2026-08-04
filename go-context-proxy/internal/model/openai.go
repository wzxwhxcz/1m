package model

import "time"

// Message represents a chat message
type Message struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

// ChatCompletionRequest represents OpenAI-compatible chat completion request
type ChatCompletionRequest struct {
	Model       string    `json:"model"`
	Messages    []Message `json:"messages"`
	Temperature float64   `json:"temperature,omitempty"`
	MaxTokens   int       `json:"max_tokens,omitempty"`
	Stream      bool      `json:"stream,omitempty"`
	TopP        float64   `json:"top_p,omitempty"`
}

// ChatCompletionResponse represents OpenAI-compatible response
type ChatCompletionResponse struct {
	ID      string                 `json:"id"`
	Object  string                 `json:"object"`
	Created int64                  `json:"created"`
	Model   string                 `json:"model"`
	Choices []ChatCompletionChoice `json:"choices"`
	Usage   Usage                  `json:"usage,omitempty"`
}

// ChatCompletionChoice represents a completion choice
type ChatCompletionChoice struct {
	Index        int     `json:"index"`
	Message      Message `json:"message"`
	FinishReason string  `json:"finish_reason"`
}

// Usage represents token usage
type Usage struct {
	PromptTokens     int `json:"prompt_tokens"`
	CompletionTokens int `json:"completion_tokens"`
	TotalTokens      int `json:"total_tokens"`
}

// RecallRequest represents request to Python recall service
type RecallRequest struct {
	Messages   []Message `json:"messages"`
	Query      string    `json:"query"`
	K          int       `json:"k"`
	Algorithm  string    `json:"algorithm"`
	NClusters  int       `json:"n_clusters,omitempty"`
}

// RecallResponse represents response from Python recall service
type RecallResponse struct {
	RecalledMessages []RecalledMessage `json:"recalled_messages"`
	OriginalCount    int               `json:"original_count"`
	RecalledCount    int               `json:"recalled_count"`
	LatencyMs        float64           `json:"latency_ms"`
	AlgorithmUsed    string            `json:"algorithm_used"`
	CacheHitRate     float64           `json:"cache_hit_rate"`
}

// RecalledMessage represents a recalled message with similarity score
type RecalledMessage struct {
	Index      int     `json:"index"`
	Content    string  `json:"content"`
	Role       string  `json:"role"`
	Topic      string  `json:"topic,omitempty"`
	Similarity float64 `json:"similarity"`
}

// User represents a user in the system
type User struct {
	ID             int       `json:"id"`
	ServiceKey     string    `json:"service_key"`
	Email          string    `json:"email"`
	Plan           string    `json:"plan"`
	QuotaDaily     int       `json:"quota_daily"`
	QuotaUsedToday int       `json:"quota_used_today"`
	IsActive       bool      `json:"is_active"`
	CreatedAt      time.Time `json:"created_at"`
	UpdatedAt      time.Time `json:"updated_at"`
}

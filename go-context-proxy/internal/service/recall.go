package service

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/wzxwhxcz/go-context-proxy/internal/model"
)

// RecallService handles communication with Python recall service
type RecallService struct {
	client    *http.Client
	baseURL   string
	timeout   time.Duration
}

// NewRecallService creates a new recall service client
func NewRecallService(baseURL string) *RecallService {
	return &RecallService{
		client: &http.Client{
			Timeout: 30 * time.Second,
		},
		baseURL: baseURL,
		timeout: 30 * time.Second,
	}
}

// Recall calls Python service to recall relevant messages
func (s *RecallService) Recall(ctx context.Context, req *model.RecallRequest) (*model.RecallResponse, error) {
	// Marshal request
	body, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("marshal request: %w", err)
	}

	// Create HTTP request
	httpReq, err := http.NewRequestWithContext(ctx, "POST", s.baseURL+"/api/v1/recall", bytes.NewReader(body))
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}

	httpReq.Header.Set("Content-Type", "application/json")

	// Send request
	resp, err := s.client.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("send request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		bodyBytes, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("recall service error: %d - %s", resp.StatusCode, string(bodyBytes))
	}

	// Parse response
	var recallResp model.RecallResponse
	if err := json.NewDecoder(resp.Body).Decode(&recallResp); err != nil {
		return nil, fmt.Errorf("decode response: %w", err)
	}

	return &recallResp, nil
}

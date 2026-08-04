package service

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"time"
)

// UpstreamService handles forwarding requests to upstream LLM providers
type UpstreamService struct {
	client *http.Client
}

// NewUpstreamService creates a new upstream service
func NewUpstreamService() *UpstreamService {
	return &UpstreamService{
		client: &http.Client{
			Timeout: 120 * time.Second, // Long timeout for streaming
		},
	}
}

// Forward forwards request to upstream URL
func (s *UpstreamService) Forward(ctx context.Context, upstreamURL string, body io.Reader, headers http.Header) (*http.Response, error) {
	// Create request
	req, err := http.NewRequestWithContext(ctx, "POST", upstreamURL, body)
	if err != nil {
		return nil, fmt.Errorf("create upstream request: %w", err)
	}

	// Copy headers
	for key, values := range headers {
		for _, value := range values {
			req.Header.Add(key, value)
		}
	}

	// Ensure Content-Type is set
	if req.Header.Get("Content-Type") == "" {
		req.Header.Set("Content-Type", "application/json")
	}

	// Send request
	resp, err := s.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("forward to upstream: %w", err)
	}

	return resp, nil
}

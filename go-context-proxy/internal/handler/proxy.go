package handler

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/wzxwhxcz/go-context-proxy/internal/model"
	"github.com/wzxwhxcz/go-context-proxy/internal/service"
)

// ProxyHandler handles proxy requests
type ProxyHandler struct {
	recallService   *service.RecallService
	upstreamService *service.UpstreamService
}

// NewProxyHandler creates a new proxy handler
func NewProxyHandler(recallService *service.RecallService, upstreamService *service.UpstreamService) *ProxyHandler {
	return &ProxyHandler{
		recallService:   recallService,
		upstreamService: upstreamService,
	}
}

// HandleChatCompletion handles chat completion requests
// URL format: /{serviceKey}/{urlEncodedUpstream}/v1/chat/completions
func (h *ProxyHandler) HandleChatCompletion(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	startTime := time.Now()

	// 1. Parse URL parameters
	serviceKey := chi.URLParam(r, "serviceKey")
	upstreamEncoded := chi.URLParam(r, "upstreamEncoded")

	if serviceKey == "" || upstreamEncoded == "" {
		http.Error(w, "Invalid URL format. Expected: /{serviceKey}/{urlEncodedUpstream}/v1/chat/completions", http.StatusBadRequest)
		return
	}

	// Decode upstream URL
	upstreamBase, err := url.PathUnescape(upstreamEncoded)
	if err != nil {
		http.Error(w, fmt.Sprintf("Invalid upstream URL encoding: %v", err), http.StatusBadRequest)
		return
	}

	upstreamURL := upstreamBase + "/v1/chat/completions"

	// 2. Parse request body
	body, err := io.ReadAll(r.Body)
	if err != nil {
		http.Error(w, fmt.Sprintf("Read request body: %v", err), http.StatusBadRequest)
		return
	}
	defer r.Body.Close()

	var req model.ChatCompletionRequest
	if err := json.Unmarshal(body, &req); err != nil {
		http.Error(w, fmt.Sprintf("Parse request JSON: %v", err), http.StatusBadRequest)
		return
	}

	// 3. Estimate tokens (simple heuristic: ~4 chars per token)
	inputTokens := 0
	for _, msg := range req.Messages {
		inputTokens += len(msg.Content) / 4
	}

	fmt.Printf("[Proxy] serviceKey=%s upstream=%s messages=%d tokens=%d\n", 
		serviceKey, upstreamBase, len(req.Messages), inputTokens)

	// 4. Call recall service if needed (>400K tokens = ~1.6M chars)
	recallTriggered := false
	if inputTokens > 100000 { // 400K tokens threshold
		fmt.Printf("[Recall] Triggering recall for %d tokens...\n", inputTokens)
		
		recallReq := &model.RecallRequest{
			Messages:  req.Messages,
			Query:     req.Messages[len(req.Messages)-1].Content, // Use last message as query
			K:         50,
			Algorithm: "car",
			NClusters: 10,
		}

		recallStart := time.Now()
		recallResp, err := h.recallService.Recall(ctx, recallReq)
		if err != nil {
			fmt.Printf("[Recall] Error: %v\n", err)
			http.Error(w, fmt.Sprintf("Recall service error: %v", err), http.StatusInternalServerError)
			return
		}

		recallLatency := time.Since(recallStart).Milliseconds()
		fmt.Printf("[Recall] Success: %d→%d messages in %dms (algorithm=%s)\n", 
			recallResp.OriginalCount, recallResp.RecalledCount, recallLatency, recallResp.AlgorithmUsed)

		// Replace messages with recalled ones
		req.Messages = make([]model.Message, len(recallResp.RecalledMessages))
		for i, recalled := range recallResp.RecalledMessages {
			req.Messages[i] = model.Message{
				Role:    recalled.Role,
				Content: recalled.Content,
			}
		}

		recallTriggered = true
	}

	// 5. Marshal modified request
	modifiedBody, err := json.Marshal(req)
	if err != nil {
		http.Error(w, fmt.Sprintf("Marshal modified request: %v", err), http.StatusInternalServerError)
		return
	}

	// 6. Forward to upstream
	upstreamResp, err := h.upstreamService.Forward(ctx, upstreamURL, bytes.NewReader(modifiedBody), r.Header)
	if err != nil {
		http.Error(w, fmt.Sprintf("Forward to upstream: %v", err), http.StatusBadGateway)
		return
	}
	defer upstreamResp.Body.Close()

	// 7. Handle streaming vs non-streaming
	if req.Stream {
		h.handleStreamResponse(w, upstreamResp)
	} else {
		h.handleNonStreamResponse(w, upstreamResp)
	}

	totalLatency := time.Since(startTime).Milliseconds()
	fmt.Printf("[Proxy] Completed in %dms (recall=%v)\n", totalLatency, recallTriggered)
}

// handleStreamResponse proxies streaming response
func (h *ProxyHandler) handleStreamResponse(w http.ResponseWriter, upstreamResp *http.Response) {
	// Set SSE headers
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("Transfer-Encoding", "chunked")

	// Copy status code
	w.WriteHeader(upstreamResp.StatusCode)

	// Get flusher
	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "Streaming not supported", http.StatusInternalServerError)
		return
	}

	// Stream response line by line
	scanner := bufio.NewScanner(upstreamResp.Body)
	for scanner.Scan() {
		line := scanner.Text()
		
		// Write line
		fmt.Fprintf(w, "%s\n", line)
		
		// Flush immediately
		flusher.Flush()

		// Check if it's the [DONE] message
		if strings.Contains(line, "[DONE]") {
			break
		}
	}

	if err := scanner.Err(); err != nil {
		fmt.Printf("[Stream] Scanner error: %v\n", err)
	}
}

// handleNonStreamResponse proxies non-streaming response
func (h *ProxyHandler) handleNonStreamResponse(w http.ResponseWriter, upstreamResp *http.Response) {
	// Copy headers
	for key, values := range upstreamResp.Header {
		for _, value := range values {
			w.Header().Add(key, value)
		}
	}

	// Copy status code
	w.WriteHeader(upstreamResp.StatusCode)

	// Copy body
	if _, err := io.Copy(w, upstreamResp.Body); err != nil {
		fmt.Printf("[Proxy] Copy response error: %v\n", err)
	}
}

// HealthCheck returns service health status
func (h *ProxyHandler) HealthCheck(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status":  "healthy",
		"service": "go-context-proxy",
		"version": "1.0.0",
		"time":    time.Now().Unix(),
	})
}

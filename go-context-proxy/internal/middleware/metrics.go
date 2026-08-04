package middleware

import (
	"net/http"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

var (
	// RequestsTotal counts total requests by status
	RequestsTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "proxy_requests_total",
			Help: "Total number of proxy requests",
		},
		[]string{"status"},
	)

	// RequestDuration tracks request latency
	RequestDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "proxy_request_duration_seconds",
			Help:    "Request duration in seconds",
			Buckets: []float64{0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0},
		},
		[]string{"status"},
	)

	// RecallTriggered counts recall invocations
	RecallTriggered = promauto.NewCounter(
		prometheus.CounterOpts{
			Name: "proxy_recall_triggered_total",
			Help: "Total number of recall invocations",
		},
	)

	// RecallDuration tracks recall latency
	RecallDuration = promauto.NewHistogram(
		prometheus.HistogramOpts{
			Name:    "proxy_recall_duration_seconds",
			Help:    "Recall duration in seconds",
			Buckets: []float64{0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0},
		},
	)

	// MessagesProcessed tracks message counts
	MessagesProcessed = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "proxy_messages_processed",
			Help:    "Number of messages processed",
			Buckets: []float64{1, 10, 50, 100, 200, 500, 1000},
		},
		[]string{"stage"}, // before_recall, after_recall
	)

	// TokensProcessed tracks token counts
	TokensProcessed = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "proxy_tokens_processed",
			Help:    "Number of tokens processed",
			Buckets: []float64{100, 1000, 10000, 50000, 100000, 400000, 1000000},
		},
		[]string{"stage"},
	)

	// ActiveRequests tracks concurrent requests
	ActiveRequests = promauto.NewGauge(
		prometheus.GaugeOpts{
			Name: "proxy_active_requests",
			Help: "Number of requests currently being processed",
		},
	)

	// RateLimitExceeded counts rate limit hits
	RateLimitExceeded = promauto.NewCounter(
		prometheus.CounterOpts{
			Name: "proxy_rate_limit_exceeded_total",
			Help: "Total number of rate limit exceeded events",
		},
	)

	// AuthFailures counts authentication failures
	AuthFailures = promauto.NewCounter(
		prometheus.CounterOpts{
			Name: "proxy_auth_failures_total",
			Help: "Total number of authentication failures",
		},
	)
)

// PrometheusHandler returns the Prometheus metrics handler
func PrometheusHandler() http.Handler {
	return promhttp.Handler()
}

// MetricsMiddleware wraps HTTP handler with metrics collection
type MetricsMiddleware struct{}

// NewMetricsMiddleware creates a new metrics middleware
func NewMetricsMiddleware() *MetricsMiddleware {
	return &MetricsMiddleware{}
}

// Handler wraps HTTP handler with metrics
func (m *MetricsMiddleware) Handler(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Skip for metrics endpoint itself
		if r.URL.Path == "/metrics" {
			next.ServeHTTP(w, r)
			return
		}

		// Track active requests
		ActiveRequests.Inc()
		defer ActiveRequests.Dec()

		// Wrap response writer to capture status code
		wrw := &wrappedResponseWriter{
			ResponseWriter: w,
			statusCode:     http.StatusOK,
		}

		// Call next handler
		next.ServeHTTP(wrw, r)
	})
}

// wrappedResponseWriter captures status code
type wrappedResponseWriter struct {
	http.ResponseWriter
	statusCode int
}

func (w *wrappedResponseWriter) WriteHeader(statusCode int) {
	w.statusCode = statusCode
	w.ResponseWriter.WriteHeader(statusCode)
}

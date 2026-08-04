package main

import (
	"fmt"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/cors"
	"github.com/golang-jwt/jwt/v5"
	"github.com/wzxwhxcz/go-context-proxy/internal/handler"
	"github.com/wzxwhxcz/go-context-proxy/internal/middleware"
	"github.com/wzxwhxcz/go-context-proxy/internal/service"
	"github.com/wzxwhxcz/go-context-proxy/internal/storage"
)

func main() {
	fmt.Println("================================================================================")
	fmt.Println("🚀 Starting Go Context Proxy")
	fmt.Println("================================================================================")

	// Load configuration
	config := loadConfig()
	printConfig(config)

	// Initialize storage layers
	var pgStore *storage.PostgresStore
	var redisStore *storage.RedisStore
	var err error

	// Try to connect to PostgreSQL
	pgConnStr := fmt.Sprintf("host=%s port=%s user=%s password=%s dbname=%s sslmode=%s",
		config.PostgresHost, config.PostgresPort, config.PostgresUser,
		config.PostgresPassword, config.PostgresDB, config.PostgresSSLMode)

	pgStore, err = storage.NewPostgresStore(pgConnStr)
	if err != nil {
		log.Printf("⚠️  PostgreSQL connection failed: %v (falling back to mock mode)", err)
		pgStore = nil
	} else {
		fmt.Println("✓ PostgreSQL connected")
	}

	// Try to connect to Redis
	redisStore, err = storage.NewRedisStore(config.RedisAddr, config.RedisPassword, config.RedisDB)
	if err != nil {
		log.Printf("⚠️  Redis connection failed: %v (falling back to mock mode)", err)
		redisStore = nil
	} else {
		fmt.Println("✓ Redis connected")
	}

	// Initialize services
	recallService := service.NewRecallService(config.PythonRecallURL)
	upstreamService := service.NewUpstreamService()

	// Initialize handlers
	proxyHandler := handler.NewProxyHandler(recallService, upstreamService)
	var adminHandler *handler.AdminHandler
	if pgStore != nil {
		adminHandler = handler.NewAdminHandler(pgStore)
	}

	// Initialize middleware (with fallback to mock if DB not available)
	var authMiddleware func(http.Handler) http.Handler
	var rateLimitMiddleware func(http.Handler) http.Handler

	if pgStore != nil && redisStore != nil {
		// Production mode with real databases
		auth := middleware.NewAuthMiddleware(pgStore, redisStore)
		authMiddleware = auth.Handler

		rateLimiter := middleware.NewRateLimiter(redisStore, config.RateLimitWindowSec, config.RateLimitMaxRequests)
		rateLimitMiddleware = rateLimiter.Handler

		fmt.Println("✓ Running in PRODUCTION mode (PostgreSQL + Redis)")
	} else {
		// Mock mode for development
		mockUserStore := middleware.NewMockUserStore()
		mockAuth := middleware.NewMockAuthMiddleware(mockUserStore)
		authMiddleware = mockAuth.Handler

		mockRateLimiter := middleware.NewMockRateLimiter(config.RateLimitWindowSec, config.RateLimitMaxRequests)
		rateLimitMiddleware = mockRateLimiter.Handler

		fmt.Println("⚠️  Running in MOCK mode (in-memory storage)")
	}

	metricsMiddleware := middleware.NewMetricsMiddleware()

	// Setup router
	r := chi.NewRouter()

	// Middleware stack (order matters!)
	r.Use(middleware.Logger)             // 1. Logging first
	r.Use(metricsMiddleware.Handler)     // 2. Metrics
	r.Use(authMiddleware)                // 3. Auth
	r.Use(rateLimitMiddleware)           // 4. Rate limiting
	r.Use(cors.Handler(cors.Options{     // 5. CORS
		AllowedOrigins:   []string{"*"},
		AllowedMethods:   []string{"GET", "POST", "PUT", "DELETE", "OPTIONS"},
		AllowedHeaders:   []string{"*"},
		ExposedHeaders:   []string{"*"},
		AllowCredentials: false,
		MaxAge:           300,
	}))

	// Routes
	r.Get("/health", proxyHandler.HealthCheck)
	r.Get("/metrics", middleware.PrometheusHandler().ServeHTTP)
	
	// Proxy route: /{serviceKey}/{urlEncodedUpstream}/v1/chat/completions
	r.Post("/{serviceKey}/{upstreamEncoded}/v1/chat/completions", proxyHandler.HandleChatCompletion)

	// Admin API routes
	if adminHandler != nil {
		r.Route("/api/admin", func(r chi.Router) {
			// 登录接口（无需认证）
			r.Post("/login", adminHandler.Login)
			
			// 需要JWT认证的接口
			r.Group(func(r chi.Router) {
				r.Use(jwtAuthMiddleware)
				
				// 用户管理
				r.Get("/users", adminHandler.ListUsers)
				r.Post("/users", adminHandler.CreateUser)
				r.Get("/users/{id}", adminHandler.GetUser)
				r.Put("/users/{id}", adminHandler.UpdateUser)
				r.Delete("/users/{id}", adminHandler.DeleteUser)
				
				// 统计数据
				r.Get("/stats/dashboard", adminHandler.DashboardStats)
				r.Get("/stats/qps", adminHandler.GetQPSData)
				r.Get("/stats/trend", adminHandler.GetTrendData)
				
				// 请求日志
				r.Get("/logs", adminHandler.ListLogs)
			})
		})
	} else {
		// Mock mode - placeholder
		r.Route("/api/admin", func(r chi.Router) {
			r.Get("/users", func(w http.ResponseWriter, r *http.Request) {
				w.Write([]byte(`{"message":"Admin API requires PostgreSQL connection"}`))
			})
		})
	}

	// Start server
	addr := ":" + config.Port
	fmt.Printf("\n✓ Server listening on %s\n", addr)
	fmt.Println("\nEndpoints:")
	fmt.Printf("  GET  http://localhost:%s/health   - Health check\n", config.Port)
	fmt.Printf("  GET  http://localhost:%s/metrics  - Prometheus metrics\n", config.Port)
	fmt.Printf("  POST http://localhost:%s/sk-test123/https%%3A%%2F%%2Fapi.openai.com/v1/chat/completions\n", config.Port)
	fmt.Println("\n================================================================================\n")

	if err := http.ListenAndServe(addr, r); err != nil {
		log.Fatalf("Server failed: %v", err)
	}
}

type Config struct {
	Port                  string
	PythonRecallURL       string
	PostgresHost          string
	PostgresPort          string
	PostgresUser          string
	PostgresPassword      string
	PostgresDB            string
	PostgresSSLMode       string
	RedisAddr             string
	RedisPassword         string
	RedisDB               int
	RateLimitWindowSec    int
	RateLimitMaxRequests  int
	RecallThreshold       int
}

func loadConfig() *Config {
	return &Config{
		Port:                 getEnv("PORT", "8080"),
		PythonRecallURL:      getEnv("PYTHON_RECALL_URL", "http://localhost:8000"),
		PostgresHost:         getEnv("POSTGRES_HOST", "localhost"),
		PostgresPort:         getEnv("POSTGRES_PORT", "5432"),
		PostgresUser:         getEnv("POSTGRES_USER", "postgres"),
		PostgresPassword:     getEnv("POSTGRES_PASSWORD", "postgres"),
		PostgresDB:           getEnv("POSTGRES_DB", "contextproxy"),
		PostgresSSLMode:      getEnv("POSTGRES_SSLMODE", "disable"),
		RedisAddr:            getEnv("REDIS_ADDR", "localhost:6379"),
		RedisPassword:        getEnv("REDIS_PASSWORD", ""),
		RedisDB:              getEnvInt("REDIS_DB", 0),
		RateLimitWindowSec:   getEnvInt("RATE_LIMIT_WINDOW_SEC", 60),
		RateLimitMaxRequests: getEnvInt("RATE_LIMIT_MAX_REQUESTS", 100),
		RecallThreshold:      getEnvInt("ENABLE_RECALL_THRESHOLD", 400000),
	}
}

func printConfig(c *Config) {
	fmt.Printf("Port:                    %s\n", c.Port)
	fmt.Printf("Python Recall URL:       %s\n", c.PythonRecallURL)
	fmt.Printf("PostgreSQL:              %s:%s/%s\n", c.PostgresHost, c.PostgresPort, c.PostgresDB)
	fmt.Printf("Redis:                   %s (DB %d)\n", c.RedisAddr, c.RedisDB)
	fmt.Printf("Rate Limit:              %d req/%ds\n", c.RateLimitMaxRequests, c.RateLimitWindowSec)
	fmt.Printf("Recall Threshold:        %d tokens\n", c.RecallThreshold)
	fmt.Println("================================================================================")
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func getEnvInt(key string, defaultValue int) int {
	if value := os.Getenv(key); value != "" {
		if intValue, err := strconv.Atoi(value); err == nil {
			return intValue
		}
	}
	return defaultValue
}

// JWT middleware for admin routes
var jwtSecret = []byte("context-proxy-secret-key-change-in-production")

func jwtAuthMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		authHeader := r.Header.Get("Authorization")
		if authHeader == "" {
			http.Error(w, "Missing authorization header", http.StatusUnauthorized)
			return
		}

		tokenString := strings.TrimPrefix(authHeader, "Bearer ")
		if tokenString == authHeader {
			http.Error(w, "Invalid authorization format", http.StatusUnauthorized)
			return
		}

		token, err := jwt.Parse(tokenString, func(token *jwt.Token) (interface{}, error) {
			if _, ok := token.Method.(*jwt.SigningMethodHMAC); !ok {
				return nil, fmt.Errorf("unexpected signing method")
			}
			return jwtSecret, nil
		})

		if err != nil || !token.Valid {
			http.Error(w, "Invalid token", http.StatusUnauthorized)
			return
		}

		next.ServeHTTP(w, r)
	})
}

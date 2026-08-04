// 用户相关类型
export interface User {
  id: number;
  service_key: string;
  email: string;
  plan: 'free' | 'pro' | 'enterprise';
  quota_daily: number;
  quota_used_today: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateUserRequest {
  email: string;
  plan: 'free' | 'pro' | 'enterprise';
  quota_daily: number;
}

export interface UpdateUserRequest {
  email?: string;
  plan?: 'free' | 'pro' | 'enterprise';
  quota_daily?: number;
  is_active?: boolean;
}

// 请求日志类型
export interface RequestLog {
  id: number;
  user_id: number;
  upstream_url: string;
  input_tokens: number;
  output_tokens: number;
  recall_triggered: boolean;
  recall_latency_ms: number;
  total_latency_ms: number;
  status: string;
  error_message: string;
  created_at: string;
}

// 统计数据类型
export interface DashboardStats {
  today_requests: number;
  today_success_rate: number;
  today_recall_rate: number;
  p99_latency: number;
  active_users: number;
  total_tokens: number;
}

export interface QPSData {
  timestamp: string;
  qps: number;
}

export interface TrendData {
  date: string;
  requests: number;
  success_rate: number;
}

// 认证相关类型
export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  token: string;
  user: {
    id: number;
    username: string;
  };
}

// API响应类型
export interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
}

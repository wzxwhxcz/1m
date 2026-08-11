import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8083';

const userClient = axios.create({
  baseURL: API_BASE,
  timeout: 10000,
});

// 请求拦截器：添加 user token
userClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('user_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器：处理错误
userClient.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('user_token');
      window.location.href = '/user/login';
    }
    return Promise.reject(error);
  }
);

export interface User {
  id: number;
  username: string;
  email: string;
  service_key: string;
  plan: string;
  quota_daily: number;
  quota_used_today: number;
  trust_level: number;
  created_at: string;
}

export interface UserStats {
  quota_daily: number;
  quota_used_today: number;
  quota_remaining: number;
  total_requests: number;
  monthly_requests: number;
  recall_triggered: number;
  avg_latency: number;
}

export interface QuotaTrend {
  date: string;
  requests: number;
  recall_count: number;
}

export interface RequestLog {
  id: number;
  upstream_url: string;
  input_tokens: number;
  output_tokens: number;
  recall_triggered: boolean;
  recall_latency_ms: number;
  total_latency_ms: number;
  status: string;
  created_at: string;
}

export const userService = {
  // Linux Do OAuth 回调
  linuxDoCallback: (code: string) =>
    userClient.post<any, { token: string; user: User }>('/api/user/auth/linuxdo/callback', { code }),

  // 获取用户信息
  getProfile: () => userClient.get<any, User>('/api/user/profile'),

  // 获取仪表盘数据
  getStats: () => userClient.get<any, UserStats>('/api/user/dashboard'),

  // 获取每日趋势
  getQuotaTrend: (days: number = 7) =>
    userClient.get<any, QuotaTrend[]>('/api/user/trend', { params: { days } }),

  // 重置 API 密钥
  resetKey: () => userClient.post<any, { new_service_key: string }>('/api/user/reset-key'),

  // 获取请求日志
  getLogs: (page: number = 1, pageSize: number = 20) =>
    userClient.get<any, { logs: RequestLog[], total: number }>('/api/user/logs', { params: { page, page_size: pageSize } }),
};

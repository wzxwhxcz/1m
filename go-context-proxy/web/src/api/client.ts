import axios from 'axios';
import type { 
  User, 
  CreateUserRequest, 
  UpdateUserRequest,
  RequestLog,
  DashboardStats,
  QPSData,
  TrendData,
  LoginRequest,
  LoginResponse,
  ApiResponse
} from '../types';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8083';

const client = axios.create({
  baseURL: API_BASE,
  timeout: 10000,
});

// 请求拦截器：添加token
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器：处理错误
client.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// 认证API
export const authApi = {
  login: (data: LoginRequest) => 
    client.post<any, ApiResponse<LoginResponse>>('/api/admin/login', data),
  
  logout: () => {
    localStorage.removeItem('token');
    window.location.href = '/login';
  },
};

// 用户管理API
export const userApi = {
  list: (page = 1, pageSize = 20) => 
    client.get<any, ApiResponse<{ users: User[]; total: number }>>('/api/admin/users', {
      params: { page, page_size: pageSize }
    }),
  
  get: (id: number) => 
    client.get<any, ApiResponse<User>>(`/api/admin/users/${id}`),
  
  create: (data: CreateUserRequest) => 
    client.post<any, ApiResponse<User>>('/api/admin/users', data),
  
  update: (id: number, data: UpdateUserRequest) => 
    client.put<any, ApiResponse<User>>(`/api/admin/users/${id}`, data),
  
  delete: (id: number) => 
    client.delete<any, ApiResponse<void>>(`/api/admin/users/${id}`),
};

// 统计数据API
export const statsApi = {
  dashboard: () => 
    client.get<any, ApiResponse<DashboardStats>>('/api/admin/stats/dashboard'),
  
  qps: (minutes = 60) => 
    client.get<any, ApiResponse<QPSData[]>>('/api/admin/stats/qps', {
      params: { minutes }
    }),
  
  trend: (days = 7) => 
    client.get<any, ApiResponse<TrendData[]>>('/api/admin/stats/trend', {
      params: { days }
    }),
};

// 请求日志API
export const logApi = {
  list: (userId?: number, page = 1, pageSize = 50) => 
    client.get<any, ApiResponse<{ logs: RequestLog[]; total: number }>>('/api/admin/logs', {
      params: { user_id: userId, page, page_size: pageSize }
    }),
};

export default client;

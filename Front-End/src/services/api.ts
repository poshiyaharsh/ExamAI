import axios from "axios";
import { authStorage } from "./auth";

export type UserRole = "student" | "faculty" | "admin";

export type TestApiGetResponse = {
  status: string;
  message: string;
  data: {
    course: string;
    backend: string;
  };
};

export type TestApiPostPayload = {
  name: string;
  message: string;
};

export type TestApiPostResponse = {
  status: string;
  message: string;
  submitted: TestApiPostPayload;
};

export type AuthPayload = {
  first_name?: string;
  last_name?: string;
  email: string;
  password: string;
};

export type AuthResponse = {
  status: string;
  message: string;
  tokens: {
    access: string;
    refresh: string;
  };
  user: {
    id: number;
    first_name: string;
    last_name: string;
    email: string;
    role: UserRole;
  };
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
});

const refreshClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
});

let isRefreshing = false;
let queuedRequests: Array<{
  resolve: (value: string) => void;
  reject: (reason?: unknown) => void;
}> = [];

function resolveQueuedRequests(token: string) {
  queuedRequests.forEach(({ resolve }) => resolve(token));
  queuedRequests = [];
}

function rejectQueuedRequests(error: unknown) {
  queuedRequests.forEach(({ reject }) => reject(error));
  queuedRequests = [];
}

apiClient.interceptors.request.use((config) => {
  const session = authStorage.getSession();
  if (session?.access) {
    config.headers.Authorization = `Bearer ${session.access}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config as (typeof error.config & { _retry?: boolean });
    const statusCode = error.response?.status;

    if (statusCode !== 401 || !originalRequest || originalRequest._retry) {
      return Promise.reject(error);
    }

    const session = authStorage.getSession();
    if (!session?.refresh) {
      authStorage.clearSession();
      return Promise.reject(error);
    }

    originalRequest._retry = true;

    if (isRefreshing) {
      return new Promise<string>((resolve, reject) => {
        queuedRequests.push({ resolve, reject });
      })
        .then((newAccessToken) => {
          originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
          return apiClient(originalRequest);
        })
        .catch((queueError) => Promise.reject(queueError));
    }

    isRefreshing = true;

    try {
      const refreshResponse = await refreshClient.post<{ access: string; refresh?: string }>(
        "/api/token/refresh/",
        { refresh: session.refresh }
      );

      const nextAccess = refreshResponse.data.access;
      const nextRefresh = refreshResponse.data.refresh ?? session.refresh;

      authStorage.setSession({
        ...session,
        access: nextAccess,
        refresh: nextRefresh,
      });

      resolveQueuedRequests(nextAccess);
      originalRequest.headers.Authorization = `Bearer ${nextAccess}`;
      return apiClient(originalRequest);
    } catch (refreshError) {
      rejectQueuedRequests(refreshError);
      authStorage.clearSession();
      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  }
);

export const testApi = {
  getTestData: async (): Promise<TestApiGetResponse> => {
    const response = await apiClient.get<TestApiGetResponse>("/api/test/");
    return response.data;
  },
  postTestData: async (payload: TestApiPostPayload): Promise<TestApiPostResponse> => {
    const response = await apiClient.post<TestApiPostResponse>("/api/test/", payload);
    return response.data;
  },
};

const authPathByRole: Record<UserRole, string> = {
  student: "/api/students",
  faculty: "/api/faculty",
  admin: "/api/admins",
};

export const authApi = {
  signup: async (role: UserRole, payload: AuthPayload): Promise<AuthResponse> => {
    const response = await apiClient.post<AuthResponse>(`${authPathByRole[role]}/signup/`, payload);
    return response.data;
  },
  login: async (role: UserRole, payload: AuthPayload): Promise<AuthResponse> => {
    const response = await apiClient.post<AuthResponse>(`${authPathByRole[role]}/login/`, payload);
    return response.data;
  },
};

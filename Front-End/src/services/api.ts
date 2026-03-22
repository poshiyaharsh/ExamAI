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

export type StudentProfileData = {
  full_name: string;
  email: string;
  student_id: string;
  department: string;
};

export type StudentProfileResponse = {
  status: string;
  message: string;
  data: StudentProfileData;
};

export type FacultyProfileData = {
  full_name: string;
  email: string;
  employee_id: string;
  department: string;
};

export type FacultyProfileResponse = {
  status: string;
  message: string;
  data: FacultyProfileData;
};

export type AdminInstitutionData = {
  institution_name: string;
  institution_code: string;
  address: string;
  phone: string;
  email: string;
};

export type AdminInstitutionResponse = {
  status: string;
  message: string;
  data: AdminInstitutionData;
  exists: boolean;
};

export type ChangePasswordResponse = {
  status: string;
  message: string;
};

export type ForgotPasswordResponse = {
  status: string;
  message: string;
  debug_otp?: string;
};

export type VerifyOtpResponse = {
  status: string;
  message: string;
  reset_token: string;
};

export type ResetPasswordResponse = {
  status: string;
  message: string;
};

const API_BASE_URL =
  (import.meta as { env?: { VITE_API_BASE_URL?: string } }).env?.VITE_API_BASE_URL ||
  "http://127.0.0.1:8000";

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
  const requestUrl = config.url ?? "";
  const isPublicAuthCall =
    requestUrl.includes("/login/") ||
    requestUrl.includes("/signup/") ||
    requestUrl.includes("/api/token/refresh/");

  if (session?.access && !isPublicAuthCall) {
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

export const studentProfileApi = {
  getProfile: async (): Promise<StudentProfileResponse> => {
    const response = await apiClient.get<StudentProfileResponse>("/api/student/profile");
    return response.data;
  },
  updateProfile: async (department: string): Promise<StudentProfileResponse> => {
    const response = await apiClient.put<StudentProfileResponse>("/api/student/profile", {
      department,
    });
    return response.data;
  },
};

export const facultyProfileApi = {
  getProfile: async (): Promise<FacultyProfileResponse> => {
    const response = await apiClient.get<FacultyProfileResponse>("/api/faculty/profile");
    return response.data;
  },
  updateProfile: async (department: string): Promise<FacultyProfileResponse> => {
    const response = await apiClient.put<FacultyProfileResponse>("/api/faculty/profile", {
      department,
    });
    return response.data;
  },
};

export const adminInstitutionApi = {
  getInstitution: async (): Promise<AdminInstitutionResponse> => {
    const response = await apiClient.get<AdminInstitutionResponse>("/api/admin/institution");
    return response.data;
  },
  createInstitution: async (payload: {
    institution_name: string;
    address: string;
    phone: string;
  }): Promise<AdminInstitutionResponse> => {
    const response = await apiClient.post<AdminInstitutionResponse>("/api/admin/institution", payload);
    return response.data;
  },
  updateInstitution: async (payload: {
    institution_name: string;
    address: string;
    phone: string;
  }): Promise<AdminInstitutionResponse> => {
    const response = await apiClient.put<AdminInstitutionResponse>("/api/admin/institution", payload);
    return response.data;
  },
};

export const authAccountApi = {
  changePassword: async (payload: {
    current_password: string;
    new_password: string;
  }): Promise<ChangePasswordResponse> => {
    const response = await apiClient.post<ChangePasswordResponse>("/api/auth/change-password", payload);
    return response.data;
  },
};

export const forgotPasswordApi = {
  requestReset: async (email: string): Promise<ForgotPasswordResponse> => {
    const response = await apiClient.post<ForgotPasswordResponse>("/api/auth/forgot-password", { email });
    return response.data;
  },
  verifyOtp: async (email: string, otp: string): Promise<VerifyOtpResponse> => {
    const response = await apiClient.post<VerifyOtpResponse>("/api/auth/verify-otp", { email, otp });
    return response.data;
  },
  resetPassword: async (payload: {
    email: string;
    reset_token: string;
    new_password: string;
    confirm_password: string;
  }): Promise<ResetPasswordResponse> => {
    const response = await apiClient.post<ResetPasswordResponse>("/api/auth/reset-password", payload);
    return response.data;
  },
};

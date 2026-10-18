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
  institution_id?: number;
  department?: string;
};

export type InstitutionOption = {
  id: number;
  institution_name: string;
  institution_code: string;
};

export type DepartmentOption = {
  id: number;
  department_name: string;
};

export type InstitutionsResponse = {
  status: string;
  message: string;
  data: InstitutionOption[];
};

export type DepartmentsResponse = {
  status: string;
  message: string;
  data: DepartmentOption[];
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

export type AuthMeResponse = {
  status: string;
  message: string;
  user: {
    id: number;
    first_name: string;
    last_name: string;
    email: string;
    institution?: {
      id: number;
      institution_name: string;
      institution_code: string;
      status?: string;
    } | null;
  };
  role: UserRole;
};

export type StudentProfileData = {
  full_name: string;
  email: string;
  student_id: string;
  department: string;
  institution: InstitutionOption | null;
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
  institution: InstitutionOption | null;
};

export type FacultyProfileResponse = {
  status: string;
  message: string;
  data: FacultyProfileData;
};

export type AiModel = "qwen2.5-3b" | "llama3.2-3b" | "phi3-mini";
export type PaperQuestionType = "MCQ" | "Subjective" | "True/False" | "Fill in the Blanks";
export type PaperDifficulty = "Easy" | "Medium" | "Hard";

export type SyllabusUploadData = {
  id: number;
  original_filename: string;
  extracted_text: string;
  created_at: string;
};

export type SyllabusUploadResponse = {
  status: string;
  message: string;
  data: SyllabusUploadData;
};

export type PaperQuestion = {
  question_number: number;
  type: PaperQuestionType;
  difficulty: PaperDifficulty;
  marks: number;
  question: string;
  options: string[];
  answer: string;
};

export type GeneratedPaper = {
  id: number;
  title: string;
  duration: number;
  total_marks: number;
  model: AiModel;
  topics: string[];
  question_types: PaperQuestionType[];
  difficulty_distribution: Record<PaperDifficulty, number>;
  questions: PaperQuestion[];
  institution: InstitutionOption;
  created_at: string;
};

export type PaperHistoryRow = {
  id: number;
  title: string;
  duration: number;
  total_marks: number;
  model: AiModel;
  questions: number;
  difficulty: PaperDifficulty;
  created_at: string;
};

export type GeneratePaperPayload = {
  syllabus_upload_id: number;
  title: string;
  duration: number;
  total_marks: number;
  model: AiModel;
  topics: string[];
  question_types: PaperQuestionType[];
  difficulty_distribution: Record<PaperDifficulty, number>;
};

export type OllamaStatusResponse = {
  status: string;
  connected: boolean;
  model_installed: boolean;
  message: string;
  models?: string[];
};

export type GeneratedPaperResponse = {
  success: boolean;
  status: string;
  message: string;
  provider: string;
  model: string;
  paper: GeneratedPaper;
  data: GeneratedPaper;
};

export type PaperHistoryResponse = {
  status: string;
  message: string;
  data: PaperHistoryRow[];
};

export type AdminInstitutionData = {
  id: number;
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

export type ExamQuestion = {
  id: number;
  order: number;
  question_type: "mcq" | "truefalse" | "fillblank" | "subjective";
  difficulty: "easy" | "medium" | "hard";
  text: string;
  options: string[] | null;
  correct_answer: string | number | boolean | null;
  model_answer: string;
  marks: number;
  topic: string;
};

export type FacultyExam = {
  id: number;
  title: string;
  duration_minutes: number;
  total_marks: number;
  topics: string[];
  difficulty_distribution: Record<string, number>;
  question_types: string[];
  ai_model_used: string;
  source_syllabus_text?: string;
  status: "generating" | "draft" | "failed" | "published" | "closed";
  error_message?: string;
  seed?: number;
  request_hash?: string;
  is_immutable?: boolean;
  validation_report?: any;
  starts_at: string | null;
  ends_at: string | null;
  created_at: string;
  updated_at: string;
  question_count?: number;
  attempts_count?: number;
  questions?: ExamQuestion[];
  visibility?: {
    can_publish: boolean;
    student_count: number;
    status_summary: string;
    reasons: string[];
  };
};

export type GenerateExamResponse = {
  exam_id: number;
  status: string;
  question_count: number;
  requested_total_marks: number;
  actual_total_marks: number;
  warning?: string;
  loaded_from_cache?: boolean;
  validation_report?: {
    passed: boolean;
    errors: string[];
    warnings: string[];
    actual_total_marks: number;
    actual_counts_by_type: Record<string, number>;
    actual_difficulty_mix: Record<string, number>;
    estimated_time_minutes: number;
    duplicates_removed_count: number;
    repeats_avoided_count: number;
    relaxation_notices: string[];
    generation_time_ms: number;
    cached_hit: boolean;
  };
  exam?: FacultyExam;
};

export type StudentExam = {
  id: number;
  title: string;
  department?: string;
  duration_minutes: number;
  total_marks: number;
  topics: string[];
  starts_at: string | null;
  ends_at: string | null;
  questions?: Array<Omit<ExamQuestion, "correct_answer" | "model_answer">>;
};

export type StudentExamSummary = {
  exam: StudentExam;
  completed: boolean;
  attempt_id: number | null;
  available: boolean;
};

export type StudentAttempt = {
  id: number;
  exam: number;
  exam_title: string;
  exam_total_marks: number;
  started_at: string;
  submitted_at: string | null;
  status: "in_progress" | "submitted" | "auto_submitted" | "evaluated";
  total_score: number;
  answers: Array<{
    question: number;
    question_text: string;
    question_type: "mcq" | "truefalse" | "fillblank" | "subjective";
    correct_answer: string | number | boolean | null;
    answer_text: string;
    is_correct: boolean | null;
    score_awarded: number | null;
    ai_feedback: string;
  }>;
};

export type StudentExamListResponse = StudentExamSummary[];
export type StudentExamStartResponse = {
  attempt_id: number;
  exam: StudentExam;
  started_at: string;
  deadline: string;
  created: boolean;
};
export type StudentAttemptResponse = StudentAttempt;

export type AdminStudentRow = {
  id: number;
  full_name: string;
  first_name?: string;
  last_name?: string;
  email: string;
  roll_number: string;
  department: string;
  year: string;
  number_of_exams: number;
  average_score: number | null;
  highest_score?: number | null;
  lowest_score?: number | null;
  last_exam_date?: string | null;
  performance_status?: "Excellent" | "Good" | "Average" | "Needs Improvement" | "N/A";
};

export type AdminStudentListResponse = {
  status: string;
  message: string;
  data: AdminStudentRow[];
  pagination?: {
    page: number;
    page_size: number;
    total_count: number;
    total_pages: number;
    has_next: boolean;
    has_prev: boolean;
  } | null;
  stats?: {
    total_students: number;
    overall_average_score: number | null;
    top_performer: {
      id: number;
      name: string;
      email: string;
      roll_number: string;
      percentage: number;
    } | null;
    students_below_pass: number;
  };
  departments?: string[];
};

export type StudentPerformanceSummary = {
  total_attempts: number;
  overall_average: number | null;
  highest_score: number | null;
  lowest_score: number | null;
  pass_count: number;
  fail_count: number;
  pass_rate: number | null;
  last_exam_date: string | null;
  performance_status: "Excellent" | "Good" | "Average" | "Needs Improvement" | "N/A";
  department: string;
  department_rank?: number | null;
  department_total_students?: number | null;
  department_percentile?: number | null;
};

export type StudentPerformanceSummaryResponse = {
  status: string;
  data: StudentPerformanceSummary;
};

export type StudentPerformanceResultRow = {
  attempt_id: number;
  exam_id: number;
  exam_title: string;
  subject: string;
  department: string;
  faculty_name: string;
  faculty_email: string;
  date: string;
  marks_obtained: number;
  total_marks: number;
  percentage: number;
  is_passed: boolean;
  time_taken_seconds: number | null;
  time_taken: string;
  status: string;
};

export type StudentPerformanceResultsResponse = {
  status: string;
  data: StudentPerformanceResultRow[];
  pagination: {
    page: number;
    page_size: number;
    total_count: number;
    total_pages: number;
    has_next: boolean;
    has_prev: boolean;
  };
};

export type StudentPerformanceTrendItem = {
  attempt_id: number;
  date: string;
  iso_date: string | null;
  percentage: number;
  marks_obtained: number;
  total_marks: number;
  exam_title: string;
  status: string;
};

export type StudentPerformanceTrendResponse = {
  status: string;
  data: StudentPerformanceTrendItem[];
};

export type StudentSubjectItem = {
  subject: string;
  average_score: number;
  exam_count: number;
  highest_score: number;
  lowest_score: number;
  is_strongest?: boolean;
  is_weakest?: boolean;
};

export type StudentPerformanceSubjectsResponse = {
  status: string;
  data: {
    subjects: StudentSubjectItem[];
    strongest_subject: string | null;
    weakest_subject: string | null;
  };
};

export type StudentDashboardProfile = {
  name: string;
  first_name: string;
  last_name: string;
  email: string;
  roll_number: string;
  department: string;
  year_semester: string;
  profile_photo: string | null;
};

export type StudentDashboardStats = {
  total_available: number;
  exams_attempted: number;
  exams_pending: number;
  average_score: number | null;
  highest_score: number | null;
  pass_count: number;
  fail_count: number;
  pass_rate: number | null;
  performance_status: "Excellent" | "Good" | "Average" | "Needs Improvement" | "N/A";
};

export type StudentDashboardExamItem = {
  id: number;
  title: string;
  subject: string;
  department: string;
  faculty_name: string;
  duration_minutes: number;
  total_marks: number;
  starts_at: string | null;
  ends_at: string | null;
  is_open: boolean;
};

export type StudentDashboardRecentResult = {
  attempt_id: number;
  exam_id: number;
  exam_title: string;
  subject: string;
  department: string;
  faculty_name: string;
  date: string;
  marks_obtained: number;
  total_marks: number;
  percentage: number;
  is_passed: boolean;
  time_taken: string;
  status: string;
};

export type StudentDashboardTrendItem = {
  attempt_id: number;
  date: string;
  percentage: number;
  exam_title: string;
};

export type StudentDashboardData = {
  profile: StudentDashboardProfile;
  stats: StudentDashboardStats;
  ongoing_exams: StudentDashboardExamItem[];
  upcoming_exams: StudentDashboardExamItem[];
  recent_results: StudentDashboardRecentResult[];
  performance_trend: StudentDashboardTrendItem[];
  subject_strengths: {
    strongest: { subject: string; average_score: number; count: number } | null;
    weakest: { subject: string; average_score: number; count: number } | null;
    all: Array<{ subject: string; average_score: number; count: number }>;
  };
  announcements: Array<{ id: number; title: string; message: string; date: string }>;
};

export type StudentDashboardResponse = {
  status: string;
  data: StudentDashboardData;
};

export type FacultyDashboardProfile = {
  name: string;
  first_name: string;
  last_name: string;
  email: string;
  department: string;
  designation: string;
  employee_id: string;
  subjects_taught: string[];
};

export type FacultyDashboardStats = {
  total_exams: number;
  published_exams: number;
  draft_exams: number;
  upcoming_exams: number;
  ongoing_exams: number;
  completed_exams: number;
  total_students: number;
  total_attempts: number;
  overall_average: number | null;
  overall_pass_rate: number | null;
  pass_count: number;
  fail_count: number;
};

export type FacultyOngoingExamItem = {
  id: number;
  title: string;
  subject: string;
  department: string;
  duration_minutes: number;
  total_marks: number;
  starts_at: string | null;
  ends_at: string | null;
  submitted_count: number;
  eligible_students: number;
};

export type FacultyUpcomingExamItem = {
  id: number;
  title: string;
  subject: string;
  department: string;
  duration_minutes: number;
  total_marks: number;
  starts_at: string | null;
  ends_at: string | null;
  eligible_students: number;
};

export type FacultyRecentExamItem = {
  id: number;
  title: string;
  subject: string;
  department: string;
  created_at: string;
  status: string;
  attempts_count: number;
  average_score: number | null;
  pass_rate: number | null;
};

export type FacultyExamPerfItem = {
  id: number;
  exam_title: string;
  average_score: number;
  attempts_count: number;
};

export type FacultyScoreDistributionItem = {
  range: string;
  count: number;
  label: string;
};

export type FacultyTopPerformerItem = {
  student_id: number;
  name: string;
  roll_number: string;
  department: string;
  average_score: number;
  exams_taken: number;
};

export type FacultyNeedsAttentionItem = {
  student_id: number;
  name: string;
  roll_number: string;
  department: string;
  average_score: number | null;
  exams_taken: number;
  type: "low_score" | "unattempted";
  issue: string;
};

export type FacultyHardestQuestionItem = {
  question_id: number;
  exam_id: number;
  exam_title: string;
  text: string;
  topic: string;
  difficulty: string;
  total_answers: number;
  wrong_answers: number;
  error_rate: number;
};

export type FacultyPendingActions = {
  draft_exams_count: number;
  drafts: Array<{ id: number; title: string; created_at: string }>;
  empty_exams_count: number;
  empty_exams: Array<{ id: number; title: string }>;
};

export type FacultyDashboardData = {
  profile: FacultyDashboardProfile;
  stats: FacultyDashboardStats;
  ongoing_exams: FacultyOngoingExamItem[];
  upcoming_exams: FacultyUpcomingExamItem[];
  recent_exams: FacultyRecentExamItem[];
  exam_performance: FacultyExamPerfItem[];
  score_distribution: FacultyScoreDistributionItem[];
  top_performers: FacultyTopPerformerItem[];
  needs_attention: {
    low_scorers: FacultyNeedsAttentionItem[];
    unattempted_students: FacultyNeedsAttentionItem[];
  };
  hardest_questions: FacultyHardestQuestionItem[];
  pending_actions: FacultyPendingActions;
};

export type FacultyDashboardResponse = {
  status: string;
  data: FacultyDashboardData;
};

export type StudentExamResultItem = {
  attempt_id: number;
  exam_id: number;
  exam_title: string;
  subject: string;
  faculty_name: string;
  faculty_email: string;
  date: string | null;
  marks_obtained: number;
  total_marks: number;
  percentage: number;
  is_passed: boolean;
  status: string;
};

export type AdminStudentResultsResponse = {
  status: string;
  data: {
    student: {
      id: number;
      full_name: string;
      first_name: string;
      last_name: string;
      email: string;
      roll_number: string;
      department: string;
    };
    summary: {
      total_attempts: number;
      overall_average: number | null;
      highest_score: number | null;
      lowest_score: number | null;
      performance_status: string;
    };
    results: StudentExamResultItem[];
    trend: Array<{
      date: string;
      percentage: number;
      exam_title: string;
      status: string;
    }>;
  };
};

export type AdminStudentDetails = {
  id: number;
  full_name: string;
  first_name: string;
  last_name: string;
  email: string;
  roll_number: string;
  department: string;
  year: string;
  number_of_exams: number;
  average_score: number | null;
  institution: InstitutionOption | null;
};

export type AdminStudentDetailResponse = {
  status: string;
  message: string;
  data: AdminStudentDetails;
};

export type AdminStudentCreatePayload = {
  first_name: string;
  last_name: string;
  email: string;
  password: string;
  department_id: number;
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
  const token = authStorage.getToken();
  const requestUrl = config.url ?? "";
  const isPublicAuthCall =
    requestUrl.includes("/login/") ||
    requestUrl.includes("/signup/") ||
    requestUrl.includes("/api/token/refresh/");

  if (token && !isPublicAuthCall) {
    config.headers.Authorization = `Bearer ${token}`;
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

export const institutionsApi = {
  getInstitutions: async (): Promise<InstitutionsResponse> => {
    const response = await apiClient.get<InstitutionsResponse>("/api/institutions");
    return response.data;
  },
};

export const departmentsApi = {
  getDepartments: async (institutionId?: number): Promise<DepartmentsResponse> => {
    const params = institutionId ? { institution_id: institutionId } : undefined;
    const response = await apiClient.get<DepartmentsResponse>("/api/departments", { params });
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
  me: async (): Promise<AuthMeResponse> => {
    const response = await apiClient.get<AuthMeResponse>("/api/auth/me");
    return response.data;
  },
  logout: async (): Promise<void> => {
    const refresh = authStorage.getRefreshToken();
    if (refresh) {
      try {
        await apiClient.post("/api/auth/logout/", { refresh });
      } catch {
        // Silently proceed with local storage wipe
      }
    }
    authStorage.clearAuth();
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

export const studentExamApi = {
  getExams: async (): Promise<StudentExamListResponse> => {
    const response = await apiClient.get<StudentExamListResponse>('/api/student/exams/');
    return response.data;
  },
  startExam: async (examId: number): Promise<StudentExamStartResponse> => {
    const response = await apiClient.post<StudentExamStartResponse>(`/api/student/exams/${examId}/start/`, {});
    return response.data;
  },
  saveAnswer: async (attemptId: number, questionId: number, answerText: string): Promise<{ saved: boolean }> => {
    const response = await apiClient.post<{ saved: boolean }>(`/api/student/attempts/${attemptId}/save/`, {
      question_id: questionId,
      answer_text: answerText,
    });
    return response.data;
  },
  saveAnswersBatch: async (attemptId: number, answers: Array<{ question_id: number; answer_text: string }>): Promise<{ saved: boolean; count?: number }> => {
    const response = await apiClient.post<{ saved: boolean; count?: number }>(`/api/student/attempts/${attemptId}/save/`, {
      answers,
    });
    return response.data;
  },
  submitAttempt: async (attemptId: number): Promise<StudentAttemptResponse> => {
    const response = await apiClient.post<StudentAttemptResponse>(`/api/student/attempts/${attemptId}/submit/`, {});
    return response.data;
  },
  getAttempt: async (attemptId: number): Promise<StudentAttemptResponse> => {
    const response = await apiClient.get<StudentAttemptResponse>(`/api/student/attempts/${attemptId}/`);
    return response.data;
  },
};

export const studentPerformanceApi = {
  getSummary: async (): Promise<StudentPerformanceSummaryResponse> => {
    const response = await apiClient.get<StudentPerformanceSummaryResponse>("/api/student/performance/summary/");
    return response.data;
  },
  getResults: async (params?: {
    search?: string;
    subject?: string;
    status?: string;
    start_date?: string;
    end_date?: string;
    sort?: string;
    page?: number;
    page_size?: number;
  }): Promise<StudentPerformanceResultsResponse> => {
    const response = await apiClient.get<StudentPerformanceResultsResponse>("/api/student/performance/results/", {
      params,
    });
    return response.data;
  },
  getTrend: async (): Promise<StudentPerformanceTrendResponse> => {
    const response = await apiClient.get<StudentPerformanceTrendResponse>("/api/student/performance/trend/");
    return response.data;
  },
  getSubjects: async (): Promise<StudentPerformanceSubjectsResponse> => {
    const response = await apiClient.get<StudentPerformanceSubjectsResponse>("/api/student/performance/subjects/");
    return response.data;
  },
};

export const studentDashboardApi = {
  getDashboard: async (): Promise<StudentDashboardResponse> => {
    const response = await apiClient.get<StudentDashboardResponse>("/api/student/dashboard/");
    return response.data;
  },
};

export const facultyDashboardApi = {
  getDashboard: async (): Promise<FacultyDashboardResponse> => {
    const response = await apiClient.get<FacultyDashboardResponse>("/api/faculty/dashboard/");
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

export const adminStudentsApi = {
  getStudents: async (params?: {
    search?: string;
    department?: string;
    score_range?: string;
    sort?: string;
    page?: number;
    page_size?: number;
  }): Promise<AdminStudentListResponse> => {
    const response = await apiClient.get<AdminStudentListResponse>('/api/admin/students', {
      params,
    });
    return response.data;
  },
  getStudentById: async (studentId: number): Promise<AdminStudentDetailResponse> => {
    const response = await apiClient.get<AdminStudentDetailResponse>(`/api/admin/students/${studentId}`);
    return response.data;
  },
  getStudentResults: async (studentId: number): Promise<AdminStudentResultsResponse> => {
    const response = await apiClient.get<AdminStudentResultsResponse>(`/api/admin/students/${studentId}/results`);
    return response.data;
  },
  createStudent: async (payload: AdminStudentCreatePayload): Promise<AdminStudentDetailResponse> => {
    const response = await apiClient.post<AdminStudentDetailResponse>("/api/admin/students", payload);
    return response.data;
  },
  updateStudent: async (
    studentId: number,
    payload: {
      first_name: string;
      last_name: string;
      email: string;
      student_id: string;
      department_id: number;
    }
  ): Promise<AdminStudentDetailResponse> => {
    const response = await apiClient.put<AdminStudentDetailResponse>(`/api/admin/students/${studentId}`, payload);
    return response.data;
  },
  deleteStudent: async (studentId: number): Promise<{ status: string; message: string }> => {
    const response = await apiClient.delete<{ status: string; message: string }>(`/api/admin/students/${studentId}`);
    return response.data;
  },
};

export type AdminFacultyRow = {
  id: number;
  full_name: string;
  email: string;
  employee_id?: string;
  department?: string;
  designation?: string;
  status?: string;
  is_active?: boolean;
  institution?: InstitutionOption | null;
  institution_id?: number | null;
  institute_id?: number | null;
};

export const facultyPaperApi = {
  uploadSyllabus: async (
    file: File,
    onUploadProgress?: (progress: number) => void
  ): Promise<SyllabusUploadResponse> => {
    const formData = new FormData();
    formData.append("file", file);
    const response = await apiClient.post<SyllabusUploadResponse>("/api/faculty/upload-syllabus", formData, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: (event) => {
        if (!event.total) return;
        onUploadProgress?.(Math.round((event.loaded * 100) / event.total));
      },
    });
    return response.data;
  },
  generatePaper: async (payload: GeneratePaperPayload): Promise<GeneratedPaperResponse> => {
    const response = await apiClient.post<GeneratedPaperResponse>("/api/faculty/generate-paper", payload, {
      timeout: 190000,
    });
    return response.data;
  },
  generateExam: async (payload: {
    title: string;
    durationMinutes: number;
    totalMarks: number;
    topics: string[];
    questionTypes: string[];
    difficultyDistribution: Record<string, number>;
    aiModel?: AiModel;
    syllabus?: File | null;
    avoidRepeats?: boolean;
    forceRegenerate?: boolean;
    subjectId?: number;
  }): Promise<GenerateExamResponse> => {
    const formData = new FormData();
    formData.append("title", payload.title);
    formData.append("duration_minutes", String(payload.durationMinutes));
    formData.append("total_marks", String(payload.totalMarks));
    payload.topics.forEach((topic) => formData.append("topics", topic));
    payload.questionTypes.forEach((questionType) => formData.append("question_types", questionType));
    formData.append("difficulty_distribution", JSON.stringify(payload.difficultyDistribution));
    if (payload.aiModel) formData.append("ai_model", payload.aiModel);
    if (payload.syllabus) formData.append("syllabus", payload.syllabus);
    formData.append("avoid_repeats", payload.avoidRepeats !== false ? "true" : "false");
    if (payload.forceRegenerate) formData.append("force_regenerate", "true");
    if (payload.subjectId) formData.append("subject_id", String(payload.subjectId));

    const response = await apiClient.post<GenerateExamResponse>("/api/faculty/exams/generate/", formData, {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 190000,
    });
    return response.data;
  },
  getOllamaStatus: async (): Promise<OllamaStatusResponse> => {
    const response = await apiClient.get<OllamaStatusResponse>("/api/faculty/ollama-status");
    return response.data;
  },
  getHistory: async (): Promise<PaperHistoryResponse> => {
    const response = await apiClient.get<PaperHistoryResponse>("/api/faculty/paper-history");
    return response.data;
  },
  getPaper: async (paperId: number): Promise<GeneratedPaperResponse> => {
    const response = await apiClient.get<GeneratedPaperResponse>(`/api/faculty/paper/${paperId}`);
    return response.data;
  },
  deletePaper: async (paperId: number): Promise<{ status: string; message: string }> => {
    const response = await apiClient.delete<{ status: string; message: string }>(`/api/faculty/paper/${paperId}`);
    return response.data;
  },
  exportPaper: async (paperId: number, format: "pdf" | "docx"): Promise<Blob> => {
    const response = await apiClient.get(`/api/faculty/paper/${paperId}/export`, {
      params: { format },
      responseType: "blob",
    });
    return response.data;
  },
};

export const facultyExamApi = {
  getExams: async (): Promise<FacultyExam[] | { results: FacultyExam[] }> => {
    const response = await apiClient.get<FacultyExam[] | { results: FacultyExam[] }>("/api/faculty/exams/");
    return response.data;
  },
  getExam: async (examId: number): Promise<FacultyExam> => {
    const response = await apiClient.get<FacultyExam>(`/api/faculty/exams/${examId}/`);
    return response.data;
  },
  updateQuestion: async (examId: number, questionId: number, question: Partial<ExamQuestion>): Promise<ExamQuestion> => {
    const response = await apiClient.put<ExamQuestion>(`/api/faculty/exams/${examId}/questions/${questionId}/`, question);
    return response.data;
  },
  publishExam: async (examId: number): Promise<FacultyExam> => {
    const response = await apiClient.post<FacultyExam>(`/api/faculty/exams/${examId}/publish/`, {});
    return response.data;
  },
  shuffleExam: async (examId: number): Promise<FacultyExam> => {
    const response = await apiClient.post<FacultyExam>(`/api/faculty/exams/${examId}/shuffle/`, {});
    return response.data;
  },
  swapQuestion: async (examId: number, questionId: number): Promise<{ question: ExamQuestion; validation_report: any }> => {
    const response = await apiClient.post<{ question: ExamQuestion; validation_report: any }>(
      `/api/faculty/exams/${examId}/questions/${questionId}/swap/`,
      {}
    );
    return response.data;
  },
  clearPaperCache: async (): Promise<{ status: string; message: string }> => {
    const response = await apiClient.delete<{ status: string; message: string }>("/api/faculty/exams/cache/");
    return response.data;
  },
  getExamAttempts: async (examId: number): Promise<{ exam_id: number; exam_title: string; attempts: any[] }> => {
    const response = await apiClient.get<{ exam_id: number; exam_title: string; attempts: any[] }>(`/api/faculty/exams/${examId}/attempts/`);
    return response.data;
  },
  getAttemptDetail: async (attemptId: number): Promise<any> => {
    const response = await apiClient.get<any>(`/api/faculty/attempts/${attemptId}/`);
    return response.data;
  },
  reevaluateAttempt: async (attemptId: number, force: boolean = false): Promise<any> => {
    const response = await apiClient.post<any>(`/api/faculty/attempts/${attemptId}/re-evaluate/`, { force });
    return response.data;
  },
  reevaluateAnswer: async (answerId: number, force: boolean = false): Promise<any> => {
    const response = await apiClient.post<any>(`/api/faculty/answers/${answerId}/re-evaluate/`, { force });
    return response.data;
  },
  manualGradeAnswer: async (answerId: number, score: number, feedback: string): Promise<any> => {
    const response = await apiClient.post<any>(`/api/faculty/answers/${answerId}/manual-grade/`, { score, feedback });
    return response.data;
  },
};

export type AdminFacultyListResponse = {
  status: string;
  message: string;
  data: AdminFacultyRow[];
  total_faculty?: number;
  active_faculty?: number;
  inactive_faculty?: number;
  total_departments?: number;
  success?: boolean;
  statistics?: {
    total_faculty: number;
    active_faculty: number;
    inactive_faculty: number;
    total_departments: number;
  };
};

export type AdminFacultyDetailResponse = {
  status: string;
  message: string;
  data: AdminFacultyRow & { first_name?: string; last_name?: string };
};

export type AdminFacultyUpdatePayload = {
  first_name: string;
  last_name: string;
  email: string;
  employee_id?: string;
  department?: string;
  designation?: string;
  is_active?: boolean;
};

export type AdminFacultyCreatePayload = {
  first_name: string;
  last_name: string;
  email: string;
  employee_id: string;
  department_id: number;
  designation: string;
  is_active: boolean;
  password: string;
};

export const adminFacultyApi = {
  getFaculty: async (params?: { search?: string; department?: string; status?: string }): Promise<AdminFacultyListResponse> => {
    const response = await apiClient.get<AdminFacultyListResponse>('/api/admin/faculty', { params });
    return response.data;
  },
  createFaculty: async (payload: AdminFacultyCreatePayload): Promise<AdminFacultyDetailResponse> => {
    const response = await apiClient.post<AdminFacultyDetailResponse>('/api/admin/faculty', payload);
    return response.data;
  },
  getFacultyById: async (facultyId: number): Promise<AdminFacultyDetailResponse> => {
    const response = await apiClient.get<AdminFacultyDetailResponse>(`/api/admin/faculty/${facultyId}`);
    return response.data;
  },
  updateFaculty: async (facultyId: number, payload: AdminFacultyUpdatePayload): Promise<AdminFacultyDetailResponse> => {
    const response = await apiClient.put<AdminFacultyDetailResponse>(`/api/admin/faculty/${facultyId}`, payload);
    return response.data;
  },
  deleteFaculty: async (facultyId: number): Promise<{ status: string; message: string }> => {
    const response = await apiClient.delete<{ status: string; message: string }>(`/api/admin/faculty/${facultyId}`);
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

export type AdminExamFaculty = {
  id: number;
  name: string;
  first_name: string;
  last_name: string;
  email: string;
  department: string;
  employee_id: string | null;
  designation: string;
};

export type AdminExamQuestion = {
  id: number;
  order: number;
  question_type: string;
  difficulty: string;
  text: string;
  options: string[] | null;
  correct_answer: unknown;
  model_answer: string;
  marks: number;
  topic: string;
};

export type AdminExamItem = {
  id: number;
  title: string;
  subject: string;
  topics: string[];
  duration_minutes: number;
  total_marks: number;
  difficulty_distribution: Record<string, number>;
  question_types: string[];
  ai_model_used: string;
  status: string;
  error_message: string;
  starts_at: string | null;
  ends_at: string | null;
  created_at: string;
  updated_at: string;
  question_count: number;
  attempts_count: number;
  faculty: AdminExamFaculty;
};

export type AdminExamDetail = AdminExamItem & {
  source_syllabus_text: string;
  questions: AdminExamQuestion[];
};

export type AdminExamListResponse = {
  status: string;
  data: AdminExamItem[];
  pagination: {
    page: number;
    page_size: number;
    total_count: number;
    total_pages: number;
    has_next: boolean;
    has_prev: boolean;
  };
  stats: {
    total_exams: number;
    published_exams: number;
    draft_exams: number;
    created_this_week: number;
    live_exams?: number;
  };
  filter_options: {
    faculties: { id: number; name: string; email: string }[];
    departments: string[];
    subjects: string[];
    statuses: { value: string; label: string }[];
  };
};

export type AdminExamDetailResponse = {
  status: string;
  data: AdminExamDetail;
};

export type AdminExamsQueryParams = {
  page?: number;
  page_size?: number;
  search?: string;
  faculty?: string | number;
  subject?: string;
  department?: string;
  status?: string;
  start_date?: string;
  end_date?: string;
  sort?: string;
};

export const adminExamsApi = {
  getExams: async (params?: AdminExamsQueryParams): Promise<AdminExamListResponse> => {
    const response = await apiClient.get<AdminExamListResponse>('/api/admin/exams', { params });
    return response.data;
  },
  getExamDetail: async (examId: number): Promise<AdminExamDetailResponse> => {
    const response = await apiClient.get<AdminExamDetailResponse>(`/api/admin/exams/${examId}`);
    return response.data;
  },
  updateExamStatus: async (examId: number, status: string): Promise<AdminExamDetailResponse> => {
    const response = await apiClient.patch<AdminExamDetailResponse>(`/api/admin/exams/${examId}`, { status });
    return response.data;
  },
  deleteExam: async (examId: number): Promise<{ status: string; message: string }> => {
    const response = await apiClient.delete<{ status: string; message: string }>(`/api/admin/exams/${examId}`);
    return response.data;
  },
};

export type AdminDashboardProfile = {
  name: string;
  email: string;
  institution_name: string;
  institution_code: string;
};

export type AdminDashboardStats = {
  total_students: number;
  total_faculty: number;
  total_departments: number;
  total_exams: number;
  published_exams: number;
  draft_exams: number;
  upcoming_exams: number;
  ongoing_exams: number;
  completed_exams: number;
  total_attempts: number;
  overall_average: number | null;
  overall_pass_rate: number | null;
  new_students_this_week: number;
  new_faculty_this_week: number;
  new_exams_this_week: number;
  new_attempts_this_week: number;
};

export type AdminOngoingExam = {
  id: number;
  title: string;
  department: string;
  faculty_name: string;
  duration_minutes: number;
  total_marks: number;
  starts_at: string | null;
  ends_at: string | null;
  seconds_remaining?: number | null;
  eligible_count: number;
  eligible_students: number;
  submitted_count: number;
  in_progress_count?: number;
  not_started_count?: number;
  participation_percent?: number;
  ineligible_attempts?: number;
};

export type LiveRosterStudent = {
  student_id: string;
  user_id: number;
  name: string;
  full_name?: string;
  roll_number?: string;
  email: string;
  department: string;
  status: 'not_started' | 'in_progress' | 'submitted';
  started_at: string | null;
  submitted_at: string | null;
  score: number | null;
};

export type IneligibleAttempt = {
  student_id: string;
  user_id: number;
  name: string;
  student_name?: string;
  student_roll?: string;
  attempt_id?: number | string;
  email: string;
  department: string;
  status: string;
  started_at: string | null;
  submitted_at: string | null;
  score: number | null;
  reason: string;
};

export type LiveRosterResponse = {
  status: string;
  data: {
    exam: {
      id: number;
      title: string;
      department: string;
      faculty_name: string;
      starts_at: string | null;
      ends_at: string | null;
      seconds_remaining: number | null;
    };
    metrics: AdminOngoingExam;
    roster: LiveRosterStudent[];
    ineligible_attempts: IneligibleAttempt[];
    pagination: {
      page: number;
      page_size: number;
      total_items: number;
      total_pages: number;
    };
  };
};

export type AdminUpcomingExam = {
  id: number;
  title: string;
  department: string;
  faculty_name: string;
  duration_minutes: number;
  total_marks: number;
  starts_at: string | null;
  ends_at: string | null;
};

export type AdminDepartmentOverview = {
  department: string;
  students_count: number;
  faculty_count: number;
  exams_count: number;
  attempts_count: number;
  average_score: number | null;
  pass_rate: number | null;
};

export type AdminFacultyRanking = {
  faculty_id: number;
  name: string;
  email: string;
  department: string;
  employee_id: string;
  total_exams: number;
  published_exams: number;
  total_attempts: number;
};

export type AdminTopStudent = {
  student_id: number;
  name: string;
  roll_number: string;
  department: string;
  average_score: number;
  exams_taken: number;
};

export type AdminAtRiskStudent = {
  student_id: number;
  name: string;
  roll_number: string;
  department: string;
  average_score: number | null;
  exams_taken: number;
  type: 'low_score' | 'unattempted';
  issue: string;
};

export type AdminActivityTrendItem = {
  date: string;
  exams_created: number;
  attempts: number;
};

export type AdminScoreDistributionItem = {
  range: string;
  count: number;
  label: string;
};

export type AdminRecentActivityItem = {
  type: string;
  title: string;
  department: string;
  actor: string;
  timestamp: string;
};

export type AdminPendingActions = {
  draft_exams_count: number;
  empty_exams_count: number;
  unassigned_students_count: number;
};

export type AdminLiveSummary = {
  live_exams_count: number;
  total_eligible_unique: number;
  total_in_progress: number;
  total_submitted: number;
  total_not_started: number;
};

export type AdminDashboardData = {
  profile: AdminDashboardProfile;
  stats: AdminDashboardStats;
  live_summary?: AdminLiveSummary;
  live_total?: number;
  shown_count?: number;
  has_more?: boolean;
  ongoing_exams: AdminOngoingExam[];
  upcoming_exams: AdminUpcomingExam[];
  department_overview: AdminDepartmentOverview[];
  exams_per_faculty: AdminFacultyRanking[];
  top_students: AdminTopStudent[];
  at_risk_students: {
    low_scorers: AdminAtRiskStudent[];
    unattempted_students: AdminAtRiskStudent[];
  };
  activity_trend: AdminActivityTrendItem[];
  score_distribution: AdminScoreDistributionItem[];
  recent_activity: AdminRecentActivityItem[];
  pending_actions: AdminPendingActions;
  departments: string[];
};

export type AdminDashboardResponse = {
  status: string;
  data: AdminDashboardData;
};

export const adminDashboardApi = {
  getDashboard: async (params?: { department?: string; range?: string }): Promise<AdminDashboardResponse> => {
    const response = await apiClient.get<AdminDashboardResponse>('/api/admin/dashboard/', { params });
    return response.data;
  },
  getLiveRoster: async (
    examId: number,
    params?: { page?: number; page_size?: number; status?: string; search?: string }
  ): Promise<LiveRosterResponse> => {
    const response = await apiClient.get<LiveRosterResponse>(`/api/admin/exams/${examId}/live-roster/`, { params });
    return response.data;
  },
};

export type PublicStatsData = {
  total_students: number;
  total_faculty: number;
  total_exams: number;
  total_departments: number;
  total_institutes?: number;
  institutes?: number;
};

export type PublicStatsResponse = {
  status: string;
  data: PublicStatsData;
};

export const publicStatsApi = {
  getStats: async (): Promise<PublicStatsResponse> => {
    const response = await apiClient.get<PublicStatsResponse>('/api/public/stats/');
    return response.data;
  },
};

// ==================== QUESTION BANK ====================
export type BankOption = {
  id?: number;
  text: string;
  is_correct: boolean;
  order: number;
};

export type BankQuestion = {
  id: number;
  text: string;
  department: string;
  subject: number;
  subject_name: string;
  topic: number | null;
  topic_name: string;
  question_type: "MCQ_SINGLE" | "MCQ_MULTIPLE" | "TRUE_FALSE" | "SHORT_ANSWER" | "LONG_ANSWER";
  difficulty: "EASY" | "MEDIUM" | "HARD";
  marks: string | number;
  negative_marks: string | number;
  status: "ACTIVE" | "DRAFT" | "ARCHIVED";
  times_used: number;
  last_used_at: string | null;
  version: number;
  tags: string[];
  created_by_name: string;
  options_count: number;
  created_at: string;
  updated_at: string;
};

export type BankQuestionDetail = BankQuestion & {
  explanation: string;
  model_answer: string;
  options: BankOption[];
  is_deleted: boolean;
  warnings?: string[];
  usage_info?: {
    is_locked: boolean;
    reason: string;
    times_used: number;
    last_used_at: string | null;
    associated_exams: Array<{ id: number; title: string; status: string }>;
  };
  audit_logs?: Array<{
    id: number;
    action: string;
    user_name: string;
    changes: Record<string, any>;
    timestamp: string;
  }>;
};

export type BankSubject = {
  id: number;
  name: string;
  code: string;
  department: string;
  question_count: number;
  created_at: string;
  updated_at: string;
};

export type BankTopic = {
  id: number;
  name: string;
  subject: number;
  subject_name: string;
  question_count: number;
  created_at: string;
  updated_at: string;
};

export type QuestionBankStats = {
  total_questions: number;
  unused_count: number;
  by_difficulty: {
    Easy: number;
    Medium: number;
    Hard: number;
  };
  by_status: {
    Active: number;
    Draft: number;
    Archived: number;
  };
  by_type: Record<string, number>;
  by_department: Record<string, number>;
  most_used_questions: Array<{
    id: number;
    text: string;
    times_used: number;
    last_used_at: string | null;
    marks: number;
    difficulty: string;
  }>;
};

export type PaginatedQuestionsResponse = {
  count: number;
  total_pages: number;
  current_page: number;
  next: string | null;
  previous: string | null;
  results: BankQuestion[];
};

export type QuestionImportReportRow = {
  row_number: number;
  question_text: string;
  is_valid: boolean;
  errors: string[];
  warnings: string[];
};

export type QuestionImportResponse = {
  dry_run: boolean;
  message?: string;
  total_rows: number;
  valid_count: number;
  imported_count?: number;
  failed_count: number;
  row_results: QuestionImportReportRow[];
};

export const questionBankApi = {
  getQuestions: async (params?: Record<string, any>): Promise<PaginatedQuestionsResponse> => {
    const response = await apiClient.get<PaginatedQuestionsResponse>('/api/admin/question-bank/questions/', { params });
    return response.data;
  },

  getQuestion: async (id: number): Promise<BankQuestionDetail> => {
    const response = await apiClient.get<BankQuestionDetail>(`/api/admin/question-bank/questions/${id}/`);
    return response.data;
  },

  createQuestion: async (payload: Partial<BankQuestionDetail>): Promise<BankQuestionDetail> => {
    const response = await apiClient.post<BankQuestionDetail>('/api/admin/question-bank/questions/', payload);
    return response.data;
  },

  updateQuestion: async (id: number, payload: Partial<BankQuestionDetail>): Promise<BankQuestionDetail> => {
    const response = await apiClient.patch<BankQuestionDetail>(`/api/admin/question-bank/questions/${id}/`, payload);
    return response.data;
  },

  deleteQuestion: async (id: number): Promise<{ message: string }> => {
    const response = await apiClient.delete<{ message: string }>(`/api/admin/question-bank/questions/${id}/`);
    return response.data;
  },

  restoreQuestion: async (id: number): Promise<BankQuestionDetail> => {
    const response = await apiClient.post<BankQuestionDetail>(`/api/admin/question-bank/questions/${id}/restore/`, {});
    return response.data;
  },

  duplicateQuestion: async (id: number): Promise<BankQuestionDetail> => {
    const response = await apiClient.post<BankQuestionDetail>(`/api/admin/question-bank/questions/${id}/duplicate/`, {});
    return response.data;
  },

  bulkAction: async (action: string, ids: number[], target_value?: string): Promise<{ message: string; affected_count: number }> => {
    const response = await apiClient.post<{ message: string; affected_count: number }>('/api/admin/question-bank/questions/bulk-action/', {
      action,
      ids,
      target_value: target_value || '',
    });
    return response.data;
  },

  getStats: async (): Promise<QuestionBankStats> => {
    const response = await apiClient.get<QuestionBankStats>('/api/admin/question-bank/stats/');
    return response.data;
  },

  getSubjects: async (department?: string): Promise<BankSubject[]> => {
    const response = await apiClient.get<BankSubject[]>('/api/admin/question-bank/subjects/', {
      params: department ? { department } : undefined,
    });
    return response.data;
  },

  createSubject: async (payload: { name: string; department: string; code?: string }): Promise<BankSubject> => {
    const response = await apiClient.post<BankSubject>('/api/admin/question-bank/subjects/', payload);
    return response.data;
  },

  updateSubject: async (id: number, payload: Partial<BankSubject>): Promise<BankSubject> => {
    const response = await apiClient.put<BankSubject>(`/api/admin/question-bank/subjects/${id}/`, payload);
    return response.data;
  },

  deleteSubject: async (id: number): Promise<{ message: string }> => {
    const response = await apiClient.delete<{ message: string }>(`/api/admin/question-bank/subjects/${id}/`);
    return response.data;
  },

  getTopics: async (subjectId?: number): Promise<BankTopic[]> => {
    const response = await apiClient.get<BankTopic[]>('/api/admin/question-bank/topics/', {
      params: subjectId ? { subject: subjectId } : undefined,
    });
    return response.data;
  },

  createTopic: async (payload: { name: string; subject: number }): Promise<BankTopic> => {
    const response = await apiClient.post<BankTopic>('/api/admin/question-bank/topics/', payload);
    return response.data;
  },

  updateTopic: async (id: number, payload: Partial<BankTopic>): Promise<BankTopic> => {
    const response = await apiClient.put<BankTopic>(`/api/admin/question-bank/topics/${id}/`, payload);
    return response.data;
  },

  deleteTopic: async (id: number): Promise<{ message: string }> => {
    const response = await apiClient.delete<{ message: string }>(`/api/admin/question-bank/topics/${id}/`);
    return response.data;
  },

  bulkImport: async (file: File, dryRun: boolean = true, mode: string = 'all_or_nothing'): Promise<QuestionImportResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('mode', mode);
    const response = await apiClient.post<QuestionImportResponse>(
      `/api/admin/question-bank/questions/bulk-import/?dry_run=${dryRun}`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    );
    return response.data;
  },

  downloadExport: async (format: 'csv' | 'xlsx' = 'csv', filters?: Record<string, any>): Promise<Blob> => {
    const response = await apiClient.get('/api/admin/question-bank/questions/export/', {
      params: { ...(filters || {}), format },
      responseType: 'blob',
    });
    return response.data;
  },

  downloadTemplate: async (format: 'csv' | 'xlsx' = 'csv'): Promise<Blob> => {
    const response = await apiClient.get('/api/admin/question-bank/questions/template/', {
      params: { format },
      responseType: 'blob',
    });
    return response.data;
  },
};




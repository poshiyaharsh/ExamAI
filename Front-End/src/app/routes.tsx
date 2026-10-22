import { createBrowserRouter, Outlet } from "react-router-dom";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { NotificationPopupManager } from "./components/NotificationPopupManager";

function RootLayout() {
  return (
    <>
      <NotificationPopupManager />
      <Outlet />
    </>
  );
}


function PageLoader() {
  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center p-6 space-y-4">
      <div className="w-10 h-10 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
      <p className="text-sm text-gray-500 font-medium">Loading...</p>
    </div>
  );
}

function PublicRoute({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<PageLoader />}>{children}</Suspense>;
}

function AdminOnly({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute allowedRoles={["admin"]}>
      <Suspense fallback={<PageLoader />}>{children}</Suspense>
    </ProtectedRoute>
  );
}

function FacultyOnly({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute allowedRoles={["faculty"]}>
      <Suspense fallback={<PageLoader />}>{children}</Suspense>
    </ProtectedRoute>
  );
}

function StudentOnly({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute allowedRoles={["student"]}>
      <Suspense fallback={<PageLoader />}>{children}</Suspense>
    </ProtectedRoute>
  );
}

// Lazy loaded page components for optimal first-load code splitting
const Landing = lazy(() => import("./pages/Landing").then((m) => ({ default: m.Landing })));
const Login = lazy(() => import("./pages/Login").then((m) => ({ default: m.Login })));
const ForgotPassword = lazy(() => import("./pages/ForgotPassword").then((m) => ({ default: m.ForgotPassword })));
const AdminDashboard = lazy(() => import("./pages/AdminDashboard").then((m) => ({ default: m.AdminDashboard })));
const AdminExams = lazy(() => import("./pages/AdminExams").then((m) => ({ default: m.AdminExams })));
const AdminStudents = lazy(() => import("./pages/AdminStudents").then((m) => ({ default: m.AdminStudents })));
const AdminSettings = lazy(() => import("./pages/AdminSettings").then((m) => ({ default: m.AdminSettings })));
const AdminQuestionBank = lazy(() => import("./pages/AdminQuestionBank").then((m) => ({ default: m.AdminQuestionBank })));
const AdminFaculty = lazy(() => import("./pages/AdminFaculty").then((m) => ({ default: m.AdminFaculty })));
const FacultyDashboard = lazy(() => import("./pages/FacultyDashboard").then((m) => ({ default: m.FacultyDashboard })));
const FacultyGeneratePaper = lazy(() => import("./pages/FacultyGeneratePaper").then((m) => ({ default: m.FacultyGeneratePaper })));
const FacultyGeneratingPaper = lazy(() => import("./pages/FacultyGeneratingPaper").then((m) => ({ default: m.FacultyGeneratingPaper })));
const FacultyExamHistory = lazy(() => import("./pages/FacultyExamHistory").then((m) => ({ default: m.FacultyExamHistory })));
const FacultyLiveMonitor = lazy(() => import("./pages/FacultyLiveMonitor").then((m) => ({ default: m.FacultyLiveMonitor })));
const EditPaperPage = lazy(() => import("./pages/EditPaperPage").then((m) => ({ default: m.EditPaperPage })));
const FacultySettings = lazy(() => import("./pages/FacultySettings").then((m) => ({ default: m.FacultySettings })));
const QuestionBank = lazy(() => import("./pages/QuestionBank").then((m) => ({ default: m.QuestionBank })));
const StudentDashboard = lazy(() => import("./pages/StudentDashboard").then((m) => ({ default: m.StudentDashboard })));
const StudentExamsPage = lazy(() => import("./pages/StudentExamsPage").then((m) => ({ default: m.StudentExamsPage })));
const TakeExamPage = lazy(() => import("./pages/TakeExamPage").then((m) => ({ default: m.TakeExamPage })));
const ResultsPage = lazy(() => import("./pages/ResultsPage").then((m) => ({ default: m.ResultsPage })));
const StudentPerformance = lazy(() => import("./pages/StudentPerformance").then((m) => ({ default: m.StudentPerformance })));
const StudentSettings = lazy(() => import("./pages/StudentSettings").then((m) => ({ default: m.StudentSettings })));
const NotFound = lazy(() => import("./pages/NotFound").then((m) => ({ default: m.NotFound })));
const SuperAdminGateway = lazy(() => import("./pages/SuperAdminConsole").then((m) => ({ default: m.SuperAdminGateway })));

export const router = createBrowserRouter([
  {
    Component: RootLayout,
    children: [
      {
        path: "/",
        Component: () => (
          <PublicRoute>
            <Landing />
          </PublicRoute>
        ),
      },

  {
    path: "/login",
    Component: () => (
      <PublicRoute>
        <Login />
      </PublicRoute>
    ),
  },
  {
    path: "/forgot-password",
    Component: () => (
      <PublicRoute>
        <ForgotPassword />
      </PublicRoute>
    ),
  },
  {
    path: "/admin",
    Component: () => (
      <AdminOnly>
        <AdminDashboard />
      </AdminOnly>
    ),
  },
  {
    path: "/admin/exams",
    Component: () => (
      <AdminOnly>
        <AdminExams />
      </AdminOnly>
    ),
  },
  {
    path: "/admin/students",
    Component: () => (
      <AdminOnly>
        <AdminStudents />
      </AdminOnly>
    ),
  },
  {
    path: "/admin/settings",
    Component: () => (
      <AdminOnly>
        <AdminSettings />
      </AdminOnly>
    ),
  },
  {
    path: "/admin/question-bank",
    Component: () => (
      <AdminOnly>
        <AdminQuestionBank />
      </AdminOnly>
    ),
  },
  {
    path: "/admin/faculty",
    Component: () => (
      <AdminOnly>
        <AdminFaculty />
      </AdminOnly>
    ),
  },
  {
    path: "/faculty",
    Component: () => (
      <FacultyOnly>
        <FacultyDashboard />
      </FacultyOnly>
    ),
  },
  {
    path: "/faculty/generate",
    Component: () => (
      <FacultyOnly>
        <FacultyGeneratePaper />
      </FacultyOnly>
    ),
  },
  {
    path: "/faculty/history",
    Component: () => (
      <FacultyOnly>
        <FacultyExamHistory />
      </FacultyOnly>
    ),
  },
  {
    path: "/faculty/exams/:id/monitor",
    Component: () => (
      <FacultyOnly>
        <FacultyLiveMonitor />
      </FacultyOnly>
    ),
  },
  {
    path: "/faculty/exams/:id/generating",
    Component: () => (
      <FacultyOnly>
        <FacultyGeneratingPaper />
      </FacultyOnly>
    ),
  },
  {
    path: "/faculty/exams/:id/edit",
    Component: () => (
      <FacultyOnly>
        <EditPaperPage />
      </FacultyOnly>
    ),
  },
  {
    path: "/faculty/settings",
    Component: () => (
      <FacultyOnly>
        <FacultySettings />
      </FacultyOnly>
    ),
  },
  {
    path: "/question-bank",
    Component: () => (
      <PublicRoute>
        <QuestionBank />
      </PublicRoute>
    ),
  },
  {
    path: "/student",
    Component: () => (
      <StudentOnly>
        <StudentDashboard />
      </StudentOnly>
    ),
  },
  {
    path: "/student/exams",
    Component: () => (
      <StudentOnly>
        <StudentExamsPage />
      </StudentOnly>
    ),
  },
  {
    path: "/student/exams/:id/take",
    Component: () => (
      <StudentOnly>
        <TakeExamPage />
      </StudentOnly>
    ),
  },
  {
    path: "/student/results/:id",
    Component: () => (
      <StudentOnly>
        <ResultsPage />
      </StudentOnly>
    ),
  },
  {
    path: "/student/performance",
    Component: () => (
      <StudentOnly>
        <StudentPerformance />
      </StudentOnly>
    ),
  },
  {
    path: "/student/settings",
    Component: () => (
      <StudentOnly>
        <StudentSettings />
      </StudentOnly>
    ),
  },
  {
    path: "/:secretSlug/console/*",
    Component: () => (
      <PublicRoute>
        <SuperAdminGateway />
      </PublicRoute>
    ),
  },
  {
    path: "/:secretSlug/console",
    Component: () => (
      <PublicRoute>
        <SuperAdminGateway />
      </PublicRoute>
    ),
  },
      {
        path: "*",
        Component: () => (
          <PublicRoute>
            <NotFound />
          </PublicRoute>
        ),
      },
    ],
  },
]);


import { createBrowserRouter } from "react-router-dom";
import { Landing } from "./pages/Landing";
import { Login } from "./pages/Login";
import { ForgotPassword } from "./pages/ForgotPassword";
import { AdminDashboard } from "./pages/AdminDashboard";
import { AdminExams } from "./pages/AdminExams";
import { AdminStudents } from "./pages/AdminStudents";
import { AdminSettings } from "./pages/AdminSettings";
import { FacultyDashboard } from "./pages/FacultyDashboard";
import { FacultyGeneratePaper } from "./pages/FacultyGeneratePaper";
import { FacultyGeneratingPaper } from "./pages/FacultyGeneratingPaper";
import { FacultyExamHistory } from "./pages/FacultyExamHistory";
import { FacultyLiveMonitor } from "./pages/FacultyLiveMonitor";
import { EditPaperPage } from "./pages/EditPaperPage";
import { FacultySettings } from "./pages/FacultySettings";
import { QuestionBank } from "./pages/QuestionBank";
import { AdminQuestionBank } from "./pages/AdminQuestionBank";
import { AdminFaculty } from "./pages/AdminFaculty";
import { StudentDashboard } from "./pages/StudentDashboard";
import { StudentExamsPage } from "./pages/StudentExamsPage";
import { TakeExamPage } from "./pages/TakeExamPage";
import { ResultsPage } from "./pages/ResultsPage";
import { StudentPerformance } from "./pages/StudentPerformance";
import { StudentSettings } from "./pages/StudentSettings";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { NotFound } from "./pages/NotFound";

function AdminOnly({ children }: { children: React.ReactNode }) {
  return <ProtectedRoute allowedRoles={["admin"]}>{children}</ProtectedRoute>;
}

function FacultyOnly({ children }: { children: React.ReactNode }) {
  return <ProtectedRoute allowedRoles={["faculty"]}>{children}</ProtectedRoute>;
}

function StudentOnly({ children }: { children: React.ReactNode }) {
  return <ProtectedRoute allowedRoles={["student"]}>{children}</ProtectedRoute>;
}

export const router = createBrowserRouter([
  {
    path: "/",
    Component: Landing,
  },
  {
    path: "/login",
    Component: Login,
  },
  {
    path: "/forgot-password",
    Component: ForgotPassword,
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
    Component: QuestionBank,
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
    path: "*",
    Component: NotFound,
  },
]);

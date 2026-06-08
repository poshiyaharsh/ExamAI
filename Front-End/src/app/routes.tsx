import { createBrowserRouter } from "react-router";
import { Landing } from "./pages/Landing";
import { Login } from "./pages/Login";
import { ForgotPassword } from "./pages/ForgotPassword";
import { AdminDashboard } from "./pages/AdminDashboard";
import { AdminExams } from "./pages/AdminExams";
import { AdminStudents } from "./pages/AdminStudents";
import { AdminSettings } from "./pages/AdminSettings";
import { FacultyDashboard } from "./pages/FacultyDashboard";
import { FacultyGeneratePaper } from "./pages/FacultyGeneratePaper";
import { FacultyExamHistory } from "./pages/FacultyExamHistory";
import { FacultySettings } from "./pages/FacultySettings";
import { QuestionBank } from "./pages/QuestionBank";
import { AdminQuestionBank } from "./pages/AdminQuestionBank";
import { AdminFaculty } from "./pages/AdminFaculty";
import { StudentDashboard } from "./pages/StudentDashboard";
import { StudentExams } from "./pages/StudentExams";
import { StudentPerformance } from "./pages/StudentPerformance";
import { StudentSettings } from "./pages/StudentSettings";
import { ExamInterface } from "./pages/ExamInterface";
import { ResultPage } from "./pages/ResultPage";
import { ProtectedRoute } from "./components/ProtectedRoute";

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
        <StudentExams />
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
    path: "/exam/:id",
    Component: () => (
      <StudentOnly>
        <ExamInterface />
      </StudentOnly>
    ),
  },
  {
    path: "/result/:id",
    Component: () => (
      <StudentOnly>
        <ResultPage />
      </StudentOnly>
    ),
  },
]);

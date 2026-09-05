import { useEffect, useState } from "react";
import { Clock, FileText, LayoutDashboard, Settings, TrendingUp } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { DashboardLayout } from "../components/DashboardLayout";
import { studentExamApi, type StudentExamSummary } from "../../services/api";

const menuItems = [
  { icon: LayoutDashboard, label: "Dashboard", path: "/student" },
  { icon: FileText, label: "Exams", path: "/student/exams" },
  { icon: TrendingUp, label: "Performance", path: "/student/performance" },
  { icon: Settings, label: "Settings", path: "/student/settings" },
];

function formatWindow(exam: StudentExamSummary["exam"]) {
  if (exam.ends_at) return `Closes ${new Date(exam.ends_at).toLocaleString()}`;
  if (exam.starts_at) return `Starts ${new Date(exam.starts_at).toLocaleString()}`;
  return "Open now";
}

export function StudentExamsPage() {
  const navigate = useNavigate();
  const [exams, setExams] = useState<StudentExamSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    studentExamApi.getExams()
      .then(setExams)
      .catch(() => toast.error("Unable to load exams."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <DashboardLayout menuItems={menuItems} userRole="Student">
      <div className="space-y-6">
        <div><h1 className="text-3xl font-bold text-foreground">Available Exams</h1><p className="mt-2 text-muted-foreground">Start an exam when its window opens.</p></div>
        {loading ? <p className="text-muted-foreground">Loading exams...</p> : exams.length === 0 ? <p className="text-muted-foreground">No published exams are available.</p> : (
          <div className="grid gap-4 lg:grid-cols-2">
            {exams.map(({ exam, completed, attempt_id: attemptId, available }) => (
              <article key={exam.id} className="rounded-xl border border-border bg-white p-6">
                <div className="flex items-start justify-between gap-4">
                  <div><h2 className="text-lg font-semibold">{exam.title}</h2><p className="mt-1 text-sm text-muted-foreground">{exam.topics.join(", ")}</p></div>
                  <FileText className="h-5 w-5 text-primary" />
                </div>
                <div className="mt-5 grid grid-cols-2 gap-3 text-sm text-muted-foreground"><span>{exam.duration_minutes} minutes</span><span>{exam.total_marks} marks</span><span>{exam.questions?.length ?? 0} questions</span><span className="inline-flex items-center gap-1"><Clock className="h-4 w-4" /> {formatWindow(exam)}</span></div>
                <div className="mt-5 flex items-center justify-between gap-3"><span className={`text-sm font-medium ${completed ? "text-emerald-600" : available ? "text-primary" : "text-amber-600"}`}>{completed ? "Completed" : available ? "Ready to start" : "Not open yet"}</span>{completed && attemptId ? <button type="button" onClick={() => navigate(`/student/results/${attemptId}`)} className="rounded-lg border border-border px-4 py-2 text-sm">View result</button> : <button type="button" disabled={!available} onClick={() => navigate(`/student/exams/${exam.id}/take`)} className="rounded-lg bg-primary px-4 py-2 text-sm text-white disabled:cursor-not-allowed disabled:opacity-50">Start exam</button>}</div>
              </article>
            ))}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

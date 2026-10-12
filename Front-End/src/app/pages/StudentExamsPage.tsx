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
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-foreground mb-1">Available Exams</h1>
          <p className="text-xs sm:text-sm text-muted-foreground">Start an exam when its window opens.</p>
        </div>
        {loading ? (
          <p className="text-sm text-muted-foreground">Loading exams...</p>
        ) : exams.length === 0 ? (
          <div className="rounded-xl border border-border bg-white p-8 text-center text-sm text-muted-foreground shadow-sm">
            No exams available for your department right now.
          </div>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {exams.map(({ exam, completed, attempt_id: attemptId, available }) => (
              <article key={exam.id} className="rounded-xl border border-border bg-white p-5 sm:p-6 shadow-sm hover:shadow-md transition-all">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <h2 className="text-base sm:text-lg font-semibold text-foreground">{exam.title}</h2>
                      {exam.department && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-primary/10 text-primary border border-primary/20">
                          {exam.department}
                        </span>
                      )}
                    </div>
                    <p className="text-xs sm:text-sm text-muted-foreground">{exam.topics.join(", ")}</p>
                  </div>
                  <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                    <FileText className="h-5 w-5 text-primary" />
                  </div>
                </div>
                <div className="mt-4 grid grid-cols-2 gap-2.5 text-xs sm:text-sm text-muted-foreground">
                  <span>{exam.duration_minutes} minutes</span>
                  <span>{exam.total_marks} marks</span>
                  <span>{exam.questions?.length ?? 0} questions</span>
                  <span className="inline-flex items-center gap-1.5"><Clock className="h-3.5 w-3.5" /> {formatWindow(exam)}</span>
                </div>
                <div className="mt-5 flex items-center justify-between gap-3 pt-3 border-t border-border/60">
                  <span className={`text-xs sm:text-sm font-medium ${completed ? "text-emerald-600" : available ? "text-primary" : "text-amber-600"}`}>
                    {completed ? "Completed" : available ? "Ready to start" : "Not open yet"}
                  </span>
                  {completed && attemptId ? (
                    <button
                      type="button"
                      onClick={() => navigate(`/student/results/${attemptId}`)}
                      className="rounded-lg border border-border px-3.5 py-1.5 text-xs sm:text-sm font-medium text-foreground hover:bg-muted/50 transition-colors"
                    >
                      View result
                    </button>
                  ) : (
                    <button
                      type="button"
                      disabled={!available}
                      onClick={() => navigate(`/student/exams/${exam.id}/take`)}
                      className="rounded-lg bg-gradient-to-r from-primary to-secondary px-4 py-2 text-xs sm:text-sm font-medium text-white shadow-sm hover:opacity-90 transition-all disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      Start exam
                    </button>
                  )}
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

import { useEffect, useState } from "react";
import { Edit3, Eye, FileText, History, LayoutDashboard, Settings } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { DashboardLayout } from "../components/DashboardLayout";
import { facultyExamApi, type FacultyExam } from "../../services/api";

const menuItems = [
  { icon: LayoutDashboard, label: "Dashboard", path: "/faculty" },
  { icon: FileText, label: "Generate Paper", path: "/faculty/generate" },
  { icon: History, label: "Exam History", path: "/faculty/history" },
  { icon: Settings, label: "Settings", path: "/faculty/settings" },
];

export function FacultyExamHistory() {
  const navigate = useNavigate();
  const [exams, setExams] = useState<FacultyExam[]>([]);
  const [loading, setLoading] = useState(true);

  const loadExams = async () => {
    try {
      const response = await facultyExamApi.getExams();
      console.log("[FacultyExamHistory] raw /api/faculty/exams/ response", response);
      const exams = Array.isArray(response) ? response : response.results ?? [];
      setExams(exams);
    } catch {
      toast.error("Unable to load exams.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadExams();
  }, []);

  const publish = async (examId: number) => {
    try {
      const published = await facultyExamApi.publishExam(examId);
      setExams((current) => current.map((exam) => exam.id === examId ? published : exam));
      toast.success("Exam published.");
    } catch {
      toast.error("Publishing failed. Check the question marks first.");
    }
  };

  return (
    <DashboardLayout menuItems={menuItems} userRole="Faculty">
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-foreground mb-1">Exam History</h1>
          <p className="text-xs sm:text-sm text-muted-foreground">Review generated papers and manage publication.</p>
        </div>
        {loading ? (
          <p className="text-sm text-muted-foreground">Loading exams...</p>
        ) : exams.length === 0 ? (
          <div className="rounded-xl border border-border bg-white p-8 text-center text-sm text-muted-foreground shadow-sm">
            No exams generated yet.
          </div>
        ) : (
          <div className="space-y-4">
            {exams.map((exam) => (
              <div key={exam.id} className="rounded-xl border border-border bg-white p-5 sm:p-6 shadow-sm hover:shadow-md transition-all">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                  <div>
                    <div className="flex items-center gap-3">
                      <h2 className="text-base sm:text-lg font-semibold text-foreground">{exam.title}</h2>
                      <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium border ${exam.status === "published" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : exam.status === "closed" ? "bg-muted text-muted-foreground border-border" : "bg-amber-50 text-amber-700 border-amber-200"}`}>
                        {exam.status}
                      </span>
                    </div>
                    <p className="mt-1.5 text-xs sm:text-sm text-muted-foreground">
                      {exam.question_count ?? exam.questions?.length ?? 0} questions · {exam.total_marks} marks · {exam.duration_minutes} minutes
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={() => navigate(`/faculty/exams/${exam.id}/edit`)}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3.5 py-2 text-xs sm:text-sm font-medium text-foreground hover:bg-muted/50 transition-colors"
                    >
                      <Edit3 className="h-4 w-4" /> Edit
                    </button>
                    {exam.status !== "published" && (
                      <button
                        type="button"
                        onClick={() => void publish(exam.id)}
                        className="inline-flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-primary to-secondary px-3.5 py-2 text-xs sm:text-sm font-medium text-white shadow-sm hover:opacity-90 transition-all"
                      >
                        Publish
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => toast.info(`Attempts: ${exam.attempts_count ?? 0}`)}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3.5 py-2 text-xs sm:text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                    >
                      <Eye className="h-4 w-4" /> View attempts
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}

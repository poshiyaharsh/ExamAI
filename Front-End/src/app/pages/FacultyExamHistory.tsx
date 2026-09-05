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
          <h1 className="text-3xl font-bold text-foreground">Exam History</h1>
          <p className="mt-2 text-muted-foreground">Review generated papers and manage publication.</p>
        </div>
        {loading ? <p className="text-muted-foreground">Loading exams...</p> : exams.length === 0 ? <p className="text-muted-foreground">No exams generated yet.</p> : (
          <div className="space-y-4">
            {exams.map((exam) => (
              <div key={exam.id} className="rounded-xl border border-border bg-white p-6">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                  <div>
                    <div className="flex items-center gap-3">
                      <h2 className="text-lg font-semibold">{exam.title}</h2>
                      <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${exam.status === "published" ? "bg-emerald-100 text-emerald-700" : exam.status === "closed" ? "bg-slate-100 text-slate-700" : "bg-amber-100 text-amber-700"}`}>{exam.status}</span>
                    </div>
                    <p className="mt-2 text-sm text-muted-foreground">{exam.question_count ?? exam.questions?.length ?? 0} questions · {exam.total_marks} marks · {exam.duration_minutes} minutes</p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <button type="button" onClick={() => navigate(`/faculty/exams/${exam.id}/edit`)} className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm hover:bg-muted"><Edit3 className="h-4 w-4" /> Edit</button>
                    {exam.status !== "published" && <button type="button" onClick={() => void publish(exam.id)} className="rounded-lg bg-primary px-3 py-2 text-sm text-white">Publish</button>}
                    <button type="button" onClick={() => toast.info(`Attempts: ${exam.attempts_count ?? 0}`)} className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm hover:bg-muted"><Eye className="h-4 w-4" /> View attempts</button>
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

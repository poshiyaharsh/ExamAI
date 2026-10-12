import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { AlertCircle, LoaderCircle, RefreshCw } from "lucide-react";
import { DashboardLayout } from "../components/DashboardLayout";
import { facultyExamApi } from "../../services/api";

const menuItems = [
  { icon: RefreshCw, label: "Generate Paper", path: "/faculty/generate" },
];

export function FacultyGeneratingPaper() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [error, setError] = useState("");

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const exam = await facultyExamApi.getExam(Number(id));
        if (cancelled) return;
        if (exam.status === "draft") {
          navigate(`/faculty/exams/${id}/edit`, { replace: true });
        } else if (exam.status === "failed") {
          setError(exam.error_message || "Paper generation failed.");
        } else {
          window.setTimeout(() => void poll(), 4000);
        }
      } catch {
        if (!cancelled) setError("Unable to check generation status.");
      }
    };
    void poll();
    return () => {
      cancelled = true;
    };
  }, [id, navigate]);

  return (
    <DashboardLayout menuItems={menuItems} userRole="Faculty">
      <div className="mx-auto max-w-xl rounded-xl border border-border bg-white p-8 sm:p-10 text-center shadow-sm my-8">
        {error ? (
          <>
            <div className="w-14 h-14 rounded-2xl bg-rose-50 border border-rose-200 flex items-center justify-center mx-auto mb-4 text-rose-600">
              <AlertCircle className="h-7 w-7" />
            </div>
            <h1 className="text-xl sm:text-2xl font-bold text-foreground">Unable to generate paper</h1>
            <p className="mt-2 text-xs sm:text-sm text-destructive">{error}</p>
            <button
              type="button"
              onClick={() => navigate("/faculty/generate")}
              className="mt-6 inline-flex items-center gap-2 rounded-lg bg-gradient-to-r from-primary to-secondary px-5 py-2.5 text-sm font-medium text-white shadow-md hover:opacity-90 transition-all"
            >
              <RefreshCw className="h-4 w-4" /> Retry
            </button>
          </>
        ) : (
          <>
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary/10 to-secondary/10 border border-primary/20 flex items-center justify-center mx-auto mb-5 shadow-xs">
              <LoaderCircle className="h-8 w-8 animate-spin text-primary" />
            </div>
            <h1 className="text-xl sm:text-2xl font-bold text-foreground">Generating paper...</h1>
            <p className="mt-2 text-xs sm:text-sm text-muted-foreground">Your paper is being generated with AI. This page will update automatically.</p>
          </>
        )}
      </div>
    </DashboardLayout>
  );
}

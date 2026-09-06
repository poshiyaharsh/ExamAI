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
      <div className="mx-auto max-w-2xl rounded-xl border border-border bg-white p-8 text-center shadow-sm">
        {error ? (
          <>
            <AlertCircle className="mx-auto mb-4 h-10 w-10 text-destructive" />
            <h1 className="text-2xl font-bold">Unable to generate paper</h1>
            <p className="mt-3 text-sm text-destructive">{error}</p>
            <button type="button" onClick={() => navigate("/faculty/generate")} className="mt-6 inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 font-medium text-white">
              <RefreshCw className="h-4 w-4" /> Retry
            </button>
          </>
        ) : (
          <>
            <LoaderCircle className="mx-auto mb-4 h-10 w-10 animate-spin text-primary" />
            <h1 className="text-2xl font-bold">Generating paper...</h1>
            <p className="mt-3 text-sm text-muted-foreground">Your paper is being generated. This page will update automatically.</p>
          </>
        )}
      </div>
    </DashboardLayout>
  );
}

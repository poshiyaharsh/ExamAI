import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Check, Save } from "lucide-react";
import { toast } from "sonner";
import { DashboardLayout } from "../components/DashboardLayout";
import { facultyExamApi, type ExamQuestion, type FacultyExam } from "../../services/api";

const menuItems = [
  { icon: Save, label: "Generate Paper", path: "/faculty/generate" },
  { icon: Check, label: "Exam History", path: "/faculty/history" },
];

function questionPayload(question: ExamQuestion) {
  const correctAnswer = question.question_type === "mcq" && /^\d+$/.test(String(question.correct_answer ?? ""))
    ? Number(question.correct_answer)
    : question.correct_answer;
  return {
    question_type: question.question_type,
    difficulty: question.difficulty,
    text: question.text,
    options: question.options,
    correct_answer: correctAnswer,
    model_answer: question.model_answer,
    marks: Number(question.marks),
    topic: question.topic,
  };
}

export function EditPaperPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [exam, setExam] = useState<FacultyExam | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState<number | null>(null);

  useEffect(() => {
    if (!id) return;
    facultyExamApi.getExam(Number(id))
      .then(setExam)
      .catch(() => toast.error("Unable to load the generated paper."))
      .finally(() => setLoading(false));
  }, [id]);

  const updateQuestion = (questionId: number, update: Partial<ExamQuestion>) => {
    setExam((current) => current ? {
      ...current,
      questions: current.questions?.map((question) => question.id === questionId ? { ...question, ...update } : question),
    } : current);
  };

  const saveQuestion = async (question: ExamQuestion) => {
    if (!id) return;
    setSavingId(question.id);
    try {
      const saved = await facultyExamApi.updateQuestion(Number(id), question.id, questionPayload(question));
      updateQuestion(question.id, saved);
      toast.success(`Question ${question.order} saved.`);
    } catch {
      toast.error("Unable to save this question.");
    } finally {
      setSavingId(null);
    }
  };

  const publish = async () => {
    if (!id) return;
    try {
      const published = await facultyExamApi.publishExam(Number(id));
      setExam(published);
      toast.success("Exam published.");
      navigate("/faculty/history");
    } catch {
      toast.error("Publishing failed. Check that question marks equal the exam total.");
    }
  };

  return (
    <DashboardLayout menuItems={menuItems} userRole="Faculty">
      <div className="space-y-6">
        <button type="button" onClick={() => navigate("/faculty/history")} className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" /> Back to exam history
        </button>
        {loading ? <p className="text-muted-foreground">Loading generated paper...</p> : !exam ? <p className="text-destructive">Exam not found.</p> : (
          <>
            <div className="flex flex-col gap-4 rounded-xl border border-border bg-white p-5 sm:p-6 shadow-sm sm:flex-row sm:items-end sm:justify-between">
              <div>
                <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium border mb-2 capitalize ${exam.status === "published" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : exam.status === "closed" ? "bg-muted text-muted-foreground border-border" : "bg-amber-50 text-amber-700 border-amber-200"}`}>
                  {exam.status}
                </span>
                <h1 className="text-2xl sm:text-3xl font-bold text-foreground">{exam.title}</h1>
                <p className="mt-1.5 text-xs sm:text-sm text-muted-foreground">{exam.duration_minutes} minutes · {exam.questions?.length ?? 0} questions</p>
                <p className="mt-1 text-xs sm:text-sm font-semibold text-primary">Computed total: {exam.total_marks} marks</p>
              </div>
              <button
                type="button"
                onClick={() => void publish()}
                disabled={exam.status === "published"}
                className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-gradient-to-r from-primary to-secondary px-5 py-2.5 font-medium text-sm text-white shadow-md hover:opacity-90 transition-all disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Check className="h-4 w-4" /> Publish
              </button>
            </div>
            <div className="space-y-4">
              {exam.questions?.map((question) => (
                <section key={question.id} className="rounded-xl border border-border bg-white p-5 sm:p-6 shadow-sm hover:shadow-md transition-all">
                  <div className="mb-4 flex items-center justify-between gap-4">
                    <h2 className="text-sm sm:text-base font-semibold text-foreground">Q{question.order} · {question.marks} {question.marks === 1 ? "mark" : "marks"}</h2>
                    <button
                      type="button"
                      onClick={() => void saveQuestion(question)}
                      disabled={savingId === question.id}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3.5 py-1.5 text-xs sm:text-sm font-medium hover:bg-muted/50 transition-colors disabled:opacity-50"
                    >
                      <Save className="h-4 w-4" /> {savingId === question.id ? "Saving..." : "Save"}
                    </button>
                  </div>
                  <textarea
                    value={question.text}
                    onChange={(event) => updateQuestion(question.id, { text: event.target.value })}
                    rows={4}
                    className="w-full rounded-lg bg-input-background border border-border p-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                  />
                  <div className="mt-4 grid gap-3.5 sm:grid-cols-3">
                    <label className="text-xs font-medium text-foreground">
                      Marks
                      <input type="number" value={question.question_type === "subjective" ? 10 : 1} readOnly className="mt-1.5 w-full cursor-not-allowed rounded-lg border border-border bg-muted/60 px-3 py-2 text-sm text-muted-foreground" />
                    </label>
                    <label className="text-xs font-medium text-foreground">
                      Correct answer
                      <input aria-label={`Correct answer for question ${question.order}`} value={String(question.correct_answer ?? "")} onChange={(event) => updateQuestion(question.id, { correct_answer: event.target.value })} className="mt-1.5 w-full rounded-lg bg-input-background border border-border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all" />
                    </label>
                    <label className="text-xs font-medium text-foreground">
                      Topic
                      <input value={question.topic} onChange={(event) => updateQuestion(question.id, { topic: event.target.value })} className="mt-1.5 w-full rounded-lg bg-input-background border border-border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all" />
                    </label>
                  </div>
                  {question.options && (
                    <div className="mt-4 space-y-2">
                      <p className="text-xs font-medium text-foreground">Options</p>
                      {question.options.map((option, index) => (
                        <label key={`${question.id}-${index}`} className="flex items-center gap-2 text-sm">
                          <span className="w-6 font-semibold text-primary text-xs">{String.fromCharCode(65 + index)})</span>
                          <input value={option} onChange={(event) => updateQuestion(question.id, { options: question.options?.map((current, optionIndex) => optionIndex === index ? event.target.value : current) })} className="w-full rounded-lg bg-input-background border border-border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all" />
                        </label>
                      ))}
                    </div>
                  )}
                  {question.question_type === "subjective" && (
                    <label className="mt-4 block text-xs font-medium text-foreground">
                      Model answer
                      <textarea aria-label={`Model answer for question ${question.order}`} value={question.model_answer} onChange={(event) => updateQuestion(question.id, { model_answer: event.target.value })} rows={4} className="mt-1.5 w-full rounded-lg bg-input-background border border-border p-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all" />
                    </label>
                  )}
                </section>
              ))}
            </div>
          </>
        )}
      </div>
    </DashboardLayout>
  );
}

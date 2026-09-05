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
            <div className="flex flex-col gap-4 rounded-xl border border-border bg-white p-6 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <p className="text-sm text-muted-foreground">{exam.status}</p>
                <h1 className="text-3xl font-bold text-foreground">{exam.title}</h1>
                <p className="mt-2 text-sm text-muted-foreground">{exam.duration_minutes} minutes · {exam.questions?.length ?? 0} questions</p>
                <p className="mt-1 text-sm font-medium text-primary">Computed total: {exam.total_marks} marks</p>
              </div>
              <button type="button" onClick={() => void publish()} disabled={exam.status === "published"} className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2 font-medium text-white disabled:cursor-not-allowed disabled:opacity-50">
                <Check className="h-4 w-4" /> Publish
              </button>
            </div>
            <div className="space-y-4">
              {exam.questions?.map((question) => (
                <section key={question.id} className="rounded-xl border border-border bg-white p-6">
                  <div className="mb-4 flex items-center justify-between gap-4">
                    <h2 className="font-semibold">Q{question.order} · {question.marks} {question.marks === 1 ? "mark" : "marks"}</h2>
                    <button type="button" onClick={() => void saveQuestion(question)} disabled={savingId === question.id} className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm disabled:opacity-50">
                      <Save className="h-4 w-4" /> {savingId === question.id ? "Saving..." : "Save"}
                    </button>
                  </div>
                  <textarea value={question.text} onChange={(event) => updateQuestion(question.id, { text: event.target.value })} rows={4} className="w-full rounded-lg border border-border p-3" />
                  <div className="mt-4 grid gap-4 sm:grid-cols-3">
                    <label className="text-sm font-medium">Marks<input type="number" value={question.question_type === "subjective" ? 10 : 1} readOnly className="mt-1 w-full cursor-not-allowed rounded-lg border border-border bg-muted p-2" /></label>
                    <label className="text-sm font-medium">Correct answer<input aria-label={`Correct answer for question ${question.order}`} value={String(question.correct_answer ?? "")} onChange={(event) => updateQuestion(question.id, { correct_answer: event.target.value })} className="mt-1 w-full rounded-lg border border-border p-2" /></label>
                    <label className="text-sm font-medium">Topic<input value={question.topic} onChange={(event) => updateQuestion(question.id, { topic: event.target.value })} className="mt-1 w-full rounded-lg border border-border p-2" /></label>
                  </div>
                  {question.options && (
                    <div className="mt-4 space-y-2"><p className="text-sm font-medium">Options</p>{question.options.map((option, index) => <label key={`${question.id}-${index}`} className="flex items-center gap-2 text-sm"><span className="w-6 font-semibold">{String.fromCharCode(65 + index)})</span><input value={option} onChange={(event) => updateQuestion(question.id, { options: question.options?.map((current, optionIndex) => optionIndex === index ? event.target.value : current) })} className="w-full rounded-lg border border-border p-2" /></label>)}</div>
                  )}
                  {question.question_type === "subjective" && <label className="mt-4 block text-sm font-medium">Model answer<textarea aria-label={`Model answer for question ${question.order}`} value={question.model_answer} onChange={(event) => updateQuestion(question.id, { model_answer: event.target.value })} rows={4} className="mt-1 w-full rounded-lg border border-border p-3" /></label>}
                </section>
              ))}
            </div>
          </>
        )}
      </div>
    </DashboardLayout>
  );
}

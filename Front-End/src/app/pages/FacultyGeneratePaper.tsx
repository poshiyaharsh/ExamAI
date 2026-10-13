import axios from "axios";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { DashboardLayout } from "../components/DashboardLayout";
import { LayoutDashboard, FileText, History, Settings, Upload, Plus, Trash2, Sparkles, Download } from "lucide-react";
import { toast } from "sonner";
import {
  facultyPaperApi,
  type AiModel,
  type GeneratedPaper,
  type PaperQuestionType,
  type SyllabusUploadData,
} from "../../services/api";

const menuItems = [
  { icon: LayoutDashboard, label: "Dashboard", path: "/faculty" },
  { icon: FileText, label: "Generate Paper", path: "/faculty/generate" },
  { icon: History, label: "Exam History", path: "/faculty/history" },
  { icon: Settings, label: "Settings", path: "/faculty/settings" }
];

const aiModels: AiModel[] = ["qwen2.5-3b", "llama3.2-3b", "phi3-mini"];
const aiModelLabels: Record<AiModel, string> = {
  "qwen2.5-3b": "Qwen 2.5 3B (Recommended - Local)",
  "llama3.2-3b": "Llama 3.2 3B (Local)",
  "phi3-mini": "Phi-3 Mini (Local)",
};
const draftKey = "faculty-paper-duplicate-draft";

const questionTypeLabels: Record<string, PaperQuestionType> = {
  mcq: "MCQ",
  subjective: "Subjective",
  trueFalse: "True/False",
  fillBlanks: "Fill in the Blanks",
};
const difficultyKeys = ["Easy", "Medium", "Hard"] as const;
type DifficultyKey = typeof difficultyKeys[number];

function extractApiErrorMessage(error: unknown, fallback: string) {
  if (!axios.isAxiosError(error)) return fallback;
  const data = error.response?.data;
  if (data instanceof Blob) return fallback;
  if (data && typeof data === "object" && "message" in data && typeof data.message === "string") {
    if ("failures" in data && Array.isArray(data.failures)) {
      const details = data.failures
        .filter((failure): failure is { provider: string; reason: string } => (
          Boolean(failure) && typeof failure === "object" && "provider" in failure && "reason" in failure
        ))
        .map((failure) => `${failure.provider}: ${failure.reason}`)
        .join(". ");
      return details ? `${data.message} ${details}` : data.message;
    }
    return data.message;
  }
  return fallback;
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function FacultyGeneratePaper() {
  const navigate = useNavigate();
  const [examTitle, setExamTitle] = useState("");
  const [duration, setDuration] = useState("60");
  const [totalMarks, setTotalMarks] = useState("100");
  const [difficultyMix, setDifficultyMix] = useState({ Easy: 30, Medium: 50, Hard: 20 });
  const [topics, setTopics] = useState<string[]>([""]);
  const [questionTypes, setQuestionTypes] = useState({
    mcq: true,
    subjective: true,
    trueFalse: false,
    fillBlanks: false
  });
  const [aiModel, setAiModel] = useState<AiModel>("qwen2.5-3b");
  const [ollamaStatus, setOllamaStatus] = useState<"loading" | "connected" | "not-running" | "model-missing">("loading");
  const [ollamaStatusMessage, setOllamaStatusMessage] = useState("Checking Ollama...");
  const [syllabusFile, setSyllabusFile] = useState<File | null>(null);
  const [uploadedSyllabus, setUploadedSyllabus] = useState<SyllabusUploadData | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [generationProgress, setGenerationProgress] = useState(0);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState("");
  const [previewPaper, setPreviewPaper] = useState<GeneratedPaper | null>(null);
  const [generationSource, setGenerationSource] = useState<{ provider: string; model: string } | null>(null);
  const [avoidRepeats, setAvoidRepeats] = useState(true);
  const [forceRegenerate, setForceRegenerate] = useState(false);
  const activeRequestRef = useRef(false);

  useEffect(() => {
    const rawDraft = localStorage.getItem(draftKey);
    if (!rawDraft) return;
    try {
      const draft = JSON.parse(rawDraft) as Partial<GeneratedPaper>;
      setExamTitle(draft.title || "");
      setDuration(String(draft.duration || 60));
      setTotalMarks(String(draft.total_marks || 100));
      setAiModel(aiModels.includes(draft.model as AiModel) ? draft.model as AiModel : "qwen2.5-3b");
      setTopics(draft.topics?.length ? draft.topics : [""]);
      if (draft.difficulty_distribution) {
        setDifficultyMix({
          Easy: draft.difficulty_distribution.Easy || 0,
          Medium: draft.difficulty_distribution.Medium || 0,
          Hard: draft.difficulty_distribution.Hard || 0,
        });
      }
      const selectedTypes = new Set(draft.question_types || []);
      setQuestionTypes({
        mcq: selectedTypes.has("MCQ"),
        subjective: selectedTypes.has("Subjective"),
        trueFalse: selectedTypes.has("True/False"),
        fillBlanks: selectedTypes.has("Fill in the Blanks"),
      });
    } catch {
      // Ignore malformed duplicate drafts.
    } finally {
      localStorage.removeItem(draftKey);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    const loadOllamaStatus = async () => {
      try {
        const response = await facultyPaperApi.getOllamaStatus();
        if (!cancelled) {
          if (!response.connected) {
            setOllamaStatus("not-running");
          } else if (!response.model_installed) {
            setOllamaStatus("model-missing");
          } else {
            setOllamaStatus("connected");
          }
          setOllamaStatusMessage(response.message);
        }
      } catch {
        if (!cancelled) {
          setOllamaStatus("not-running");
          setOllamaStatusMessage("Ollama: Not Running");
        }
      }
    };
    void loadOllamaStatus();
    return () => {
      cancelled = true;
    };
  }, [aiModel]);

  const selectedQuestionTypes = useMemo(
    () => Object.entries(questionTypes)
      .filter(([, selected]) => selected)
      .map(([key]) => questionTypeLabels[key]),
    [questionTypes]
  );

  const selectedQuestionTypeValues = useMemo(
    () => Object.entries(questionTypes)
      .filter(([, selected]) => selected)
      .map(([key]) => ({ mcq: "mcq", subjective: "subjective", trueFalse: "truefalse", fillBlanks: "fillblank" }[key])),
    [questionTypes]
  );

  const cleanTopics = useMemo(() => topics.map((topic) => topic.trim()).filter(Boolean), [topics]);

  const handleAddTopic = () => {
    setTopics([...topics, ""]);
  };

  const handleRemoveTopic = (index: number) => {
    setTopics(topics.filter((_, i) => i !== index));
  };

  const handleTopicChange = (index: number, value: string) => {
    const newTopics = [...topics];
    newTopics[index] = value;
    setTopics(newTopics);
  };

  const handleDifficultyChange = (level: DifficultyKey, rawValue: string) => {
    const value = Math.max(0, Math.min(100, Number.parseInt(rawValue, 10) || 0));
    const otherLevels = difficultyKeys.filter((difficulty) => difficulty !== level);
    const otherTotal = otherLevels.reduce((sum, difficulty) => sum + difficultyMix[difficulty], 0);
    const remaining = 100 - value;
    const nextMix = { ...difficultyMix, [level]: value };

    if (otherTotal === 0) {
      nextMix[otherLevels[0]] = Math.floor(remaining / 2);
      nextMix[otherLevels[1]] = remaining - nextMix[otherLevels[0]];
    } else {
      nextMix[otherLevels[0]] = Math.round(remaining * difficultyMix[otherLevels[0]] / otherTotal);
      nextMix[otherLevels[1]] = remaining - nextMix[otherLevels[0]];
    }
    setDifficultyMix(nextMix);
  };

  const validateForm = () => {
    if (!examTitle.trim()) return "Exam Title is required.";
    if (Number(duration) <= 0) return "Duration must be greater than 0.";
    if (Number(totalMarks) <= 0) return "Total Marks must be greater than 0.";
    if (cleanTopics.length === 0) return "At least one topic is required.";
    if (selectedQuestionTypes.length === 0) return "At least one question type is required.";
    if (difficultyMix.Easy + difficultyMix.Medium + difficultyMix.Hard !== 100) {
      return "Difficulty percentages must equal exactly 100%.";
    }
    if (syllabusFile) {
      const lowerName = syllabusFile.name.toLowerCase();
      if (!lowerName.endsWith(".pdf") && !lowerName.endsWith(".docx")) {
        return "Only PDF and DOCX syllabus files are supported.";
      }
    }
    return "";
  };

  const handleFileChange = (file: File | null) => {
    setError("");
    setUploadedSyllabus(null);
    setUploadProgress(0);
    if (!file) {
      setSyllabusFile(null);
      return;
    }
    const lowerName = file.name.toLowerCase();
    if (!lowerName.endsWith(".pdf") && !lowerName.endsWith(".docx")) {
      setError("Only PDF and DOCX syllabus files are supported.");
      setSyllabusFile(null);
      return;
    }
    setSyllabusFile(file);
  };

  const handleGenerate = async () => {
    console.log("[GeneratePaper] Button clicked");
    if (activeRequestRef.current) return;
    console.log("[GeneratePaper] Validation started");
    const validationMessage = validateForm();
    if (validationMessage) {
      console.log("[GeneratePaper] Validation failed:", validationMessage);
      setError(validationMessage);
      toast.error(validationMessage);
      return;
    }
    console.log("[GeneratePaper] Validation passed");

    setIsGenerating(true);
    activeRequestRef.current = true;
    setError("");
    setGenerationProgress(15);

    try {
      setGenerationProgress(45);
      const response = await facultyPaperApi.generateExam({
        title: examTitle.trim(),
        durationMinutes: Number(duration),
        totalMarks: Number(totalMarks),
        topics: cleanTopics,
        questionTypes: selectedQuestionTypeValues,
        difficultyDistribution: {
          easy: difficultyMix.Easy,
          medium: difficultyMix.Medium,
          hard: difficultyMix.Hard,
        },
        aiModel,
        syllabus: syllabusFile,
        avoidRepeats,
        forceRegenerate,
      });

      setGenerationProgress(100);

      if (response.status === "draft") {
        if (response.loaded_from_cache) {
          toast.success("Loaded paper instantly from cache (<200 ms)!");
        } else {
          toast.success(`Generated paper with ${response.question_count || "all"} unique questions!`);
        }
        navigate(`/faculty/exams/${response.exam_id}/edit`);
      } else {
        toast.info("Paper generation started in background...");
        navigate(`/faculty/exams/${response.exam_id}/generating`);
      }
    } catch (requestError: any) {
      const respData = requestError?.response?.data;
      const detailMsg = respData?.detail || respData?.message;
      const message = detailMsg || (requestError instanceof Error && !axios.isAxiosError(requestError)
        ? requestError.message
        : extractApiErrorMessage(requestError, "Unable to generate paper."));
      setError(message);
      toast.error(message);
    } finally {
      activeRequestRef.current = false;
      setIsGenerating(false);
    }
  };

  const handleExport = async (format: "pdf" | "docx") => {
    if (!previewPaper) return;
    try {
      const blob = await facultyPaperApi.exportPaper(previewPaper.id, format);
      downloadBlob(blob, `${previewPaper.title}.${format}`);
    } catch (requestError) {
      toast.error(extractApiErrorMessage(requestError, `Unable to download ${format.toUpperCase()}.`));
    }
  };

  return (
    <DashboardLayout menuItems={menuItems} userRole="Faculty">
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-foreground mb-1">Generate Exam Paper</h1>
          <p className="text-xs sm:text-sm text-muted-foreground">Create AI-powered exam papers with customized parameters</p>
        </div>

        <div className="grid lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <div className="bg-white rounded-xl p-5 sm:p-6 shadow-sm border border-border">
              <h3 className="font-semibold text-foreground mb-4">Basic Details</h3>
              <div className="space-y-3.5">
                <div>
                  <label className="block text-xs font-medium text-foreground mb-1.5">Exam Title</label>
                  <input
                    type="text"
                    value={examTitle}
                    onChange={(e) => setExamTitle(e.target.value)}
                    placeholder="e.g., Data Structures Midterm"
                    className="w-full px-3.5 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                  />
                </div>
                <div className="grid sm:grid-cols-2 gap-3.5">
                  <div>
                    <label className="block text-xs font-medium text-foreground mb-1.5">Duration (minutes)</label>
                    <input
                      type="number"
                      value={duration}
                      onChange={(e) => setDuration(e.target.value)}
                      className="w-full px-3.5 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-foreground mb-1.5">Total Marks</label>
                    <input
                      type="number"
                      value={totalMarks}
                      onChange={(e) => setTotalMarks(e.target.value)}
                      className="w-full px-3.5 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                    />
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-xl p-5 sm:p-6 shadow-sm border border-border">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-foreground">Topics to Cover</h3>
                <button
                  onClick={handleAddTopic}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Add Topic
                </button>
              </div>
              <div className="space-y-2.5">
                {topics.map((topic, index) => (
                  <div key={index} className="flex items-center gap-2">
                    <input
                      type="text"
                      value={topic}
                      onChange={(e) => handleTopicChange(index, e.target.value)}
                      placeholder={`Topic ${index + 1}`}
                      className="flex-1 px-3.5 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
                    />
                    {topics.length > 1 && (
                      <button
                        onClick={() => handleRemoveTopic(index)}
                        className="p-2 text-rose-500 hover:text-rose-700 hover:bg-rose-50 rounded-lg transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-white rounded-xl p-5 sm:p-6 shadow-sm border border-border">
              <h3 className="font-semibold text-foreground mb-4">Question Types</h3>
              <div className="grid sm:grid-cols-2 gap-3.5">
                {Object.entries({
                  mcq: "Multiple Choice",
                  subjective: "Subjective",
                  trueFalse: "True/False",
                  fillBlanks: "Fill in the Blanks"
                }).map(([key, label]) => (
                  <label key={key} className="flex items-center gap-2.5 p-2 rounded-lg hover:bg-muted/30 transition-colors cursor-pointer">
                    <input
                      type="checkbox"
                      checked={questionTypes[key as keyof typeof questionTypes]}
                      onChange={(e) => setQuestionTypes({
                        ...questionTypes,
                        [key]: e.target.checked
                      })}
                      className="w-4 h-4 rounded border-border text-primary focus:ring-2 focus:ring-primary accent-primary"
                    />
                    <span className="text-xs sm:text-sm font-medium text-foreground">{label}</span>
                  </label>
                ))}
              </div>
            </div>

            <div className="bg-white rounded-xl p-5 sm:p-6 shadow-sm border border-border">
              <h3 className="font-semibold text-foreground mb-4">Difficulty Distribution</h3>
              <div className="space-y-4">
                {difficultyKeys.map((level) => {
                  const value = difficultyMix[level];
                  return (
                  <div key={level}>
                    <div className="flex items-center justify-between mb-1.5">
                      <label className="text-xs font-medium text-foreground">{level}</label>
                      <span className="text-xs font-bold text-primary">{value}%</span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="100"
                      value={value}
                      onChange={(e) => handleDifficultyChange(level, e.target.value)}
                      className="w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                    />
                  </div>
                    );
                  })}
                  {(() => {
                    const total = difficultyKeys.reduce((sum, level) => sum + difficultyMix[level], 0);
                    return <p className={`text-sm ${total === 100 ? "text-muted-foreground" : "text-red-600"}`}>Total: {total}%</p>;
                  })()}
              </div>
            </div>

            {previewPaper && (
              <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
                <div className="flex items-center justify-between gap-4 mb-4">
                  <h3 className="font-semibold">Preview</h3>
                  <div className="flex items-center gap-2">
                    <button onClick={() => void handleExport("pdf")} className="px-3 py-1.5 rounded-lg border border-border hover:bg-muted transition-colors flex items-center gap-2 text-sm">
                      <Download className="w-4 h-4" />
                      PDF
                    </button>
                    <button onClick={() => void handleExport("docx")} className="px-3 py-1.5 rounded-lg border border-border hover:bg-muted transition-colors flex items-center gap-2 text-sm">
                      <Download className="w-4 h-4" />
                      DOCX
                    </button>
                  </div>
                </div>
                <div className="space-y-4 text-sm">
                  <div className="text-center border-b border-border pb-4">
                    <p className="font-semibold text-lg">{previewPaper.institution.institution_name}</p>
                    <p className="font-semibold">{previewPaper.title}</p>
                    <p className="text-muted-foreground">Duration: {previewPaper.duration} minutes | Total Marks: {previewPaper.total_marks}</p>
                    {generationSource && <p className="text-xs text-muted-foreground mt-1">Generated by {generationSource.provider} ({generationSource.model})</p>}
                  </div>
                  <div>
                    <p className="font-medium">Instructions</p>
                    <p className="text-muted-foreground">Answer all questions. Marks are shown beside each question.</p>
                  </div>
                  {["MCQ", "Subjective", "True/False", "Fill in the Blanks"].map((type, sectionIndex) => {
                    const questions = previewPaper.questions.filter((question) => question.type === type);
                    if (!questions.length) return null;
                    return (
                      <div key={type}>
                        <p className="font-semibold mb-2">Section {String.fromCharCode(65 + sectionIndex)}</p>
                        <div className="space-y-3">
                          {questions.map((question) => (
                            <div key={question.question_number}>
                              <p>{question.question_number}. {question.question} <span className="text-muted-foreground">[{question.marks} marks]</span></p>
                              {question.options.length > 0 && (
                                <ul className="mt-1 ml-5 list-disc text-muted-foreground">
                                  {question.options.map((option) => <li key={option}>{option}</li>)}
                                </ul>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          <div className="space-y-6">
            <div className="bg-white rounded-xl p-5 sm:p-6 shadow-sm border border-border">
              <h3 className="font-semibold text-foreground mb-4">Upload Syllabus</h3>
              <label className="block border-2 border-dashed border-border rounded-xl p-6 text-center hover:border-primary/60 hover:bg-primary/5 transition-all cursor-pointer">
                <Upload className="w-9 h-9 text-muted-foreground/60 mx-auto mb-2" />
                <p className="text-sm font-medium text-foreground mb-1">Click to upload</p>
                <p className="text-xs text-muted-foreground">PDF, DOCX (Max 10MB)</p>
                <input
                  type="file"
                  accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  className="hidden"
                  onChange={(e) => handleFileChange(e.target.files?.[0] || null)}
                />
              </label>
              <div className="mt-4 space-y-2">
                <div className="flex items-center justify-between text-xs sm:text-sm p-2 rounded-lg bg-muted/40">
                  <span className="text-muted-foreground">Uploaded:</span>
                  <span className="font-medium text-foreground truncate max-w-[200px]">{uploadedSyllabus?.original_filename || syllabusFile?.name || "-"}</span>
                </div>
                {(uploadProgress > 0 || isGenerating) && (
                  <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                    <div className="h-full bg-primary transition-all" style={{ width: `${uploadProgress}%` }} />
                  </div>
                )}
              </div>
            </div>

            <div className="bg-white rounded-xl p-5 sm:p-6 shadow-sm border border-border">
              <h3 className="font-semibold text-foreground mb-3">AI Model</h3>
              <select
                value={aiModel}
                onChange={(e) => setAiModel(e.target.value as AiModel)}
                className="w-full px-3.5 py-2 rounded-lg bg-input-background border border-border text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
              >
                {aiModels.map((model) => (
                  <option key={model} value={model}>{aiModelLabels[model]}</option>
                ))}
              </select>
              <p className={`mt-2 text-xs font-medium ${ollamaStatus === "connected" ? "text-emerald-600" : ollamaStatus === "model-missing" ? "text-amber-600" : "text-rose-600"}`}>
                {ollamaStatusMessage}
              </p>
            </div>

            {isGenerating && (
              <div className="bg-white rounded-xl p-5 sm:p-6 shadow-sm border border-border">
                <div className="flex items-center justify-between text-xs sm:text-sm mb-2">
                  <span className="text-muted-foreground">Generation Progress</span>
                  <span className="font-semibold text-primary">{generationProgress}%</span>
                </div>
                <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-primary to-secondary transition-all" style={{ width: `${generationProgress}%` }} />
                </div>
              </div>
            )}

            <div className="bg-white rounded-xl p-5 sm:p-6 shadow-sm border border-border space-y-3">
              <h3 className="font-semibold text-foreground text-sm">Quality & Deduplication Settings</h3>
              <label className="flex items-center gap-2.5 text-xs sm:text-sm text-foreground cursor-pointer">
                <input
                  type="checkbox"
                  checked={avoidRepeats}
                  onChange={(e) => setAvoidRepeats(e.target.checked)}
                  className="rounded border-border text-primary focus:ring-primary w-4 h-4"
                />
                <span>Avoid repeating questions from my recent papers (last 3 papers / 30 days)</span>
              </label>
              <label className="flex items-center gap-2.5 text-xs sm:text-sm text-foreground cursor-pointer">
                <input
                  type="checkbox"
                  checked={forceRegenerate}
                  onChange={(e) => setForceRegenerate(e.target.checked)}
                  className="rounded border-border text-primary focus:ring-primary w-4 h-4"
                />
                <span>Bypass cache (force fresh in-memory generation)</span>
              </label>
              <div className="pt-2 border-t border-border flex justify-between items-center text-xs">
                <span className="text-muted-foreground">Cached papers load in &lt; 200 ms</span>
                <button
                  type="button"
                  onClick={async () => {
                    try {
                      await facultyExamApi.clearPaperCache();
                      toast.success("Cached papers cleared!");
                    } catch {
                      toast.error("Failed to clear cache");
                    }
                  }}
                  className="text-xs text-muted-foreground hover:text-foreground underline"
                >
                  Clear My Paper Cache
                </button>
              </div>
            </div>

            {error && <p className="text-xs sm:text-sm text-destructive font-medium">{error}</p>}

            <button
              onClick={() => void handleGenerate()}
              disabled={isGenerating}
              className="w-full px-5 py-2.5 rounded-lg bg-gradient-to-r from-primary to-secondary text-white font-medium text-sm hover:opacity-90 shadow-md transition-all flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              <Sparkles className="w-4 h-4" />
              {isGenerating ? "Generating paper..." : "Generate Paper"}
            </button>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

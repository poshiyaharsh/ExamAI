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

const aiModels: AiModel[] = ["ollama-qwen2.5-3b", "ollama-llama3.2-3b", "ollama-phi3-mini"];
const aiModelLabels: Record<AiModel, string> = {
  "ollama-qwen2.5-3b": "Qwen 2.5 3B (Recommended - Local)",
  "ollama-llama3.2-3b": "Llama 3.2 3B (Local)",
  "ollama-phi3-mini": "Phi-3 Mini (Local)",
};
const draftKey = "faculty-paper-duplicate-draft";

const questionTypeLabels: Record<string, PaperQuestionType> = {
  mcq: "MCQ",
  subjective: "Subjective",
  trueFalse: "True/False",
  fillBlanks: "Fill in the Blanks",
};

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
  const [aiModel, setAiModel] = useState<AiModel>("ollama-qwen2.5-3b");
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
  const activeRequestRef = useRef(false);

  useEffect(() => {
    const rawDraft = localStorage.getItem(draftKey);
    if (!rawDraft) return;
    try {
      const draft = JSON.parse(rawDraft) as Partial<GeneratedPaper>;
      setExamTitle(draft.title || "");
      setDuration(String(draft.duration || 60));
      setTotalMarks(String(draft.total_marks || 100));
      setAiModel(aiModels.includes(draft.model as AiModel) ? draft.model as AiModel : "ollama-qwen2.5-3b");
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

  const validateForm = () => {
    if (!examTitle.trim()) return "Exam Title is required.";
    if (Number(duration) <= 0) return "Duration must be greater than 0.";
    if (Number(totalMarks) <= 0) return "Total Marks must be greater than 0.";
    if (cleanTopics.length === 0) return "At least one topic is required.";
    if (selectedQuestionTypes.length === 0) return "At least one question type is required.";
    if (difficultyMix.Easy + difficultyMix.Medium + difficultyMix.Hard !== 100) {
      return "Difficulty percentages must equal exactly 100%.";
    }
    if (!syllabusFile) return "Please upload a syllabus file.";
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
    setGenerationProgress(5);

    try {
      if (!syllabusFile) {
        throw new Error("Please upload a syllabus file.");
      }
      setGenerationProgress(25);
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
      });
      setGenerationProgress(100);
      if (response.warning) {
        toast.warning(`${response.warning} Computed total: ${response.actual_total_marks} marks.`);
      } else {
        toast.success(`Exam paper generated: ${response.actual_total_marks} marks.`);
      }
      navigate(`/faculty/exams/${response.exam_id}/edit`);
    } catch (requestError) {
      const message = requestError instanceof Error && !axios.isAxiosError(requestError)
        ? requestError.message
        : extractApiErrorMessage(requestError, "Unable to generate paper.");
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
          <h1 className="text-3xl font-bold text-foreground mb-2">Generate Exam Paper</h1>
          <p className="text-muted-foreground">Create AI-powered exam papers with customized parameters</p>
        </div>

        <div className="grid lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
              <h3 className="font-semibold mb-4">Basic Details</h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-2">Exam Title</label>
                  <input
                    type="text"
                    value={examTitle}
                    onChange={(e) => setExamTitle(e.target.value)}
                    placeholder="e.g., Data Structures Midterm"
                    className="w-full px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                  />
                </div>
                <div className="grid sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">Duration (minutes)</label>
                    <input
                      type="number"
                      value={duration}
                      onChange={(e) => setDuration(e.target.value)}
                      className="w-full px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-2">Total Marks</label>
                    <input
                      type="number"
                      value={totalMarks}
                      onChange={(e) => setTotalMarks(e.target.value)}
                      className="w-full px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                    />
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold">Topics to Cover</h3>
                <button
                  onClick={handleAddTopic}
                  className="flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
                >
                  <Plus className="w-4 h-4" />
                  Add Topic
                </button>
              </div>
              <div className="space-y-3">
                {topics.map((topic, index) => (
                  <div key={index} className="flex items-center gap-2">
                    <input
                      type="text"
                      value={topic}
                      onChange={(e) => handleTopicChange(index, e.target.value)}
                      placeholder={`Topic ${index + 1}`}
                      className="flex-1 px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                    />
                    {topics.length > 1 && (
                      <button
                        onClick={() => handleRemoveTopic(index)}
                        className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                      >
                        <Trash2 className="w-5 h-5" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
              <h3 className="font-semibold mb-4">Question Types</h3>
              <div className="grid sm:grid-cols-2 gap-4">
                {Object.entries({
                  mcq: "Multiple Choice",
                  subjective: "Subjective",
                  trueFalse: "True/False",
                  fillBlanks: "Fill in the Blanks"
                }).map(([key, label]) => (
                  <label key={key} className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={questionTypes[key as keyof typeof questionTypes]}
                      onChange={(e) => setQuestionTypes({
                        ...questionTypes,
                        [key]: e.target.checked
                      })}
                      className="w-5 h-5 rounded border-border text-primary focus:ring-2 focus:ring-primary/20"
                    />
                    <span className="text-sm font-medium">{label}</span>
                  </label>
                ))}
              </div>
            </div>

            <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
              <h3 className="font-semibold mb-4">Difficulty Distribution</h3>
              <div className="space-y-4">
                {Object.entries(difficultyMix).map(([level, value]) => (
                  <div key={level}>
                    <div className="flex items-center justify-between mb-2">
                      <label className="text-sm font-medium">{level}</label>
                      <span className="text-sm text-muted-foreground">{value}%</span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="100"
                      value={value}
                      onChange={(e) => setDifficultyMix({
                        ...difficultyMix,
                        [level]: parseInt(e.target.value)
                      })}
                      className="w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary"
                    />
                  </div>
                ))}
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
            <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
              <h3 className="font-semibold mb-4">Upload Syllabus</h3>
              <label className="block border-2 border-dashed border-border rounded-lg p-6 text-center hover:border-primary transition-colors cursor-pointer">
                <Upload className="w-10 h-10 text-muted-foreground mx-auto mb-2" />
                <p className="text-sm text-muted-foreground mb-1">Click to upload</p>
                <p className="text-xs text-muted-foreground">PDF, DOCX (Max 10MB)</p>
                <input
                  type="file"
                  accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  className="hidden"
                  onChange={(e) => handleFileChange(e.target.files?.[0] || null)}
                />
              </label>
              <div className="mt-4 space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Uploaded:</span>
                  <span className="font-medium">{uploadedSyllabus?.original_filename || syllabusFile?.name || "-"}</span>
                </div>
                {(uploadProgress > 0 || isGenerating) && (
                  <div className="h-2 rounded-full bg-muted overflow-hidden">
                    <div className="h-full bg-primary transition-all" style={{ width: `${uploadProgress}%` }} />
                  </div>
                )}
              </div>
            </div>

            <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
              <h3 className="font-semibold mb-4">AI Model</h3>
              <select
                value={aiModel}
                onChange={(e) => setAiModel(e.target.value as AiModel)}
                className="w-full px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
              >
                {aiModels.map((model) => (
                  <option key={model} value={model}>{aiModelLabels[model]}</option>
                ))}
              </select>
              <p className={`mt-2 text-xs ${ollamaStatus === "connected" ? "text-emerald-600" : ollamaStatus === "model-missing" ? "text-amber-600" : "text-red-600"}`}>
                {ollamaStatusMessage}
              </p>
            </div>

            {isGenerating && (
              <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
                <div className="flex items-center justify-between text-sm mb-2">
                  <span className="text-muted-foreground">Generation Progress</span>
                  <span className="font-medium">{generationProgress}%</span>
                </div>
                <div className="h-2 rounded-full bg-muted overflow-hidden">
                  <div className="h-full bg-primary transition-all" style={{ width: `${generationProgress}%` }} />
                </div>
              </div>
            )}

            {error && <p className="text-sm text-destructive">{error}</p>}

            <button
              onClick={() => void handleGenerate()}
              disabled={isGenerating}
              className="w-full px-6 py-3 rounded-lg bg-gradient-to-r from-primary to-secondary text-white font-semibold shadow-lg hover:shadow-xl transition-all flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              <Sparkles className="w-5 h-5" />
              {isGenerating ? `Generating with ${aiModel}… this can take up to a minute.` : "Generate Paper"}
            </button>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

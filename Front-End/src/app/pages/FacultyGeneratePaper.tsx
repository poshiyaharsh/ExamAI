import { useState } from "react";
import { DashboardLayout } from "../components/DashboardLayout";
import { LayoutDashboard, FileText, History, Settings, Upload, Plus, Trash2, Sparkles } from "lucide-react";

const menuItems = [
  { icon: LayoutDashboard, label: "Dashboard", path: "/faculty" },
  { icon: FileText, label: "Generate Paper", path: "/faculty/generate" },
  { icon: History, label: "Exam History", path: "/faculty/history" },
  { icon: Settings, label: "Settings", path: "/faculty/settings" }
];

export function FacultyGeneratePaper() {
  const [examTitle, setExamTitle] = useState("");
  const [duration, setDuration] = useState("60");
  const [totalMarks, setTotalMarks] = useState("100");
  const [difficultyMix, setDifficultyMix] = useState({ easy: 30, medium: 50, hard: 20 });
  const [topics, setTopics] = useState<string[]>([""]);
  const [questionTypes, setQuestionTypes] = useState({
    mcq: true,
    subjective: true,
    trueFalse: false,
    fillBlanks: false
  });

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

  const handleGenerate = () => {
    console.log("Generating paper with:", {
      examTitle,
      duration,
      totalMarks,
      difficultyMix,
      topics,
      questionTypes
    });
  };

  return (
    <DashboardLayout menuItems={menuItems} userRole="Faculty">
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-foreground mb-2">Generate Exam Paper</h1>
          <p className="text-muted-foreground">Create AI-powered exam papers with customized parameters</p>
        </div>

        <div className="grid lg:grid-cols-3 gap-6">
          {/* Main Form */}
          <div className="lg:col-span-2 space-y-6">
            {/* Basic Details */}
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

            {/* Topics */}
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

            {/* Question Types */}
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

            {/* Difficulty Mix */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
              <h3 className="font-semibold mb-4">Difficulty Distribution</h3>
              <div className="space-y-4">
                {Object.entries(difficultyMix).map(([level, value]) => (
                  <div key={level}>
                    <div className="flex items-center justify-between mb-2">
                      <label className="text-sm font-medium capitalize">{level}</label>
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
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Upload Syllabus */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
              <h3 className="font-semibold mb-4">Upload Syllabus</h3>
              <div className="border-2 border-dashed border-border rounded-lg p-6 text-center hover:border-primary transition-colors cursor-pointer">
                <Upload className="w-10 h-10 text-muted-foreground mx-auto mb-2" />
                <p className="text-sm text-muted-foreground mb-1">Click to upload</p>
                <p className="text-xs text-muted-foreground">PDF, DOC (Max 10MB)</p>
              </div>
              <div className="mt-4 space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Uploaded:</span>
                  <span className="font-medium">syllabus.pdf</span>
                </div>
              </div>
            </div>

            {/* AI Model */}
            <div className="bg-white rounded-xl p-6 shadow-sm border border-border">
              <h3 className="font-semibold mb-4">AI Model</h3>
              <select className="w-full px-4 py-2.5 rounded-lg border border-border focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all">
                <option>GPT-4 (Recommended)</option>
                <option>GPT-3.5</option>
                <option>Claude 3</option>
                <option>Gemini Pro</option>
              </select>
            </div>

            {/* Generate Button */}
            <button
              onClick={handleGenerate}
              className="w-full px-6 py-3 rounded-lg bg-gradient-to-r from-primary to-secondary text-white font-semibold shadow-lg hover:shadow-xl transition-all flex items-center justify-center gap-2"
            >
              <Sparkles className="w-5 h-5" />
              Generate Paper
            </button>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

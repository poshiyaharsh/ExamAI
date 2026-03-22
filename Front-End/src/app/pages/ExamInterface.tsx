import { useState, useEffect, useCallback } from "react";
import { useNavigate, useParams } from "react-router";
import { Clock, CheckCircle, Circle, Save } from "lucide-react";

const sampleQuestions = [
  {
    id: 1,
    type: "mcq",
    question: "What is the time complexity of binary search?",
    options: ["O(n)", "O(log n)", "O(n²)", "O(1)"],
    marks: 2
  },
  {
    id: 2,
    type: "mcq",
    question: "Which data structure uses LIFO principle?",
    options: ["Queue", "Stack", "Tree", "Graph"],
    marks: 2
  },
  {
    id: 3,
    type: "subjective",
    question: "Explain the concept of polymorphism in object-oriented programming with an example.",
    marks: 10
  },
  {
    id: 4,
    type: "mcq",
    question: "What does SQL stand for?",
    options: ["Structured Query Language", "Simple Query Language", "Standard Query Language", "System Query Language"],
    marks: 2
  },
  {
    id: 5,
    type: "subjective",
    question: "Write a function to implement bubble sort and analyze its time complexity.",
    marks: 10
  }
];

export function ExamInterface() {
  const navigate = useNavigate();
  const { id } = useParams();
  const [currentQuestion, setCurrentQuestion] = useState(0);
  const [answers, setAnswers] = useState<{ [key: number]: any }>({});
  const [timeLeft, setTimeLeft] = useState(3600); // 60 minutes in seconds
  const [autoSaved, setAutoSaved] = useState(false);

  const handleSubmit = useCallback(() => {
    navigate(`/result/${id}`);
  }, [navigate, id]);

  useEffect(() => {
    const timer = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          handleSubmit();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [handleSubmit]);

  useEffect(() => {
    // Auto-save every 30 seconds
    const autoSaveTimer = setInterval(() => {
      setAutoSaved(true);
      setTimeout(() => setAutoSaved(false), 2000);
    }, 30000);

    return () => clearInterval(autoSaveTimer);
  }, []);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  const handleAnswerChange = (questionId: number, answer: any) => {
    setAnswers({ ...answers, [questionId]: answer });
  };

  const question = sampleQuestions[currentQuestion];
  const isAnswered = answers[question.id] !== undefined;

  return (
    <div className="min-h-screen bg-muted/30">
      {/* Timer Top Bar */}
      <div className="sticky top-0 z-50 bg-white border-b border-border shadow-sm">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-foreground">Data Structures Midterm</h3>
            <p className="text-sm text-muted-foreground">Computer Science - Midterm Examination</p>
          </div>
          <div className="flex items-center gap-6">
            {/* Auto Save Indicator */}
            <div className="flex items-center gap-2">
              {autoSaved ? (
                <>
                  <CheckCircle className="w-4 h-4 text-green-600" />
                  <span className="text-sm text-green-600">Saved</span>
                </>
              ) : (
                <>
                  <Save className="w-4 h-4 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">Auto-saving...</span>
                </>
              )}
            </div>
            {/* Timer */}
            <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-accent">
              <Clock className="w-5 h-5 text-accent-foreground" />
              <span className="font-semibold text-accent-foreground">{formatTime(timeLeft)}</span>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto p-6">
        <div className="grid lg:grid-cols-4 gap-6">
          {/* Main Question Area */}
          <div className="lg:col-span-3">
            <div className="bg-white rounded-xl shadow-sm border border-border p-8">
              <div className="mb-6">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-xl font-semibold text-foreground">
                    Question {currentQuestion + 1} of {sampleQuestions.length}
                  </h2>
                  <span className="px-3 py-1 rounded-full bg-accent text-accent-foreground text-sm">
                    {question.marks} marks
                  </span>
                </div>
                <p className="text-lg text-foreground leading-relaxed">{question.question}</p>
              </div>

              {question.type === "mcq" ? (
                <div className="space-y-3">
                  {question.options?.map((option, index) => (
                    <label
                      key={index}
                      className={`flex items-start gap-4 p-4 rounded-lg border-2 cursor-pointer transition-all ${
                        answers[question.id] === option
                          ? "border-primary bg-accent"
                          : "border-border hover:border-primary/50"
                      }`}
                    >
                      <input
                        type="radio"
                        name={`question-${question.id}`}
                        value={option}
                        checked={answers[question.id] === option}
                        onChange={(e) => handleAnswerChange(question.id, e.target.value)}
                        className="mt-1 w-5 h-5 text-primary"
                      />
                      <span className="flex-1 text-foreground">{option}</span>
                    </label>
                  ))}
                </div>
              ) : (
                <div>
                  <textarea
                    rows={12}
                    placeholder="Type your answer here..."
                    value={answers[question.id] || ""}
                    onChange={(e) => handleAnswerChange(question.id, e.target.value)}
                    className="w-full px-4 py-3 rounded-lg bg-input-background border border-border focus:outline-none focus:ring-2 focus:ring-primary resize-none"
                  />
                  <p className="text-sm text-muted-foreground mt-2">
                    {answers[question.id]?.length || 0} characters
                  </p>
                </div>
              )}

              {/* Navigation Buttons */}
              <div className="flex items-center justify-between mt-8 pt-6 border-t border-border">
                <button
                  onClick={() => setCurrentQuestion(Math.max(0, currentQuestion - 1))}
                  disabled={currentQuestion === 0}
                  className="px-6 py-2 rounded-lg border border-border text-foreground hover:bg-accent transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Previous
                </button>
                <div className="flex gap-3">
                  <button className="px-6 py-2 rounded-lg border border-border text-foreground hover:bg-accent transition-colors">
                    Save & Mark for Review
                  </button>
                  {currentQuestion < sampleQuestions.length - 1 ? (
                    <button
                      onClick={() => setCurrentQuestion(currentQuestion + 1)}
                      className="px-6 py-2 rounded-lg bg-gradient-to-r from-primary to-secondary text-white hover:opacity-90 transition-opacity"
                    >
                      Next
                    </button>
                  ) : (
                    <button
                      onClick={handleSubmit}
                      className="px-6 py-2 rounded-lg bg-gradient-to-r from-green-600 to-green-700 text-white hover:opacity-90 transition-opacity"
                    >
                      Submit Exam
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Question Navigation Panel */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-xl shadow-sm border border-border p-6 sticky top-24">
              <h3 className="font-semibold mb-4">Question Navigator</h3>
              <div className="grid grid-cols-5 gap-2 mb-6">
                {sampleQuestions.map((q, index) => (
                  <button
                    key={q.id}
                    onClick={() => setCurrentQuestion(index)}
                    className={`aspect-square rounded-lg flex items-center justify-center text-sm transition-all ${
                      currentQuestion === index
                        ? "bg-gradient-to-r from-primary to-secondary text-white"
                        : answers[q.id] !== undefined
                        ? "bg-green-100 text-green-700 border border-green-300"
                        : "bg-muted text-muted-foreground hover:bg-accent"
                    }`}
                  >
                    {index + 1}
                  </button>
                ))}
              </div>

              <div className="space-y-2 text-sm">
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded bg-green-100 border border-green-300"></div>
                  <span className="text-muted-foreground">
                    Answered ({Object.keys(answers).length})
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded bg-muted"></div>
                  <span className="text-muted-foreground">
                    Not Answered ({sampleQuestions.length - Object.keys(answers).length})
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded bg-gradient-to-r from-primary to-secondary"></div>
                  <span className="text-muted-foreground">Current</span>
                </div>
              </div>

              <button
                onClick={handleSubmit}
                className="w-full mt-6 px-6 py-3 rounded-lg bg-gradient-to-r from-green-600 to-green-700 text-white hover:opacity-90 transition-opacity"
              >
                Submit Exam
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

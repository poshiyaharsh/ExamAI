import { Link, useParams } from "react-router-dom";
import { motion } from "motion/react";
import { Download, TrendingUp, TrendingDown, Award, Brain, CheckCircle, XCircle } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar } from "recharts";

const topicWiseData = [
  { topic: "Arrays", score: 90, maxScore: 100 },
  { topic: "Linked Lists", score: 75, maxScore: 100 },
  { topic: "Trees", score: 85, maxScore: 100 },
  { topic: "Graphs", score: 70, maxScore: 100 },
  { topic: "Sorting", score: 95, maxScore: 100 }
];

const skillsRadarData = [
  { skill: "Problem Solving", value: 85 },
  { skill: "Conceptual", value: 78 },
  { skill: "Application", value: 90 },
  { skill: "Analysis", value: 75 },
  { skill: "Synthesis", value: 82 }
];

const questionBreakdown = [
  { question: "Question 1", yourAnswer: "O(log n)", correctAnswer: "O(log n)", marks: 2, obtained: 2, correct: true },
  { question: "Question 2", yourAnswer: "Stack", correctAnswer: "Stack", marks: 2, obtained: 2, correct: true },
  { question: "Question 3", yourAnswer: "Subjective Answer", correctAnswer: "N/A", marks: 10, obtained: 8, correct: true },
  { question: "Question 4", yourAnswer: "Structured Query Language", correctAnswer: "Structured Query Language", marks: 2, obtained: 2, correct: true },
  { question: "Question 5", yourAnswer: "Subjective Answer", correctAnswer: "N/A", marks: 10, obtained: 7, correct: true }
];

export function ResultPage() {
  const { id } = useParams();
  const totalScore = 21;
  const maxScore = 26;
  const percentage = Math.round((totalScore / maxScore) * 100);

  return (
    <div className="min-h-screen bg-muted/30">
      {/* Header */}
      <div className="bg-gradient-to-r from-primary to-secondary text-white py-12">
        <div className="max-w-7xl mx-auto px-6">
          <Link to="/student" className="text-white/80 hover:text-white mb-4 inline-block">
            ← Back to Dashboard
          </Link>
          <h1 className="text-4xl font-bold mb-2">Exam Results</h1>
          <p className="text-white/90">Data Structures Midterm Examination</p>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8 space-y-6">
        {/* Score Card */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white rounded-xl shadow-lg border border-border overflow-hidden"
        >
          <div className="bg-gradient-to-r from-primary to-secondary p-8 text-white">
            <div className="grid md:grid-cols-3 gap-6 items-center">
              <div className="text-center">
                <div className="text-6xl font-bold mb-2">{percentage}%</div>
                <div className="text-white/90">Overall Score</div>
              </div>
              <div className="text-center border-x border-white/20 py-4">
                <div className="text-4xl font-bold mb-2">{totalScore}/{maxScore}</div>
                <div className="text-white/90">Marks Obtained</div>
              </div>
              <div className="text-center">
                <div className="flex items-center justify-center gap-2 mb-2">
                  <Award className="w-12 h-12" />
                  <span className="text-4xl font-bold">A</span>
                </div>
                <div className="text-white/90">Grade</div>
              </div>
            </div>
          </div>
          <div className="p-6 bg-muted/30">
            <div className="grid md:grid-cols-4 gap-4 text-center">
              <div>
                <div className="text-2xl font-bold text-foreground mb-1">25</div>
                <div className="text-sm text-muted-foreground">Total Questions</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-green-600 mb-1">22</div>
                <div className="text-sm text-muted-foreground">Correct Answers</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-red-600 mb-1">3</div>
                <div className="text-sm text-muted-foreground">Incorrect Answers</div>
              </div>
              <div>
                <div className="text-2xl font-bold text-foreground mb-1">60 min</div>
                <div className="text-sm text-muted-foreground">Time Taken</div>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Topic Wise Analysis */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="bg-white rounded-xl shadow-sm border border-border p-6"
        >
          <h3 className="font-semibold text-xl mb-6">Topic Wise Analysis</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={topicWiseData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
              <XAxis dataKey="topic" stroke="#6B7280" />
              <YAxis stroke="#6B7280" />
              <Tooltip />
              <Bar dataKey="score" fill="#4F46E5" radius={[8, 8, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </motion.div>

        <div className="grid lg:grid-cols-2 gap-6">
          {/* AI Feedback Section */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="bg-white rounded-xl shadow-sm border border-border p-6"
          >
            <div className="flex items-center gap-3 mb-4">
              <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
                <Brain className="w-6 h-6 text-white" />
              </div>
              <h3 className="font-semibold text-xl">AI Feedback</h3>
            </div>
            <div className="space-y-4">
              <div className="bg-accent/50 rounded-lg p-4">
                <h4 className="font-semibold text-foreground mb-2">Overall Performance</h4>
                <p className="text-sm text-muted-foreground">
                  You have demonstrated a strong understanding of fundamental data structures concepts. 
                  Your performance in arrays and sorting algorithms is exceptional.
                </p>
              </div>
              <div className="bg-blue-50 rounded-lg p-4">
                <h4 className="font-semibold text-foreground mb-2">Areas of Improvement</h4>
                <ul className="text-sm text-muted-foreground space-y-1 list-disc list-inside">
                  <li>Focus more on graph traversal algorithms</li>
                  <li>Practice more problems on linked list manipulation</li>
                  <li>Review time complexity analysis for tree operations</li>
                </ul>
              </div>
              <div className="bg-green-50 rounded-lg p-4">
                <h4 className="font-semibold text-foreground mb-2">Recommended Topics</h4>
                <ul className="text-sm text-muted-foreground space-y-1 list-disc list-inside">
                  <li>Advanced graph algorithms (Dijkstra, Bellman-Ford)</li>
                  <li>Balanced search trees (AVL, Red-Black)</li>
                  <li>Dynamic programming optimization techniques</li>
                </ul>
              </div>
            </div>
          </motion.div>

          {/* Strength & Weakness Report */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="bg-white rounded-xl shadow-sm border border-border p-6"
          >
            <h3 className="font-semibold text-xl mb-6">Skills Assessment</h3>
            <ResponsiveContainer width="100%" height={300}>
              <RadarChart data={skillsRadarData}>
                <PolarGrid stroke="#E5E7EB" />
                <PolarAngleAxis dataKey="skill" stroke="#6B7280" />
                <PolarRadiusAxis stroke="#6B7280" />
                <Radar name="Your Score" dataKey="value" stroke="#4F46E5" fill="#4F46E5" fillOpacity={0.3} />
              </RadarChart>
            </ResponsiveContainer>
            <div className="mt-6 grid grid-cols-2 gap-4">
              <div className="bg-green-50 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-2">
                  <TrendingUp className="w-5 h-5 text-green-600" />
                  <h4 className="font-semibold text-green-900">Strengths</h4>
                </div>
                <ul className="text-sm text-green-700 space-y-1">
                  <li>• Application Skills</li>
                  <li>• Problem Solving</li>
                  <li>• Synthesis</li>
                </ul>
              </div>
              <div className="bg-red-50 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-2">
                  <TrendingDown className="w-5 h-5 text-red-600" />
                  <h4 className="font-semibold text-red-900">Needs Work</h4>
                </div>
                <ul className="text-sm text-red-700 space-y-1">
                  <li>• Analysis Skills</li>
                  <li>• Conceptual Understanding</li>
                </ul>
              </div>
            </div>
          </motion.div>
        </div>

        {/* Detailed Question Breakdown */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="bg-white rounded-xl shadow-sm border border-border"
        >
          <div className="p-6 border-b border-border">
            <h3 className="font-semibold text-xl">Detailed Question Breakdown</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-muted/50">
                <tr>
                  <th className="text-left px-6 py-3 text-sm text-muted-foreground">Question</th>
                  <th className="text-left px-6 py-3 text-sm text-muted-foreground">Your Answer</th>
                  <th className="text-left px-6 py-3 text-sm text-muted-foreground">Status</th>
                  <th className="text-left px-6 py-3 text-sm text-muted-foreground">Marks</th>
                </tr>
              </thead>
              <tbody>
                {questionBreakdown.map((item, index) => (
                  <tr key={index} className="border-t border-border hover:bg-muted/30 transition-colors">
                    <td className="px-6 py-4">{item.question}</td>
                    <td className="px-6 py-4 text-sm">{item.yourAnswer}</td>
                    <td className="px-6 py-4">
                      {item.correct ? (
                        <div className="flex items-center gap-2 text-green-600">
                          <CheckCircle className="w-4 h-4" />
                          <span className="text-sm">Correct</span>
                        </div>
                      ) : (
                        <div className="flex items-center gap-2 text-red-600">
                          <XCircle className="w-4 h-4" />
                          <span className="text-sm">Incorrect</span>
                        </div>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <span className="font-semibold">{item.obtained}/{item.marks}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </motion.div>

        {/* Download Result PDF */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
          className="flex justify-center"
        >
          <button className="px-8 py-4 rounded-lg bg-gradient-to-r from-primary to-secondary text-white hover:opacity-90 transition-opacity flex items-center gap-3">
            <Download className="w-5 h-5" />
            Download Result PDF
          </button>
        </motion.div>
      </div>
    </div>
  );
}

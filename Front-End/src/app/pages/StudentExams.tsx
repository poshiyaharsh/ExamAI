import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { DashboardLayout } from "../components/DashboardLayout";
import { Calendar, CheckCircle, Clock, FileText, Filter, LayoutDashboard, Search, Settings, TrendingUp } from "lucide-react";
import { studentExamApi, type StudentExamSummary } from "../../services/api";

const menuItems = [
  { icon: LayoutDashboard, label: "Dashboard", path: "/student" },
  { icon: FileText, label: "Exams", path: "/student/exams" },
  { icon: TrendingUp, label: "Performance", path: "/student/performance" },
  { icon: Settings, label: "Settings", path: "/student/settings" },
];

export function StudentExams() {
  const [activeTab, setActiveTab] = useState<"available" | "upcoming" | "completed">("available");
  const [searchQuery, setSearchQuery] = useState("");
  const [exams, setExams] = useState<StudentExamSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadExams = async () => {
    try {
      setLoading(true);
      const response = await studentExamApi.getExams();
      setExams(response.data || []);
      setError("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to fetch exams.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadExams();
    const handleFocus = () => void loadExams();
    window.addEventListener("focus", handleFocus);
    return () => window.removeEventListener("focus", handleFocus);
  }, []);

  const filteredExams = useMemo(() => {
    const search = searchQuery.trim().toLowerCase();
    return search ? exams.filter((exam) => `${exam.title} ${exam.faculty}`.toLowerCase().includes(search)) : exams;
  }, [exams, searchQuery]);

  return (
    <DashboardLayout menuItems={menuItems} userRole="Student">
      <div className="space-y-6">
        <div><h1 className="text-3xl font-bold text-foreground mb-2">My Exams</h1><p className="text-muted-foreground">View and manage all your exams</p></div>
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1 relative"><Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" /><input type="text" placeholder="Search exams..." value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} className="w-full pl-10 pr-4 py-2 rounded-lg border border-border bg-input-background focus:outline-none focus:ring-2 focus:ring-ring" /></div>
          <button className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border bg-white hover:bg-muted/30 transition-colors"><Filter className="w-5 h-5" /><span>Filter</span></button>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-border">
          <div className="border-b border-border"><div className="flex">
            {(["available", "upcoming", "completed"] as const).map((tab) => <button key={tab} onClick={() => setActiveTab(tab)} className={`flex-1 px-6 py-4 font-medium transition-colors ${activeTab === tab ? "text-primary border-b-2 border-primary" : "text-muted-foreground hover:text-foreground"}`}>{tab[0].toUpperCase() + tab.slice(1)} ({tab === "available" ? exams.length : 0})</button>)}
          </div></div>
          <div className="p-6">
            {activeTab !== "available" ? <div className="text-center py-12"><CheckCircle className="w-16 h-16 text-muted-foreground mx-auto mb-4" /><p className="text-muted-foreground">No {activeTab} exams at the moment</p></div> : loading ? <div className="text-center py-12 text-muted-foreground">Loading exams...</div> : error ? <div className="text-center py-12 text-destructive">{error}</div> : filteredExams.length === 0 ? <div className="text-center py-12"><FileText className="w-16 h-16 text-muted-foreground mx-auto mb-4" /><p className="text-muted-foreground">No available exams at the moment</p></div> : <div className="space-y-4">
              {filteredExams.map((exam) => <div key={exam.id} className="p-6 rounded-lg border border-border hover:border-primary transition-colors"><div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4"><div className="flex-1"><div className="flex items-start gap-3 mb-3"><div className="w-12 h-12 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center flex-shrink-0"><FileText className="w-6 h-6 text-white" /></div><div><h4 className="font-semibold text-lg text-foreground mb-1">{exam.title}</h4><p className="text-sm text-muted-foreground">{exam.faculty}</p></div></div><div className="grid grid-cols-2 sm:grid-cols-4 gap-3 ml-15"><div className="flex items-center gap-2 text-sm text-muted-foreground"><Calendar className="w-4 h-4" />{new Date(exam.created_at).toLocaleDateString()}</div><div className="flex items-center gap-2 text-sm text-muted-foreground"><Clock className="w-4 h-4" />{exam.duration} min</div><div className="text-sm text-muted-foreground">{exam.total_marks} Marks</div><div className="text-sm text-muted-foreground">{exam.question_count} Questions</div></div></div><Link to={`/exam/${exam.id}`}><button className="w-full sm:w-auto px-6 py-2 rounded-lg bg-gradient-to-r from-primary to-secondary text-white hover:opacity-90 transition-opacity">Start Exam</button></Link></div></div>)}
            </div>}
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

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
      setExams(Array.isArray(response) ? response : []);
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

  const tabExams = useMemo(() => {
    return exams.filter((item) => {
      if (activeTab === "completed") return item.completed;
      if (activeTab === "upcoming") return !item.completed && !item.available;
      return !item.completed && item.available;
    });
  }, [exams, activeTab]);

  const filteredExams = useMemo(() => {
    const search = searchQuery.trim().toLowerCase();
    return search
      ? tabExams.filter((item) =>
          `${item.exam.title} ${item.exam.topics.join(" ")} ${item.exam.department || ""}`
            .toLowerCase()
            .includes(search)
        )
      : tabExams;
  }, [tabExams, searchQuery]);

  const getTabCount = (tab: "available" | "upcoming" | "completed") => {
    if (tab === "completed") return exams.filter((item) => item.completed).length;
    if (tab === "upcoming") return exams.filter((item) => !item.completed && !item.available).length;
    return exams.filter((item) => !item.completed && item.available).length;
  };

  return (
    <DashboardLayout menuItems={menuItems} userRole="Student">
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-foreground mb-1">My Exams</h1>
          <p className="text-xs sm:text-sm text-muted-foreground">View and manage all your exams</p>
        </div>
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="flex-1 relative">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search exams..."
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              className="w-full pl-10 pr-3.5 py-2 rounded-lg border border-border bg-input-background text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
            />
          </div>
          <button className="flex items-center justify-center gap-2 px-4 py-2 rounded-lg border border-border bg-white text-foreground text-xs sm:text-sm font-medium hover:bg-muted/50 transition-colors">
            <Filter className="w-4 h-4" />
            <span>Filter</span>
          </button>
        </div>
        <div className="bg-white rounded-xl shadow-sm border border-border overflow-hidden">
          <div className="border-b border-border">
            <div className="flex">
              {(["available", "upcoming", "completed"] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`flex-1 px-4 sm:px-6 py-3.5 text-xs sm:text-sm font-medium transition-colors ${
                    activeTab === tab ? "text-primary border-b-2 border-primary font-semibold" : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {tab[0].toUpperCase() + tab.slice(1)} ({getTabCount(tab)})
                </button>
              ))}
            </div>
          </div>
          <div className="p-5 sm:p-6">
            {loading ? (
              <div className="text-center py-12 text-xs sm:text-sm text-muted-foreground">Loading exams...</div>
            ) : error ? (
              <div className="text-center py-12 text-xs sm:text-sm text-destructive font-medium">{error}</div>
            ) : filteredExams.length === 0 ? (
              <div className="text-center py-12">
                {activeTab === "completed" ? (
                  <>
                    <CheckCircle className="w-12 h-12 text-muted-foreground/60 mx-auto mb-3" />
                    <p className="text-xs sm:text-sm text-muted-foreground">No completed exams yet.</p>
                  </>
                ) : activeTab === "upcoming" ? (
                  <>
                    <Calendar className="w-12 h-12 text-muted-foreground/60 mx-auto mb-3" />
                    <p className="text-xs sm:text-sm text-muted-foreground">No upcoming exams scheduled.</p>
                  </>
                ) : (
                  <>
                    <FileText className="w-12 h-12 text-muted-foreground/60 mx-auto mb-3" />
                    <p className="text-xs sm:text-sm text-muted-foreground">No exams available for your department right now.</p>
                  </>
                )}
              </div>
            ) : (
              <div className="space-y-3.5">
                {filteredExams.map(({ exam, completed, attempt_id: attemptId, available }) => (
                  <div key={exam.id} className="p-4 sm:p-5 rounded-xl border border-border hover:border-primary/50 hover:shadow-xs transition-all">
                    <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
                      <div className="flex-1">
                        <div className="flex items-start gap-3 mb-3">
                          <div className="w-11 h-11 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center shrink-0 shadow-xs">
                            <FileText className="w-5 h-5 text-white" />
                          </div>
                          <div>
                            <div className="flex items-center gap-2 mb-1 flex-wrap">
                              <h4 className="font-semibold text-base sm:text-lg text-foreground">{exam.title}</h4>
                              {exam.department && (
                                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-primary/10 text-primary border border-primary/20">
                                  {exam.department}
                                </span>
                              )}
                            </div>
                            {exam.topics && exam.topics.length > 0 && (
                              <p className="text-xs sm:text-sm text-muted-foreground">{exam.topics.join(", ")}</p>
                            )}
                          </div>
                        </div>
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 sm:ml-14">
                          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                            <Calendar className="w-3.5 h-3.5" />
                            {exam.starts_at
                              ? new Date(exam.starts_at).toLocaleDateString()
                              : exam.ends_at
                              ? new Date(exam.ends_at).toLocaleDateString()
                              : "Open now"}
                          </div>
                          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                            <Clock className="w-3.5 h-3.5" />
                            {exam.duration_minutes} min
                          </div>
                          <div className="text-xs text-muted-foreground">{exam.total_marks} Marks</div>
                          <div className="text-xs text-muted-foreground">{exam.questions?.length ?? 0} Questions</div>
                        </div>
                      </div>
                      <div>
                        {completed && attemptId ? (
                          <Link to={`/student/results/${attemptId}`}>
                            <button className="w-full sm:w-auto px-4 py-2 rounded-lg border border-border bg-white text-foreground font-medium text-xs sm:text-sm hover:bg-muted/50 shadow-xs transition-all">
                              View Result
                            </button>
                          </Link>
                        ) : (
                          <Link to={`/student/exams/${exam.id}/take`}>
                            <button
                              disabled={!available}
                              className="w-full sm:w-auto px-4 py-2 rounded-lg bg-gradient-to-r from-primary to-secondary text-white font-medium text-xs sm:text-sm hover:opacity-90 shadow-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              Start Exam
                            </button>
                          </Link>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

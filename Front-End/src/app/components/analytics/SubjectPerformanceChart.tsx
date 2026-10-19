import React, { useState, useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
  LabelList,
} from "recharts";
import {
  ArrowDownUp,
  Award,
  BookOpen,
  ChevronRight,
  Eye,
  Info,
  Layers,
  List,
  RotateCcw,
  Sparkles,
  Table as TableIcon,
  X,
} from "lucide-react";
import {
  CLASSIFICATION_MAP,
  PASSING_THRESHOLD,
  formatPercentage,
  getClassificationMeta,
  truncateText,
} from "./chartConstants";
import { AnalyticsChartLegend } from "./AnalyticsChartLegend";
import type {
  StudentPerformanceSubjectsResponse,
  StudentSubjectItem,
  StudentSubjectTopic,
} from "../../../services/api";

interface Props {
  data: StudentPerformanceSubjectsResponse["data"] | null;
  loading?: boolean;
  error?: string;
  onRetry?: () => void;
  overallAverage?: number | null;
}

export function SubjectPerformanceChart({
  data,
  loading = false,
  error = "",
  onRetry,
  overallAverage,
}: Props) {
  const [sortOrder, setSortOrder] = useState<"weakest" | "strongest">("weakest");
  const [showAll, setShowAll] = useState(false);
  const [viewMode, setViewMode] = useState<"chart" | "table">("chart");
  const [selectedDrilldown, setSelectedDrilldown] = useState<StudentSubjectItem | null>(null);

  const rawSubjects = data?.subjects || [];
  const unattemptedSubjects = data?.unattempted_subjects || [];

  // Sort subjects based on current toggle
  const sortedSubjects = useMemo(() => {
    const list = [...rawSubjects];
    if (sortOrder === "weakest") {
      list.sort((a, b) => a.average_score - b.average_score);
    } else {
      list.sort((a, b) => b.average_score - a.average_score);
    }
    return list;
  }, [rawSubjects, sortOrder]);

  const displayedSubjects = useMemo(() => {
    if (showAll || sortedSubjects.length <= 6) {
      return sortedSubjects;
    }
    return sortedSubjects.slice(0, 6);
  }, [sortedSubjects, showAll]);

  // Loading Skeleton State
  if (loading) {
    return (
      <div className="bg-card rounded-xl p-5 sm:p-6 border border-border shadow-2xs animate-pulse">
        <div className="flex justify-between items-center mb-6">
          <div className="space-y-2">
            <div className="h-5 w-44 bg-muted rounded-md" />
            <div className="h-3 w-64 bg-muted/60 rounded-md" />
          </div>
          <div className="h-8 w-28 bg-muted rounded-md" />
        </div>
        <div className="h-64 sm:h-72 w-full bg-muted/30 rounded-lg flex items-center justify-center">
          <div className="text-xs text-muted-foreground flex items-center gap-2">
            <RotateCcw className="w-4 h-4 animate-spin text-primary" />
            Loading subject performance analytics...
          </div>
        </div>
      </div>
    );
  }

  // Error State
  if (error) {
    return (
      <div className="bg-card rounded-xl p-5 sm:p-6 border border-rose-200 dark:border-rose-900/50 shadow-2xs">
        <div className="flex flex-col items-center justify-center py-8 text-center space-y-3">
          <div className="w-10 h-10 rounded-full bg-rose-50 dark:bg-rose-950/50 text-rose-600 flex items-center justify-center">
            <Info className="w-5 h-5" />
          </div>
          <div>
            <h4 className="font-semibold text-foreground text-sm">Failed to Load Subject Analytics</h4>
            <p className="text-xs text-muted-foreground mt-1 max-w-sm">{error}</p>
          </div>
          {onRetry && (
            <button
              onClick={onRetry}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-primary text-white hover:bg-primary/90 transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5" /> Retry
            </button>
          )}
        </div>
      </div>
    );
  }

  // Empty State (No graded exams yet)
  if (!rawSubjects || rawSubjects.length === 0) {
    return (
      <div className="bg-card rounded-xl p-5 sm:p-6 border border-border shadow-2xs">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="font-semibold text-foreground text-sm sm:text-base">Subject Performance</h3>
            <p className="text-xs text-muted-foreground">Rigorous performance across evaluated subjects</p>
          </div>
        </div>
        <div className="h-60 flex flex-col items-center justify-center text-center py-8 space-y-2">
          <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center text-muted-foreground">
            <BookOpen className="w-5 h-5" />
          </div>
          <p className="text-sm font-medium text-foreground">No graded results yet</p>
          <p className="text-xs text-muted-foreground max-w-sm">
            Complete your first exam to view your comprehensive subject breakdown and study focus areas.
          </p>
          {data?.excluded_exams_note && (
            <span className="inline-block mt-2 text-xs bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800 px-2.5 py-1 rounded-md">
              {data.excluded_exams_note}
            </span>
          )}
        </div>
      </div>
    );
  }

  // Dynamic height based on number of items to ensure generous bar breathing room
  const chartHeight = Math.max(260, displayedSubjects.length * 44 + 40);

  return (
    <div
      className="bg-card rounded-xl p-5 sm:p-6 border border-border shadow-2xs flex flex-col justify-between"
      aria-labelledby="subject-performance-title"
    >
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div>
          <div className="flex items-center gap-2">
            <h3
              id="subject-performance-title"
              className="font-semibold text-foreground text-sm sm:text-base"
            >
              {data?.title || "Subject Performance"}
            </h3>
            <span className="text-xs text-primary font-medium bg-primary/10 px-2 py-0.5 rounded-full">
              {rawSubjects.length} {rawSubjects.length === 1 ? "subject" : "subjects"}
            </span>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Average evaluated score per subject · Sorted by {sortOrder === "weakest" ? "weakest first (study priorities)" : "strongest first"}
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex items-center flex-wrap gap-2">
          {/* Weakest / Strongest Sort Toggle */}
          <button
            type="button"
            onClick={() => setSortOrder(sortOrder === "weakest" ? "strongest" : "weakest")}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-lg border border-border bg-background hover:bg-muted text-foreground transition-colors"
            title="Toggle sort order"
          >
            <ArrowDownUp className="w-3.5 h-3.5 text-muted-foreground" />
            <span>{sortOrder === "weakest" ? "Weakest first" : "Strongest first"}</span>
          </button>

          {/* Table / Chart Toggle */}
          <button
            type="button"
            onClick={() => setViewMode(viewMode === "chart" ? "table" : "chart")}
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-lg border transition-colors ${
              viewMode === "table"
                ? "bg-primary text-white border-primary"
                : "border-border bg-background hover:bg-muted text-foreground"
            }`}
            title="Toggle accessible table view"
            aria-pressed={viewMode === "table"}
          >
            {viewMode === "table" ? (
              <>
                <Layers className="w-3.5 h-3.5" /> View Chart
              </>
            ) : (
              <>
                <TableIcon className="w-3.5 h-3.5" /> View as Table
              </>
            )}
          </button>
        </div>
      </div>

      {/* Legend */}
      <div className="mb-4 pb-3 border-b border-border/60">
        <AnalyticsChartLegend />
      </div>

      {/* Chart View or Accessible Table View */}
      {viewMode === "chart" ? (
        <div className="w-full min-w-0" style={{ height: chartHeight }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              layout="vertical"
              data={displayedSubjects}
              margin={{ top: 10, right: 40, left: 10, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="var(--border)" opacity={0.6} />
              
              {/* Horizontal X Axis (Percentage 0 to 100) */}
              <XAxis
                type="number"
                domain={[0, 100]}
                stroke="#6B7280"
                fontSize={11}
                tickLine={false}
                unit="%"
              />

              {/* Vertical Y Axis (Subject Names truncated cleanly on left) */}
              <YAxis
                type="category"
                dataKey="subject"
                stroke="#6B7280"
                fontSize={12}
                tickLine={false}
                width={130}
                tick={({ x, y, payload }) => {
                  const fullName = String(payload.value || "");
                  const shortName = truncateText(fullName, 18);
                  return (
                    <g transform={`translate(${x},${y})`}>
                      <text
                        x={-6}
                        y={4}
                        textAnchor="end"
                        fill="currentColor"
                        className="text-xs font-medium fill-foreground hover:fill-primary cursor-pointer transition-colors"
                      >
                        <title>{fullName}</title>
                        {shortName}
                      </text>
                    </g>
                  );
                }}
              />

              {/* Reference Lines */}
              <ReferenceLine
                x={PASSING_THRESHOLD}
                stroke="#EF4444"
                strokeDasharray="4 4"
                label={{
                  value: "Pass (40%)",
                  position: "insideBottomRight",
                  fill: "#EF4444",
                  fontSize: 10,
                }}
              />
              {overallAverage !== undefined && overallAverage !== null && (
                <ReferenceLine
                  x={overallAverage}
                  stroke="#6366F1"
                  strokeDasharray="3 3"
                  label={{
                    value: `Avg (${overallAverage}%)`,
                    position: "insideTopRight",
                    fill: "#6366F1",
                    fontSize: 10,
                  }}
                />
              )}

              {/* Custom Tooltip */}
              <Tooltip
                cursor={{ fill: "var(--muted)", opacity: 0.25 }}
                content={({ active, payload }) => {
                  if (!active || !payload || !payload.length) return null;
                  const item: StudentSubjectItem = payload[0].payload;
                  const classif = getClassificationMeta(item.average_score);
                  const Icon = classif.icon;

                  return (
                    <div className="bg-card text-foreground rounded-lg p-3 shadow-lg border border-border text-xs space-y-2 min-w-[200px]">
                      <div className="flex items-center justify-between gap-2 border-b border-border pb-1.5">
                        <span className="font-semibold text-sm">{item.subject}</span>
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium border ${classif.badgeClass}`}
                        >
                          <Icon className="w-3 h-3" />
                          {classif.badgeLabel}
                        </span>
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <div>
                          <span className="text-muted-foreground block">Average Score:</span>
                          <span className="font-bold text-sm text-foreground">
                            {formatPercentage(item.average_score)}
                          </span>
                        </div>
                        <div>
                          <span className="text-muted-foreground block">Exams Counted:</span>
                          <span className="font-semibold text-foreground">
                            {item.exams_counted ?? item.exam_count}
                          </span>
                        </div>
                      </div>
                      {item.best_exam_title && (
                        <div className="text-[11px] pt-1 text-muted-foreground">
                          <div>
                            <span className="text-emerald-600 font-medium">Best:</span>{" "}
                            {item.best_exam_title} ({item.highest_score}%)
                          </div>
                          {item.worst_exam_title && item.worst_exam_title !== item.best_exam_title && (
                            <div>
                              <span className="text-amber-600 font-medium">Lowest:</span>{" "}
                              {item.worst_exam_title} ({item.lowest_score}%)
                            </div>
                          )}
                        </div>
                      )}
                      {item.cohort_average !== null && item.cohort_average !== undefined && (
                        <div className="text-[11px] text-muted-foreground border-t border-border pt-1">
                          Cohort Class Average: <span className="font-semibold">{item.cohort_average}%</span>
                        </div>
                      )}
                      {item.has_topic_data && (
                        <div className="text-[10px] text-primary font-medium pt-1">
                          💡 Click bar for real topic drill-down
                        </div>
                      )}
                    </div>
                  );
                }}
              />

              {/* Horizontal Bars with Color-Coding */}
              <Bar
                dataKey="average_score"
                radius={[0, 6, 6, 0]}
                onClick={(entry: any) => {
                  if (entry?.has_topic_data) {
                    setSelectedDrilldown(entry);
                  }
                }}
              >
                {displayedSubjects.map((entry, index) => {
                  const meta = getClassificationMeta(entry.average_score);
                  return (
                    <Cell
                      key={`subj-cell-${index}`}
                      fill={meta.fill}
                      className={entry.has_topic_data ? "cursor-pointer hover:opacity-85 transition-opacity" : ""}
                    />
                  );
                })}
                {/* Text values directly on the bars */}
                <LabelList
                  dataKey="average_score"
                  position="right"
                  formatter={(val: any) => `${val}%`}
                  className="fill-foreground font-semibold text-[11px]"
                />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        /* Accessible Table Alternative */
        <div className="w-full overflow-x-auto my-2 rounded-lg border border-border">
          <table className="w-full text-left text-xs border-collapse">
            <caption className="sr-only">Student Subject Performance Table</caption>
            <thead className="bg-muted/60 text-muted-foreground border-b border-border">
              <tr>
                <th scope="col" className="p-2.5 font-medium">Subject</th>
                <th scope="col" className="p-2.5 font-medium">Average Score</th>
                <th scope="col" className="p-2.5 font-medium">Classification</th>
                <th scope="col" className="p-2.5 font-medium">Exams Counted</th>
                <th scope="col" className="p-2.5 font-medium">Best Score</th>
                <th scope="col" className="p-2.5 font-medium">Topics</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/60">
              {sortedSubjects.map((s, idx) => {
                const meta = getClassificationMeta(s.average_score);
                const Icon = meta.icon;
                return (
                  <tr key={`table-row-${idx}`} className="hover:bg-muted/30">
                    <th scope="row" className="p-2.5 font-semibold text-foreground">
                      {s.subject}
                    </th>
                    <td className="p-2.5 font-bold text-foreground">
                      {formatPercentage(s.average_score)}
                    </td>
                    <td className="p-2.5">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium border ${meta.badgeClass}`}>
                        <Icon className="w-3 h-3" />
                        {meta.badgeLabel}
                      </span>
                    </td>
                    <td className="p-2.5 text-muted-foreground">
                      {s.exams_counted ?? s.exam_count}
                    </td>
                    <td className="p-2.5 text-muted-foreground">
                      {s.highest_score}% {s.best_exam_title && `(${s.best_exam_title})`}
                    </td>
                    <td className="p-2.5">
                      {s.has_topic_data ? (
                        <button
                          type="button"
                          onClick={() => setSelectedDrilldown(s)}
                          className="text-primary hover:underline font-medium inline-flex items-center gap-1"
                        >
                          View {s.topics?.length || 0} topics <ChevronRight className="w-3 h-3" />
                        </button>
                      ) : (
                        <span className="text-muted-foreground">Not tagged</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Show All / Show Less Toggle if > 6 subjects */}
      {sortedSubjects.length > 6 && viewMode === "chart" && (
        <div className="flex justify-center mt-2">
          <button
            type="button"
            onClick={() => setShowAll(!showAll)}
            className="text-xs text-primary hover:underline font-medium inline-flex items-center gap-1"
          >
            {showAll ? "Show Top 6 Only" : `Show All ${sortedSubjects.length} Subjects`}
          </button>
        </div>
      )}

      {/* Sub-chart Information / Insights / Excluded rows */}
      <div className="mt-4 pt-3 border-t border-border space-y-2">
        {/* Real Data Insight Line */}
        {data?.insight && (
          <div className="flex items-center gap-2 text-xs font-medium text-foreground bg-accent/40 rounded-lg p-2.5">
            <Sparkles className="w-4 h-4 text-primary shrink-0" />
            <span>{data.insight}</span>
          </div>
        )}

        {/* Data Excluded Notice */}
        {data?.excluded_exams_note && (
          <div className="flex items-center gap-1.5 text-xs text-amber-700 dark:text-amber-400 bg-amber-50/70 dark:bg-amber-950/30 px-2.5 py-1.5 rounded-md border border-amber-200/60 dark:border-amber-800/40">
            <Info className="w-3.5 h-3.5 shrink-0" />
            <span>{data.excluded_exams_note}</span>
          </div>
        )}

        {/* Muted Placeholder Row for Subjects with No Graded Exams */}
        {unattemptedSubjects.length > 0 && (
          <div className="text-xs text-muted-foreground pt-1">
            <span className="font-medium text-foreground">No graded results yet:</span>{" "}
            {unattemptedSubjects.map((u, i) => (
              <span key={u.subject} className="inline-flex items-center">
                {u.subject}
                {u.status === "pending_grading" && " (evaluation in progress)"}
                {i < unattemptedSubjects.length - 1 ? ", " : ""}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Real Topic Drilldown Modal */}
      {selectedDrilldown && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="drilldown-title"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs animate-in fade-in"
        >
          <div className="bg-card w-full max-w-lg rounded-xl border border-border shadow-2xl p-5 sm:p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div>
                <h4 id="drilldown-title" className="font-bold text-base text-foreground">
                  {selectedDrilldown.subject} · Topic Accuracy
                </h4>
                <p className="text-xs text-muted-foreground">
                  Computed from genuine per-question topic tags of evaluated answers
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedDrilldown(null)}
                className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                aria-label="Close modal"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {selectedDrilldown.topics && selectedDrilldown.topics.length > 0 ? (
              <div className="space-y-3 max-h-80 overflow-y-auto pr-1">
                {selectedDrilldown.topics.map((t) => {
                  const meta = getClassificationMeta(t.average_score);
                  return (
                    <div key={t.topic} className="p-2.5 rounded-lg border border-border bg-muted/20 space-y-1">
                      <div className="flex justify-between items-center text-xs">
                        <span className="font-semibold text-foreground">{t.topic}</span>
                        <span className="font-bold">{formatPercentage(t.average_score)}</span>
                      </div>
                      <div className="w-full bg-muted rounded-full h-2 overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-300"
                          style={{ width: `${Math.min(100, Math.max(0, t.average_score))}%`, backgroundColor: meta.fill }}
                        />
                      </div>
                      <div className="flex justify-between items-center text-[10px] text-muted-foreground pt-0.5">
                        <span>{t.questions_count} {t.questions_count === 1 ? "question" : "questions"} evaluated</span>
                        <span className={`px-1.5 py-0.2 rounded font-medium border ${meta.badgeClass}`}>
                          {meta.badgeLabel}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground py-4 text-center">
                No per-question topic tags exist for this subject.
              </p>
            )}

            <div className="flex justify-end pt-2">
              <button
                type="button"
                onClick={() => setSelectedDrilldown(null)}
                className="px-4 py-1.5 rounded-lg bg-primary text-white text-xs font-medium hover:bg-primary/90 transition-colors"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

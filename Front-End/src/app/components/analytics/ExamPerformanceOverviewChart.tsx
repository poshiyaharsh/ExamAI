import React, { useState, useMemo } from "react";
import { Link } from "react-router-dom";
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
  ArrowRight,
  BookOpen,
  Calendar,
  Clock,
  Eye,
  Info,
  Layers,
  RotateCcw,
  Table as TableIcon,
  Users,
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
  FacultyExamPerfItem,
  FacultyExamPerfSummary,
} from "../../../services/api";

interface Props {
  exams: FacultyExamPerfItem[];
  summary?: FacultyExamPerfSummary;
  generatedAt?: string;
  loading?: boolean;
  error?: string;
  onRetry?: () => void;
}

export function ExamPerformanceOverviewChart({
  exams,
  summary,
  generatedAt,
  loading = false,
  error = "",
  onRetry,
}: Props) {
  const [rangeLimit, setRangeLimit] = useState<number | "all">(8);
  const [viewMode, setViewMode] = useState<"chart" | "table">("chart");

  // Separate exams with results from exams with no submissions / pending grading
  const filteredExams = useMemo(() => {
    let list = [...exams];
    if (rangeLimit !== "all") {
      list = list.slice(0, rangeLimit);
    }
    return list;
  }, [exams, rangeLimit]);

  const examsWithResults = useMemo(
    () => filteredExams.filter((e) => e.status === "has_results" && e.average_score !== null),
    [filteredExams]
  );

  const examsWithoutResults = useMemo(
    () => filteredExams.filter((e) => e.status !== "has_results" || e.average_score === null),
    [filteredExams]
  );

  const badgeText = summary?.badge_text || `${exams.length} exams · ${examsWithResults.length} with results`;

  // Format updated timestamp
  const updatedTime = useMemo(() => {
    if (!generatedAt) return "Just now";
    try {
      const d = new Date(generatedAt);
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch {
      return "Recently";
    }
  }, [generatedAt]);

  // Loading Skeleton
  if (loading) {
    return (
      <div className="bg-card rounded-xl shadow-2xs border border-border p-5 sm:p-6 animate-pulse">
        <div className="flex justify-between items-center mb-6">
          <div className="space-y-2">
            <div className="h-5 w-48 bg-muted rounded-md" />
            <div className="h-3 w-64 bg-muted/60 rounded-md" />
          </div>
          <div className="h-7 w-24 bg-muted rounded-full" />
        </div>
        <div className="h-60 w-full bg-muted/30 rounded-lg flex items-center justify-center">
          <div className="text-xs text-muted-foreground flex items-center gap-2">
            <RotateCcw className="w-4 h-4 animate-spin text-primary" />
            Loading exam performance overview...
          </div>
        </div>
      </div>
    );
  }

  // Error State
  if (error) {
    return (
      <div className="bg-card rounded-xl shadow-2xs border border-rose-200 dark:border-rose-900/50 p-5 sm:p-6">
        <div className="flex flex-col items-center justify-center py-8 text-center space-y-3">
          <div className="w-10 h-10 rounded-full bg-rose-50 dark:bg-rose-950/50 text-rose-600 flex items-center justify-center">
            <Info className="w-5 h-5" />
          </div>
          <div>
            <h4 className="font-semibold text-foreground text-sm">Failed to Load Exam Overview</h4>
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

  // Empty State (No published exams yet)
  if (!exams || exams.length === 0) {
    return (
      <div className="bg-card rounded-xl shadow-2xs border border-border p-5 sm:p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="font-semibold text-foreground text-sm sm:text-base">Exam Performance Overview</h3>
            <p className="text-xs text-muted-foreground">Class average score (%) across published exams</p>
          </div>
          <span className="text-xs text-muted-foreground font-medium bg-muted px-2.5 py-0.5 rounded-full">
            0 exams
          </span>
        </div>
        <div className="h-56 flex flex-col items-center justify-center text-center py-6 space-y-2">
          <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center text-muted-foreground">
            <BookOpen className="w-5 h-5" />
          </div>
          <p className="text-sm font-medium text-foreground">No published exams yet</p>
          <p className="text-xs text-muted-foreground max-w-sm">
            Publish an exam from your draft papers to monitor student performance and class benchmarks.
          </p>
        </div>
      </div>
    );
  }

  // Calculate dynamic chart height based on active exams with results
  const chartHeight = Math.max(220, examsWithResults.length * 44 + 40);

  return (
    <div
      className="bg-card rounded-xl shadow-2xs border border-border p-5 sm:p-6 flex flex-col justify-between"
      aria-label="Exam Performance Overview Analytics"
    >
      {/* Header and Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-foreground text-sm sm:text-base">
              Exam Performance Overview
            </h3>
            {/* Honest Badge */}
            <span
              className="text-xs text-primary font-medium bg-primary/10 px-2.5 py-0.5 rounded-full"
              title="Accurately shows total published exams vs exams with evaluated student submissions"
            >
              {badgeText}
            </span>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Class average score (%) across fully evaluated published exams
          </p>
        </div>

        {/* Right side controls: Range selector & Table Toggle */}
        <div className="flex items-center flex-wrap gap-2">
          {/* Range Selector */}
          <div className="flex items-center rounded-lg border border-border bg-muted/40 p-0.5 text-xs">
            <button
              type="button"
              onClick={() => setRangeLimit(5)}
              className={`px-2 py-0.5 rounded-md font-medium transition-colors ${
                rangeLimit === 5 ? "bg-card text-foreground shadow-2xs" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Last 5
            </button>
            <button
              type="button"
              onClick={() => setRangeLimit(8)}
              className={`px-2 py-0.5 rounded-md font-medium transition-colors ${
                rangeLimit === 8 ? "bg-card text-foreground shadow-2xs" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Last 8
            </button>
            <button
              type="button"
              onClick={() => setRangeLimit("all")}
              className={`px-2 py-0.5 rounded-md font-medium transition-colors ${
                rangeLimit === "all" ? "bg-card text-foreground shadow-2xs" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              All
            </button>
          </div>

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
                <Layers className="w-3.5 h-3.5" /> Chart
              </>
            ) : (
              <>
                <TableIcon className="w-3.5 h-3.5" /> Table
              </>
            )}
          </button>
        </div>
      </div>

      {/* Shared Legend */}
      <div className="mb-4 pb-3 border-b border-border/60">
        <AnalyticsChartLegend />
      </div>

      {/* Main Visualization or Accessible Table */}
      {viewMode === "chart" ? (
        examsWithResults.length > 0 ? (
          <div className="w-full min-w-0" style={{ height: chartHeight }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                layout="vertical"
                data={examsWithResults}
                margin={{ top: 10, right: 40, left: 10, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="var(--border)" opacity={0.6} />

                {/* Horizontal X Axis (Class Avg 0 to 100%) */}
                <XAxis
                  type="number"
                  domain={[0, 100]}
                  stroke="#6B7280"
                  fontSize={11}
                  tickLine={false}
                  unit="%"
                />

                {/* Vertical Y Axis (Exam Titles truncated on left with tooltip) */}
                <YAxis
                  type="category"
                  dataKey="exam_title"
                  stroke="#6B7280"
                  fontSize={12}
                  tickLine={false}
                  width={140}
                  tick={({ x, y, payload }) => {
                    const fullName = String(payload.value || "");
                    const shortName = truncateText(fullName, 19);
                    return (
                      <g transform={`translate(${x},${y})`}>
                        <text
                          x={-6}
                          y={4}
                          textAnchor="end"
                          fill="currentColor"
                          className="text-xs font-medium fill-foreground hover:fill-primary cursor-default"
                        >
                          <title>{fullName}</title>
                          {shortName}
                        </text>
                      </g>
                    );
                  }}
                />

                {/* Passing Benchmark Reference Line (40%) */}
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

                {/* Rich Custom Tooltip */}
                <Tooltip
                  cursor={{ fill: "var(--muted)", opacity: 0.25 }}
                  content={({ active, payload }) => {
                    if (!active || !payload || !payload.length) return null;
                    const item: FacultyExamPerfItem = payload[0].payload;
                    const meta = getClassificationMeta(item.average_score);
                    const Icon = meta.icon;

                    return (
                      <div className="bg-card text-foreground rounded-lg p-3.5 shadow-lg border border-border text-xs space-y-2 min-w-[220px]">
                        <div className="flex items-center justify-between gap-2 border-b border-border pb-1.5">
                          <span className="font-semibold text-sm">{item.exam_title}</span>
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium border ${meta.badgeClass}`}>
                            <Icon className="w-3 h-3" />
                            {meta.badgeLabel}
                          </span>
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          <div>
                            <span className="text-muted-foreground block">Class Average:</span>
                            <span className="font-bold text-sm text-foreground">
                              {formatPercentage(item.average_score)}
                            </span>
                          </div>
                          <div>
                            <span className="text-muted-foreground block">Pass Rate:</span>
                            <span className="font-bold text-sm text-foreground">
                              {item.pass_rate !== null ? `${item.pass_rate}%` : "N/A"}
                            </span>
                          </div>
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-[11px] text-muted-foreground border-t border-border pt-1.5">
                          <div>
                            <span>Highest: </span>
                            <span className="font-semibold text-foreground">{item.highest_score ?? "-"}%</span>
                          </div>
                          <div>
                            <span>Lowest: </span>
                            <span className="font-semibold text-foreground">{item.lowest_score ?? "-"}%</span>
                          </div>
                        </div>
                        <div className="text-[11px] text-muted-foreground pt-0.5">
                          Submissions: <span className="font-semibold text-foreground">{item.graded_count ?? item.submissions_count}</span>
                          {item.eligible_students_count ? ` / ${item.eligible_students_count} students` : ""}
                          {item.pending_grading_count ? ` (${item.pending_grading_count} pending)` : ""}
                        </div>
                      </div>
                    );
                  }}
                />

                {/* Horizontal Bars with Classification Fill */}
                <Bar dataKey="average_score" radius={[0, 6, 6, 0]}>
                  {examsWithResults.map((entry, index) => {
                    const meta = getClassificationMeta(entry.average_score);
                    return <Cell key={`faculty-bar-${index}`} fill={meta.fill} />;
                  })}
                  {/* Percentage text label directly on bar */}
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
          <div className="h-44 flex items-center justify-center text-xs text-muted-foreground bg-muted/20 rounded-lg">
            None of the recent published exams have fully evaluated student attempts yet.
          </div>
        )
      ) : (
        /* Accessible Table Alternative */
        <div className="w-full overflow-x-auto my-2 rounded-lg border border-border">
          <table className="w-full text-left text-xs border-collapse">
            <caption className="sr-only">Faculty Published Exams Performance Overview</caption>
            <thead className="bg-muted/60 text-muted-foreground border-b border-border">
              <tr>
                <th scope="col" className="p-2.5 font-medium">Exam Title</th>
                <th scope="col" className="p-2.5 font-medium">Subject</th>
                <th scope="col" className="p-2.5 font-medium">Status</th>
                <th scope="col" className="p-2.5 font-medium">Class Avg</th>
                <th scope="col" className="p-2.5 font-medium">Pass Rate</th>
                <th scope="col" className="p-2.5 font-medium">Submissions</th>
                <th scope="col" className="p-2.5 font-medium">Eligible</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/60">
              {filteredExams.map((e, idx) => {
                const meta = getClassificationMeta(e.average_score);
                const Icon = meta.icon;
                return (
                  <tr key={`table-exam-${idx}`} className="hover:bg-muted/30">
                    <th scope="row" className="p-2.5 font-semibold text-foreground">
                      {e.exam_title}
                    </th>
                    <td className="p-2.5 text-muted-foreground">{e.subject || "-"}</td>
                    <td className="p-2.5">
                      {e.status === "has_results" ? (
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium border ${meta.badgeClass}`}>
                          <Icon className="w-3 h-3" />
                          {meta.badgeLabel}
                        </span>
                      ) : e.status === "pending_grading" ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-50 text-amber-700 border border-amber-200">
                          Pending Grading
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-slate-100 text-slate-600 border border-slate-200">
                          No Submissions
                        </span>
                      )}
                    </td>
                    <td className="p-2.5 font-bold text-foreground">
                      {formatPercentage(e.average_score)}
                    </td>
                    <td className="p-2.5 text-muted-foreground">
                      {e.pass_rate !== null ? `${e.pass_rate}%` : "-"}
                    </td>
                    <td className="p-2.5 text-muted-foreground">
                      {e.graded_count ?? e.submissions_count}
                    </td>
                    <td className="p-2.5 text-muted-foreground">
                      {e.eligible_students_count ?? "-"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Muted Placeholder Rows for Exams with No Submissions / Pending */}
      {examsWithoutResults.length > 0 && (
        <div className="mt-3 pt-3 border-t border-border/60 space-y-1.5">
          <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider block">
            Published Exams Awaiting Results ({examsWithoutResults.length})
          </span>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
            {examsWithoutResults.map((ex) => (
              <div
                key={ex.id}
                className="flex items-center justify-between p-2 rounded-lg bg-muted/30 border border-border/40 text-muted-foreground"
              >
                <div className="truncate pr-2">
                  <span className="font-medium text-foreground">{truncateText(ex.exam_title, 26)}</span>
                  <span className="text-[11px] block">{ex.subject}</span>
                </div>
                <span className="text-[11px] px-2 py-0.5 rounded-md bg-muted text-muted-foreground shrink-0 border border-border">
                  {ex.status === "pending_grading"
                    ? `${ex.pending_grading_count || 1} pending review`
                    : "0 submissions"}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Footer Details: Last Updated & View All Results link */}
      <div className="mt-4 pt-3 border-t border-border flex items-center justify-between text-xs text-muted-foreground">
        <span className="flex items-center gap-1">
          <Clock className="w-3.5 h-3.5 text-muted-foreground/70" />
          Updated {updatedTime}
        </span>
        <Link
          to="/faculty/results"
          className="text-primary hover:underline font-medium inline-flex items-center gap-1"
        >
          View all results <ArrowRight className="w-3 h-3" />
        </Link>
      </div>
    </div>
  );
}

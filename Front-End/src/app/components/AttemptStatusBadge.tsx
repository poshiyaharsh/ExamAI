import React from "react";
import {
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  PlayCircle,
  MinusCircle,
  FileQuestion,
} from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "./ui/tooltip";

export interface ResultStatusInfo {
  status_code?: string;
  label?: string;
  sub_label?: string;
  tooltip?: string;
  badge_variant?: string;
  is_passed?: boolean | null;
  is_provisional?: boolean;
  submit_reason?: string;
}

interface AttemptStatusBadgeProps {
  status?: string;
  resultStatus?: ResultStatusInfo;
  isPassed?: boolean | null;
  size?: "sm" | "md";
  showTooltip?: boolean;
  className?: string;
}

export function AttemptStatusBadge({
  status,
  resultStatus,
  isPassed,
  size = "md",
  showTooltip = true,
  className = "",
}: AttemptStatusBadgeProps) {
  // Determine canonical code
  const code = (
    resultStatus?.status_code ||
    (status === "auto_submitted" ? "auto_submitted" : "") ||
    (status === "in_progress" ? "in_progress" : "") ||
    (status === "submitted" && resultStatus?.is_provisional ? "pending_grading" : "") ||
    (isPassed === true ? "pass" : isPassed === false ? "fail" : "pending_grading")
  ).toLowerCase();

  let label = resultStatus?.label;
  let subLabel = resultStatus?.sub_label;
  let tooltip = resultStatus?.tooltip;
  let icon = <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />;
  let styleClasses = "bg-emerald-50 text-emerald-700 border-emerald-200";

  switch (code) {
    case "pass":
      label = label || "Pass";
      tooltip = tooltip || "Passed the examination.";
      icon = <CheckCircle2 className="w-3.5 h-3.5 shrink-0 text-emerald-600" />;
      styleClasses = "bg-emerald-50 text-emerald-700 border-emerald-200";
      break;

    case "fail":
      label = label || "Fail";
      tooltip = tooltip || "Did not meet the passing mark.";
      icon = <XCircle className="w-3.5 h-3.5 shrink-0 text-rose-600" />;
      styleClasses = "bg-rose-50 text-rose-700 border-rose-200";
      break;

    case "pending_grading":
    case "submitted":
      label = label || "Pending grading";
      subLabel = subLabel || "Provisional";
      tooltip = tooltip || "Subjective answers are pending review. Score shown is provisional.";
      icon = <Clock className="w-3.5 h-3.5 shrink-0 text-amber-600" />;
      styleClasses = "bg-amber-50 text-amber-700 border-amber-200";
      break;

    case "auto_submitted":
      label = label || "Auto-submitted";
      subLabel = subLabel || (resultStatus?.submit_reason === "violations" ? "Violations" : "Time up");
      tooltip = tooltip || (resultStatus?.submit_reason === "violations"
        ? "Auto-submitted due to proctoring rule violations."
        : "Auto-submitted when testing time limit was reached.");
      icon = <AlertTriangle className="w-3.5 h-3.5 shrink-0 text-rose-600" />;
      styleClasses = isPassed ? "bg-amber-50 text-amber-700 border-amber-200" : "bg-rose-50 text-rose-700 border-rose-200";
      break;

    case "in_progress":
      label = label || "In progress";
      tooltip = tooltip || "Student is actively taking this exam.";
      icon = <PlayCircle className="w-3.5 h-3.5 shrink-0 text-blue-600" />;
      styleClasses = "bg-blue-50 text-blue-700 border-blue-200";
      break;

    case "not_attempted":
      label = label || "Not attempted";
      tooltip = tooltip || "The exam was not attempted.";
      icon = <MinusCircle className="w-3.5 h-3.5 shrink-0 text-slate-500" />;
      styleClasses = "bg-slate-100 text-slate-700 border-slate-200";
      break;

    default:
      label = label || status || "Evaluated";
      icon = <FileQuestion className="w-3.5 h-3.5 shrink-0 text-slate-500" />;
      styleClasses = "bg-slate-100 text-slate-700 border-slate-200";
      break;
  }

  const padding = size === "sm" ? "px-2 py-0.5 text-[11px]" : "px-2.5 py-1 text-xs";

  const badgeContent = (
    <span
      className={`inline-flex items-center gap-1.5 font-semibold rounded-full border whitespace-nowrap select-none transition-colors ${padding} ${styleClasses} ${className}`}
      role="status"
    >
      {icon}
      <span>{label}</span>
      {subLabel && (
        <span className="opacity-75 font-normal text-[10px] hidden sm:inline">
          ({subLabel})
        </span>
      )}
    </span>
  );

  if (!showTooltip || !tooltip) {
    return badgeContent;
  }

  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip>
        <TooltipTrigger asChild>{badgeContent}</TooltipTrigger>
        <TooltipContent side="top" className="max-w-xs text-xs">
          {tooltip}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

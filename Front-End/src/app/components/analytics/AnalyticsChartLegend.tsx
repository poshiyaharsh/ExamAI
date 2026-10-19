import React from "react";
import { CLASSIFICATION_MAP } from "./chartConstants";

interface Props {
  className?: string;
  showTooltips?: boolean;
}

export function AnalyticsChartLegend({ className = "" }: Props) {
  const classes = [
    CLASSIFICATION_MAP.strong,
    CLASSIFICATION_MAP.average,
    CLASSIFICATION_MAP.needs_focus,
  ];

  return (
    <div
      role="group"
      aria-label="Chart Classification Legend"
      className={`flex flex-wrap items-center gap-3 sm:gap-4 text-xs font-medium ${className}`}
    >
      {classes.map((c) => {
        const Icon = c.icon;
        return (
          <div
            key={c.code}
            className="flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-muted/50 border border-border/40 hover:bg-muted transition-colors cursor-default"
            title={`${c.label}: Threshold applied across all metrics`}
          >
            <span
              className="w-2.5 h-2.5 rounded-full shrink-0"
              style={{ backgroundColor: c.fill }}
              aria-hidden="true"
            />
            <Icon className="w-3.5 h-3.5 text-muted-foreground" aria-hidden="true" />
            <span className="text-foreground">{c.label}</span>
          </div>
        );
      })}
    </div>
  );
}

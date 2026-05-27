"use client";

import { cn } from "@/lib/utils";
import type { RiskLevel } from "@/types";

interface RiskBadgeProps {
  level: RiskLevel;
  className?: string;
  showDot?: boolean;
}

const BADGE_STYLES: Record<RiskLevel, string> = {
  LOW: "bg-emerald-100 text-emerald-800 border border-emerald-200",
  MEDIUM: "bg-amber-100 text-amber-800 border border-amber-200",
  HIGH: "bg-red-100 text-red-800 border border-red-200",
  CRITICAL: "bg-red-100 text-red-900 border border-red-300",
};

const LABEL: Record<RiskLevel, string> = {
  LOW: "Low Risk",
  MEDIUM: "Medium Risk",
  HIGH: "High Risk",
  CRITICAL: "Critical",
};

export function RiskBadge({ level, className, showDot = true }: RiskBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold tracking-wide",
        BADGE_STYLES[level],
        className,
      )}
    >
      {showDot && (
        <span
          className={cn(
            "w-1.5 h-1.5 rounded-full flex-shrink-0",
            level === "LOW" && "bg-emerald-500",
            level === "MEDIUM" && "bg-amber-500",
            level === "HIGH" && "bg-red-500",
            level === "CRITICAL" && "bg-red-600 animate-pulse",
          )}
        />
      )}
      {LABEL[level]}
    </span>
  );
}

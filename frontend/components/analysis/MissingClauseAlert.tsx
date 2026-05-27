"use client";

import { AlertTriangle, AlertCircle, Info } from "lucide-react";
import { cn } from "@/lib/utils";
import type { MissingClause } from "@/types";

const SEVERITY_CONFIG = {
  CRITICAL: {
    icon: AlertTriangle,
    bg: "bg-red-50 border-red-300",
    title: "text-red-800",
    body: "text-red-700",
    badge: "bg-red-100 text-red-800 border border-red-200",
    iconColor: "text-red-500",
  },
  IMPORTANT: {
    icon: AlertCircle,
    bg: "bg-amber-50 border-amber-200",
    title: "text-amber-800",
    body: "text-amber-700",
    badge: "bg-amber-100 text-amber-800 border border-amber-200",
    iconColor: "text-amber-500",
  },
  RECOMMENDED: {
    icon: Info,
    bg: "bg-blue-50 border-blue-200",
    title: "text-blue-800",
    body: "text-blue-700",
    badge: "bg-blue-100 text-blue-800 border border-blue-200",
    iconColor: "text-blue-500",
  },
};

const CLAUSE_LABELS: Record<string, string> = {
  CONFIDENTIALITY: "Confidentiality Clause",
  DEFINITIONS: "Definitions Section",
  GOVERNING_LAW: "Governing Law Clause",
  DISPUTE_RESOLUTION: "Dispute Resolution Clause",
  FORCE_MAJEURE: "Force Majeure Clause",
  PAYMENT_TERMS: "Payment Terms",
  IP_ASSIGNMENT: "IP Assignment Clause",
  TERMINATION_FOR_CAUSE: "Termination for Cause",
  NOTICE: "Notice Requirements",
  DATA_PROTECTION: "Data Protection Clause",
  AUTO_RENEWAL: "Auto-Renewal Terms",
  LIMITATION_OF_LIABILITY: "Limitation of Liability",
  WARRANTY_DISCLAIMER: "Warranty Disclaimer",
  TERMINATION_FOR_CONVENIENCE: "Termination for Convenience",
  WORK_PRODUCT: "Work Product Ownership",
  ASSIGNMENT: "Assignment Rights",
};

interface MissingClauseAlertProps {
  missing: MissingClause;
}

export function MissingClauseAlert({ missing }: MissingClauseAlertProps) {
  const config = SEVERITY_CONFIG[missing.severity];
  const Icon = config.icon;
  const label = CLAUSE_LABELS[missing.clause_type] ?? missing.clause_type;

  return (
    <div className={cn("rounded-xl border p-4 space-y-2", config.bg)}>
      <div className="flex items-start gap-2.5">
        <Icon className={cn("h-4 w-4 flex-shrink-0 mt-0.5", config.iconColor)} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <p className={cn("text-sm font-semibold", config.title)}>{label}</p>
            <span
              className={cn(
                "text-xs px-2 py-0.5 rounded-full font-medium",
                config.badge,
              )}
            >
              {missing.severity === "CRITICAL"
                ? "Missing – Critical"
                : missing.severity === "IMPORTANT"
                ? "Missing – Important"
                : "Recommended"}
            </span>
          </div>
          <p className={cn("text-xs mt-1 leading-relaxed", config.body)}>
            {missing.why_it_matters}
          </p>
        </div>
      </div>

      <div className="ml-6.5 pl-0.5">
        <p className="text-xs font-semibold text-gray-500 mb-1">Example language:</p>
        <p className="text-xs text-gray-600 italic bg-white/60 rounded p-2 border border-white/80">
          {missing.example_language}
        </p>
      </div>
    </div>
  );
}

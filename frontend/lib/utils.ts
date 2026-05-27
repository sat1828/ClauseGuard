import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import type { RiskLevel, MissingClauseSeverity } from "@/types";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// ── Risk Color System ─────────────────────────────────────────────────────────
// Colors are defined in globals.css as CSS variables for theme consistency.

export const RISK_COLORS: Record<
  RiskLevel,
  { bg: string; text: string; border: string; badge: string }
> = {
  LOW: {
    bg: "bg-emerald-50",
    text: "text-emerald-800",
    border: "border-emerald-200",
    badge: "bg-emerald-100 text-emerald-800",
  },
  MEDIUM: {
    bg: "bg-amber-50",
    text: "text-amber-800",
    border: "border-amber-200",
    badge: "bg-amber-100 text-amber-800",
  },
  HIGH: {
    bg: "bg-orange-50",
    text: "text-red-800",
    border: "border-orange-200",
    badge: "bg-red-100 text-red-800",
  },
  CRITICAL: {
    bg: "bg-red-50",
    text: "text-red-900",
    border: "border-red-300",
    badge: "bg-red-100 text-red-900",
  },
};

export const SEVERITY_COLORS: Record<
  MissingClauseSeverity,
  { bg: string; text: string; border: string }
> = {
  RECOMMENDED: {
    bg: "bg-blue-50",
    text: "text-blue-800",
    border: "border-blue-200",
  },
  IMPORTANT: {
    bg: "bg-amber-50",
    text: "text-amber-800",
    border: "border-amber-200",
  },
  CRITICAL: {
    bg: "bg-red-50",
    text: "text-red-800",
    border: "border-red-300",
  },
};

export function getRiskScoreColor(score: number): string {
  if (score <= 3) return "text-emerald-600";
  if (score <= 6) return "text-amber-600";
  return "text-red-600";
}

export function getRiskScoreBg(score: number): string {
  if (score <= 3) return "bg-emerald-50 border-emerald-200";
  if (score <= 6) return "bg-amber-50 border-amber-200";
  return "bg-red-50 border-red-200";
}

// ── Date Formatting ───────────────────────────────────────────────────────────

export function formatDate(isoString: string | null | undefined): string {
  if (!isoString) return "—";
  const date = new Date(isoString);
  return date.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${mins}m ${secs}s`;
}

// ── Contract Type Labels ──────────────────────────────────────────────────────

export const CONTRACT_TYPE_LABELS: Record<string, string> = {
  NDA: "Non-Disclosure Agreement",
  EMPLOYMENT: "Employment Contract",
  SAAS: "SaaS Agreement",
  LEASE: "Lease Agreement",
  SERVICE: "Service Agreement",
  UNKNOWN: "Unknown Contract Type",
};

export function getContractTypeLabel(type: string): string {
  return CONTRACT_TYPE_LABELS[type] ?? type;
}

// ── File Helpers ──────────────────────────────────────────────────────────────

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// Re-export CLAUSE_TYPE_LABELS here so components can import from a single utils file.
// Types/index.ts is the source of truth; this re-export prevents double-maintenance.
export const CLAUSE_TYPE_LABELS: Record<string, string> = {
  CONFIDENTIALITY: "Confidentiality",
  NON_COMPETE: "Non-Compete",
  NON_SOLICITATION: "Non-Solicitation",
  IP_ASSIGNMENT: "IP Assignment",
  INDEMNIFICATION: "Indemnification",
  LIMITATION_OF_LIABILITY: "Limitation of Liability",
  TERMINATION_FOR_CAUSE: "Termination for Cause",
  TERMINATION_FOR_CONVENIENCE: "Termination for Convenience",
  AUTO_RENEWAL: "Auto-Renewal",
  PAYMENT_TERMS: "Payment Terms",
  LATE_PAYMENT_PENALTY: "Late Payment Penalty",
  GOVERNING_LAW: "Governing Law",
  DISPUTE_RESOLUTION: "Dispute Resolution",
  FORCE_MAJEURE: "Force Majeure",
  DATA_PROTECTION: "Data Protection",
  EXCLUSIVITY: "Exclusivity",
  ASSIGNMENT: "Assignment",
  AMENDMENT: "Amendment",
  ENTIRE_AGREEMENT: "Entire Agreement",
  WAIVER: "Waiver",
  SEVERABILITY: "Severability",
  NOTICE: "Notice",
  WARRANTY_DISCLAIMER: "Warranty Disclaimer",
  REPRESENTATIONS: "Representations",
  WORK_PRODUCT: "Work Product",
  AUDIT_RIGHTS: "Audit Rights",
  MOST_FAVORED_NATION: "Most Favored Nation",
  LIQUIDATED_DAMAGES: "Liquidated Damages",
  SURVIVAL: "Survival",
  DEFINITIONS: "Definitions",
};

export const ACCEPTED_FILE_TYPES = {
  "application/pdf": [".pdf"],
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
  "text/plain": [".txt"],
};

export const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

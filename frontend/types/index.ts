/**
 * ClauseGuard Frontend Types
 * ============================
 * These types exactly mirror the Pydantic schemas in backend/schemas/analysis.py.
 * Any change to Pydantic schemas MUST be reflected here.
 *
 * Validated at runtime against the API response using Zod in lib/api.ts.
 */

export type ContractType =
  | "NDA"
  | "EMPLOYMENT"
  | "SAAS"
  | "LEASE"
  | "SERVICE"
  | "UNKNOWN";

export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export type DisadvantagedParty = "USER" | "COUNTERPARTY" | "NEITHER" | "BOTH";

export type ChatConfidence = "HIGH" | "MEDIUM" | "LOW" | "NOT_IN_DOCUMENT";

export type ContractStatus = "PENDING" | "PROCESSING" | "COMPLETE" | "FAILED";

// ── Stage 0 ──────────────────────────────────────────────────────────────────

export interface ContractTypeResult {
  contract_type: ContractType;
  confidence: number;
  reasoning: string;
  jurisdiction_hint: string | null;
}

// ── Stage 2 ──────────────────────────────────────────────────────────────────

export interface LegalChunk {
  chunk_id: string;
  text: string;
  context_header: string;
  page_range: [number, number];
  section_heading: string;
  chunk_index: number;
  token_count: number;
}

// ── Stage 3 ──────────────────────────────────────────────────────────────────

export interface ClauseExtractionResult {
  clause_type: string;
  relevant_text: string;
  confidence: number;
  chunk_id: string;
  low_confidence: boolean;
}

// ── Stage 4 ──────────────────────────────────────────────────────────────────

export interface RiskAssessment {
  clause_id: string;
  clause_type: string;
  risk_level: RiskLevel;
  risk_score: number;
  disadvantaged_party: DisadvantagedParty;
  plain_english_summary: string;
  why_it_matters: string;
  rubric_scores: Record<string, number>;
  confidence: number;
  source_text: string;
}

// ── Stage 5 ──────────────────────────────────────────────────────────────────

export interface AlternativeClause {
  original_clause_text: string;
  replacement_clause_text: string;
  what_changed: string;
  negotiation_points: [string, string, string];
  protection_improved: string;
}

// ── Stage 6 ──────────────────────────────────────────────────────────────────

export type MissingClauseSeverity = "RECOMMENDED" | "IMPORTANT" | "CRITICAL";

export interface MissingClause {
  clause_type: string;
  severity: MissingClauseSeverity;
  why_it_matters: string;
  example_language: string;
}

// ── Full Result ───────────────────────────────────────────────────────────────

export interface FullAnalysisResult {
  contract_id: string;
  contract_type: ContractTypeResult;
  extracted_clauses: ClauseExtractionResult[];
  risk_assessments: RiskAssessment[];
  alternatives: AlternativeClause[];
  missing_clauses: MissingClause[];
  overall_risk_score: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  total_clauses_found: number;
  analysis_duration_seconds: number;
  pipeline_version: string;
  analyzed_at: string;
}

// ── Chat ──────────────────────────────────────────────────────────────────────

export interface Citation {
  chunk_id: string;
  page_range: [number, number];
  relevant_excerpt: string;
  section_heading?: string;
}

export interface ChatResponse {
  answer: string;
  citations: Citation[];
  confidence: ChatConfidence;
  tokens_used?: number;
}

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  confidence?: ChatConfidence;
  id?: string;
  created_at?: string;
}

// ── API Responses ─────────────────────────────────────────────────────────────

export interface ContractUploadResponse {
  contract_id: string;
  filename: string;
  status: string;
  message: string;
}

export interface ContractStatusResponse {
  contract_id: string;
  status: ContractStatus;
  progress_pct: number;
  current_stage?: string;
  error_message?: string;
}

export interface ContractListItem {
  contract_id: string;
  filename: string;
  analyzed_at: string | null;
  overall_risk_score: number | null;
  contract_type: ContractType | null;
  status: ContractStatus;
  critical_count: number;
  high_count: number;
}

// ── UI Helpers ────────────────────────────────────────────────────────────────

export const RISK_LEVEL_ORDER: Record<RiskLevel, number> = {
  CRITICAL: 4,
  HIGH: 3,
  MEDIUM: 2,
  LOW: 1,
};

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

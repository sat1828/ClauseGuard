"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, FileText, AlertCircle, Lightbulb } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { RiskBadge } from "./RiskBadge";
import { AlternativeClauseView } from "./AlternativeClause";
import { cn, CLAUSE_TYPE_LABELS } from "@/lib/utils";
import { useContractStore } from "@/lib/store";
import type { RiskAssessment, AlternativeClause } from "@/types";

interface ClauseCardProps {
  assessment: RiskAssessment;
  alternative?: AlternativeClause;
  onShowInDocument?: (page: number) => void;
}

export function ClauseCard({ assessment, alternative, onShowInDocument }: ClauseCardProps) {
  const [isExpanded, setIsExpanded] = useState(
    // Auto-expand CRITICAL clauses
    assessment.risk_level === "CRITICAL",
  );
  const setHighlightedClause = useContractStore((s) => s.setHighlightedClause);

  const clauseLabel =
    CLAUSE_TYPE_LABELS[assessment.clause_type] ?? assessment.clause_type;

  function handleShowInDocument() {
    setHighlightedClause(assessment);
    // Page number comes from the source chunk — approximated here
    onShowInDocument?.(1);
  }

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "rounded-xl border bg-white shadow-sm overflow-hidden transition-all",
        assessment.risk_level === "CRITICAL" && "border-red-300 ring-1 ring-red-200",
        assessment.risk_level === "HIGH" && "border-orange-200",
        assessment.risk_level === "MEDIUM" && "border-amber-200",
        assessment.risk_level === "LOW" && "border-gray-200",
      )}
    >
      {/* ── Collapsed Header ─────────────────────────────────────── */}
      <button
        onClick={() => setIsExpanded((v) => !v)}
        className="w-full flex items-center justify-between p-4 hover:bg-gray-50 transition-colors text-left"
        aria-expanded={isExpanded}
      >
        <div className="flex items-center gap-3 min-w-0">
          <RiskBadge level={assessment.risk_level} />
          <div className="min-w-0">
            <p className="font-semibold text-gray-900 text-sm truncate">
              {clauseLabel}
            </p>
            {!isExpanded && (
              <p className="text-xs text-gray-500 mt-0.5 truncate max-w-md">
                {assessment.plain_english_summary.split(".")[0]}.
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0 ml-2">
          <span className="text-xs text-gray-400 font-mono">
            Risk {assessment.risk_score}/10
          </span>
          {isExpanded ? (
            <ChevronUp className="h-4 w-4 text-gray-400" />
          ) : (
            <ChevronDown className="h-4 w-4 text-gray-400" />
          )}
        </div>
      </button>

      {/* ── Expanded Content ──────────────────────────────────────── */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <div className="px-4 pb-4 space-y-4 border-t border-gray-100">
              {/* Original clause text */}
              <div className="mt-4">
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
                  Contract Language
                </p>
                <div className="bg-gray-50 rounded-lg p-3 font-mono text-xs text-gray-700 max-h-32 overflow-y-auto border border-gray-200 leading-relaxed">
                  {assessment.source_text}
                </div>
              </div>

              {/* Plain English explanation */}
              <div className="flex gap-2">
                <AlertCircle className="h-4 w-4 text-gray-400 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">
                    What This Means
                  </p>
                  <p className="text-sm text-gray-700 leading-relaxed">
                    {assessment.plain_english_summary}
                  </p>
                </div>
              </div>

              {/* Why it matters */}
              <div className="flex gap-2">
                <Lightbulb className="h-4 w-4 text-amber-500 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">
                    Why It Matters
                  </p>
                  <p className="text-sm text-gray-700 leading-relaxed">
                    {assessment.why_it_matters}
                  </p>
                </div>
              </div>

              {/* Show in document button */}
              <button
                onClick={handleShowInDocument}
                className="flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-700 font-medium"
              >
                <FileText className="h-3.5 w-3.5" />
                Show in document
              </button>

              {/* Alternative clause (HIGH/CRITICAL only) */}
              {alternative &&
                (assessment.risk_level === "HIGH" ||
                  assessment.risk_level === "CRITICAL") && (
                  <AlternativeClauseView
                    alternative={alternative}
                    riskLevel={assessment.risk_level}
                  />
                )}

              {/* Talking points only for MEDIUM */}
              {alternative && assessment.risk_level === "MEDIUM" && (
                <div className="bg-blue-50 rounded-lg p-3 border border-blue-200">
                  <p className="text-xs font-semibold text-blue-800 mb-2">
                    💬 Negotiation Talking Points
                  </p>
                  <ul className="space-y-1.5">
                    {alternative.negotiation_points.map((point, i) => (
                      <li key={i} className="text-xs text-blue-700 flex gap-2">
                        <span className="font-bold flex-shrink-0">{i + 1}.</span>
                        <span>{point}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

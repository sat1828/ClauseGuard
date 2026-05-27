"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, MessageSquare, RefreshCw } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { RiskDashboard } from "@/components/analysis/RiskDashboard";
import { ClauseCard } from "@/components/analysis/ClauseCard";
import { MissingClauseAlert } from "@/components/analysis/MissingClauseAlert";
import { getAnalysis } from "@/lib/api";
import { useContractStore } from "@/lib/store";
import type { FullAnalysisResult, RiskAssessment } from "@/types";

export default function AnalysisPage() {
  const { contractId } = useParams<{ contractId: string }>();
  const router = useRouter();
  const [analysis, setAnalysis] = useState<FullAnalysisResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"clauses" | "missing">("clauses");
  const [filterLevel, setFilterLevel] = useState<string>("ALL");

  const setStoreAnalysis = useContractStore((s) => s.setAnalysis);

  useEffect(() => {
    if (!contractId) return;
    loadAnalysis();
  }, [contractId]);

  async function loadAnalysis() {
    try {
      setLoading(true);
      const result = await getAnalysis(contractId);
      setAnalysis(result);
      setStoreAnalysis(result);
    } catch (e: any) {
      if (e?.status === 202) {
        // Still processing — redirect back to dashboard
        router.push("/dashboard");
      } else {
        setError(e?.detail ?? "Could not load analysis.");
      }
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center space-y-3">
          <RefreshCw className="h-8 w-8 text-blue-500 animate-spin mx-auto" />
          <p className="text-gray-500 text-sm">Loading analysis…</p>
        </div>
      </div>
    );
  }

  if (error || !analysis) {
    return (
      <div className="text-center py-20 space-y-4">
        <p className="text-red-600">{error ?? "Analysis not found."}</p>
        <Link href="/dashboard" className="text-blue-600 text-sm underline">
          ← Back to dashboard
        </Link>
      </div>
    );
  }

  // Build alternative map: clause_type → AlternativeClause
  const alternativeMap = new Map(
    analysis.alternatives.map((alt) => {
      const matching = analysis.risk_assessments.find(
        (r) => r.source_text === alt.original_clause_text,
      );
      return [matching?.clause_type ?? "", alt];
    }),
  );

  const filteredAssessments =
    filterLevel === "ALL"
      ? analysis.risk_assessments
      : analysis.risk_assessments.filter((r) => r.risk_level === filterLevel);

  const FILTER_LEVELS = ["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW"];

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/dashboard"
            className="p-2 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-700 transition-colors"
          >
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <div>
            <h1 className="text-xl font-black text-gray-900">Contract Analysis</h1>
            <p className="text-xs text-gray-400">
              {analysis.contract_type.contract_type} ·{" "}
              {analysis.contract_type.jurisdiction_hint ?? "Unknown jurisdiction"}
            </p>
          </div>
        </div>
        <Link
          href={`/dashboard/${contractId}/chat`}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold px-4 py-2 rounded-xl transition-colors"
        >
          <MessageSquare className="h-4 w-4" />
          Ask questions
        </Link>
      </div>

      {/* Risk Dashboard */}
      <RiskDashboard analysis={analysis} />

      {/* Tabs */}
      <div className="flex items-center gap-1 border-b border-gray-200">
        {[
          { id: "clauses", label: `Risk Clauses (${analysis.risk_assessments.length})` },
          {
            id: "missing",
            label: `Missing Protections (${analysis.missing_clauses.length})`,
          },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={`px-4 py-2.5 text-sm font-semibold border-b-2 transition-colors ${
              activeTab === tab.id
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-800"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Clauses tab */}
      {activeTab === "clauses" && (
        <div className="space-y-4">
          {/* Filter */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-gray-500 font-medium">Filter:</span>
            {FILTER_LEVELS.map((level) => (
              <button
                key={level}
                onClick={() => setFilterLevel(level)}
                className={`text-xs px-3 py-1.5 rounded-full font-medium transition-colors border ${
                  filterLevel === level
                    ? "bg-gray-800 text-white border-gray-800"
                    : "bg-white text-gray-600 border-gray-200 hover:border-gray-400"
                }`}
              >
                {level === "ALL"
                  ? `All (${analysis.risk_assessments.length})`
                  : `${level} (${analysis.risk_assessments.filter((r) => r.risk_level === level).length})`}
              </button>
            ))}
          </div>

          {/* Clause cards */}
          <AnimatePresence mode="popLayout">
            {filteredAssessments.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-8">
                No {filterLevel.toLowerCase()} risk clauses found.
              </p>
            ) : (
              <div className="space-y-3">
                {filteredAssessments.map((assessment) => (
                  <ClauseCard
                    key={assessment.clause_id}
                    assessment={assessment}
                    alternative={alternativeMap.get(assessment.clause_type)}
                  />
                ))}
              </div>
            )}
          </AnimatePresence>
        </div>
      )}

      {/* Missing clauses tab */}
      {activeTab === "missing" && (
        <div className="space-y-3">
          {analysis.missing_clauses.length === 0 ? (
            <div className="text-center py-12 space-y-2">
              <p className="text-2xl">✅</p>
              <p className="text-gray-600 font-medium">No missing required clauses detected</p>
              <p className="text-sm text-gray-400">
                This contract contains all standard required clauses for its type.
              </p>
            </div>
          ) : (
            <>
              <p className="text-sm text-gray-500">
                The following protections are absent from this contract and should be
                added before signing.
              </p>
              {analysis.missing_clauses.map((clause) => (
                <MissingClauseAlert
                  key={clause.clause_type}
                  missing={clause}
                />
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}

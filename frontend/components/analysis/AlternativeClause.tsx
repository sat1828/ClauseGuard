"use client";

import { useState } from "react";
import { Copy, CheckCheck, ShieldCheck } from "lucide-react";
import type { AlternativeClause, RiskLevel } from "@/types";
import { cn } from "@/lib/utils";

interface AlternativeClauseViewProps {
  alternative: AlternativeClause;
  riskLevel: RiskLevel;
}

export function AlternativeClauseView({ alternative, riskLevel }: AlternativeClauseViewProps) {
  const [copied, setCopied] = useState(false);

  if (!alternative.replacement_clause_text) return null;

  async function copyReplacement() {
    await navigator.clipboard.writeText(alternative.replacement_clause_text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div
      className={cn(
        "rounded-lg border p-4 space-y-3",
        riskLevel === "CRITICAL"
          ? "bg-emerald-50 border-emerald-200"
          : "bg-emerald-50 border-emerald-200",
      )}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-emerald-600" />
          <p className="text-xs font-semibold text-emerald-800 uppercase tracking-wider">
            Safer Alternative Clause
          </p>
        </div>
        <button
          onClick={copyReplacement}
          className="flex items-center gap-1 text-xs text-emerald-700 hover:text-emerald-900 font-medium transition-colors"
          title="Copy replacement clause"
        >
          {copied ? (
            <><CheckCheck className="h-3.5 w-3.5" /> Copied</>
          ) : (
            <><Copy className="h-3.5 w-3.5" /> Copy</>
          )}
        </button>
      </div>

      <div className="bg-white rounded border border-emerald-200 p-3 font-mono text-xs text-gray-700 max-h-32 overflow-y-auto leading-relaxed">
        {alternative.replacement_clause_text}
      </div>

      <div>
        <p className="text-xs font-semibold text-emerald-800 mb-1">What Changed</p>
        <p className="text-xs text-emerald-700">{alternative.what_changed}</p>
      </div>

      <div>
        <p className="text-xs font-semibold text-emerald-800 mb-2">How to Ask for This</p>
        <ul className="space-y-1.5">
          {alternative.negotiation_points.map((point, i) => (
            <li key={i} className="flex gap-2 text-xs text-emerald-700">
              <span className="font-bold flex-shrink-0 text-emerald-600">{i + 1}.</span>
              <span className="italic">"{point}"</span>
            </li>
          ))}
        </ul>
      </div>

      <p className="text-xs text-emerald-600 font-medium">
        ✓ {alternative.protection_improved}
      </p>
    </div>
  );
}

"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import { AlertTriangle, Clock, Globe, Shield, TrendingUp } from "lucide-react";
import { cn, formatDuration, getContractTypeLabel } from "@/lib/utils";
import type { FullAnalysisResult } from "@/types";

interface RiskDashboardProps {
  analysis: FullAnalysisResult;
}

/** Animated count-up hook */
function useCountUp(target: number, duration = 1200) {
  const [value, setValue] = useState(0);
  useEffect(() => {
    let start = 0;
    const steps = 40;
    const increment = target / steps;
    const interval = duration / steps;
    const timer = setInterval(() => {
      start += increment;
      if (start >= target) {
        setValue(target);
        clearInterval(timer);
      } else {
        setValue(Math.round(start * 10) / 10);
      }
    }, interval);
    return () => clearInterval(timer);
  }, [target, duration]);
  return value;
}

const CHART_COLORS = {
  CRITICAL: "#ef4444",
  HIGH: "#f97316",
  MEDIUM: "#f59e0b",
  LOW: "#10b981",
};

const RISK_SCORE_BG = (score: number) => {
  if (score <= 3) return "text-emerald-600";
  if (score <= 5) return "text-amber-500";
  if (score <= 7) return "text-orange-500";
  return "text-red-600";
};

export function RiskDashboard({ analysis }: RiskDashboardProps) {
  const animatedScore = useCountUp(analysis.overall_risk_score);
  const animatedCritical = useCountUp(analysis.critical_count, 800);
  const animatedHigh = useCountUp(analysis.high_count, 800);
  const animatedMedium = useCountUp(analysis.medium_count, 800);
  const animatedLow = useCountUp(analysis.low_count, 800);

  const chartData = [
    { name: "Critical", value: analysis.critical_count, color: CHART_COLORS.CRITICAL },
    { name: "High", value: analysis.high_count, color: CHART_COLORS.HIGH },
    { name: "Medium", value: analysis.medium_count, color: CHART_COLORS.MEDIUM },
    { name: "Low", value: analysis.low_count, color: CHART_COLORS.LOW },
  ].filter((d) => d.value > 0);

  const contractTypeLabel = getContractTypeLabel(analysis.contract_type.contract_type);

  return (
    <div className="space-y-4">
      {/* Top row: Score + breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Overall Score */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="md:col-span-1 bg-white rounded-xl border border-gray-200 p-6 flex flex-col items-center justify-center shadow-sm"
        >
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
            Overall Risk Score
          </p>
          <motion.span
            className={cn(
              "text-6xl font-black tabular-nums",
              RISK_SCORE_BG(analysis.overall_risk_score),
            )}
          >
            {animatedScore.toFixed(1)}
          </motion.span>
          <span className="text-gray-400 text-sm font-medium mt-1">/ 10</span>

          <div className="mt-4 w-full bg-gray-100 rounded-full h-2">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${(analysis.overall_risk_score / 10) * 100}%` }}
              transition={{ duration: 1.2, ease: "easeOut" }}
              className={cn(
                "h-2 rounded-full",
                analysis.overall_risk_score <= 3 && "bg-emerald-500",
                analysis.overall_risk_score > 3 && analysis.overall_risk_score <= 5 && "bg-amber-500",
                analysis.overall_risk_score > 5 && analysis.overall_risk_score <= 7 && "bg-orange-500",
                analysis.overall_risk_score > 7 && "bg-red-500",
              )}
            />
          </div>

          {/* Contract type badge */}
          <div className="mt-4 flex items-center gap-1.5">
            <Globe className="h-3.5 w-3.5 text-gray-400" />
            <span className="text-xs text-gray-600 font-medium">{contractTypeLabel}</span>
            {analysis.contract_type.jurisdiction_hint && (
              <span className="text-xs text-gray-400">
                · {analysis.contract_type.jurisdiction_hint}
              </span>
            )}
          </div>
        </motion.div>

        {/* Risk count cards */}
        <div className="md:col-span-2 grid grid-cols-2 gap-3">
          {[
            {
              label: "Critical",
              count: animatedCritical,
              real: analysis.critical_count,
              bg: "bg-red-50 border-red-200",
              text: "text-red-700",
              icon: <AlertTriangle className="h-4 w-4 text-red-500" />,
            },
            {
              label: "High Risk",
              count: animatedHigh,
              real: analysis.high_count,
              bg: "bg-orange-50 border-orange-200",
              text: "text-orange-700",
              icon: <TrendingUp className="h-4 w-4 text-orange-500" />,
            },
            {
              label: "Medium Risk",
              count: animatedMedium,
              real: analysis.medium_count,
              bg: "bg-amber-50 border-amber-200",
              text: "text-amber-700",
              icon: <Shield className="h-4 w-4 text-amber-500" />,
            },
            {
              label: "Low Risk",
              count: animatedLow,
              real: analysis.low_count,
              bg: "bg-emerald-50 border-emerald-200",
              text: "text-emerald-700",
              icon: <Shield className="h-4 w-4 text-emerald-500" />,
            },
          ].map((item) => (
            <motion.div
              key={item.label}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className={cn(
                "rounded-xl border p-4 flex items-center gap-3 shadow-sm",
                item.bg,
              )}
            >
              {item.icon}
              <div>
                <p className={cn("text-2xl font-black tabular-nums", item.text)}>
                  {Math.round(item.count)}
                </p>
                <p className="text-xs text-gray-500 font-medium">{item.label}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Second row: Donut chart + meta */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Donut chart */}
        {chartData.length > 0 && (
          <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
              Risk Distribution
            </p>
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie
                  data={chartData}
                  cx="50%"
                  cy="50%"
                  innerRadius={45}
                  outerRadius={75}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {chartData.map((entry) => (
                    <Cell key={entry.name} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value: number, name: string) => [
                    `${value} clause${value !== 1 ? "s" : ""}`,
                    name,
                  ]}
                />
                <Legend
                  iconType="circle"
                  iconSize={8}
                  formatter={(value) => (
                    <span className="text-xs text-gray-600">{value}</span>
                  )}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Meta info */}
        <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm space-y-3">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
            Analysis Details
          </p>

          <div className="space-y-2.5">
            <Row label="Clauses Identified" value={`${analysis.total_clauses_found}`} />
            <Row label="Missing Protections" value={`${analysis.missing_clauses.length}`}
              valueClass={analysis.missing_clauses.length > 0 ? "text-red-600 font-semibold" : ""}
            />
            <Row label="Alternatives Generated" value={`${analysis.alternatives.length}`} />
            <Row label="Analysis Time" value={formatDuration(analysis.analysis_duration_seconds)} />
            <Row label="Pipeline Version" value={`v${analysis.pipeline_version}`} />
            <Row label="Confidence" value={`${Math.round(analysis.contract_type.confidence * 100)}%`} />
          </div>

          {analysis.missing_clauses.length > 0 && (
            <div className="mt-3 flex items-start gap-2 bg-red-50 rounded-lg p-2.5 border border-red-200">
              <AlertTriangle className="h-3.5 w-3.5 text-red-500 flex-shrink-0 mt-0.5" />
              <p className="text-xs text-red-700">
                <strong>{analysis.missing_clauses.filter(m => m.severity === "CRITICAL").length} critical</strong> protections absent from this contract.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Row({
  label,
  value,
  valueClass = "",
}: {
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-gray-500">{label}</span>
      <span className={cn("font-medium text-gray-800", valueClass)}>{value}</span>
    </div>
  );
}

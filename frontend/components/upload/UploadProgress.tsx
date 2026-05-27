"use client";

import { motion } from "framer-motion";
import { CheckCircle2, Loader2, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";

const STAGES = [
  { pct: 10, label: "Parsing document" },
  { pct: 20, label: "Identifying contract type" },
  { pct: 30, label: "Chunking clauses" },
  { pct: 45, label: "Building search index" },
  { pct: 60, label: "Extracting clauses" },
  { pct: 75, label: "Scoring risks" },
  { pct: 85, label: "Generating alternatives" },
  { pct: 90, label: "Checking for missing clauses" },
  { pct: 100, label: "Finalising analysis" },
];

interface UploadProgressProps {
  stage: string;
  progress: number;
  status: string;
}

export function UploadProgress({ stage, progress, status }: UploadProgressProps) {
  const isFailed = status === "FAILED";

  return (
    <div className="space-y-4">
      {/* Progress bar */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-sm">
          <span className="font-medium text-gray-700">
            {isFailed ? "Analysis failed" : stage || "Starting analysis…"}
          </span>
          <span className="text-gray-400 tabular-nums">{progress}%</span>
        </div>
        <div className="w-full bg-gray-100 rounded-full h-2 overflow-hidden">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.5, ease: "easeInOut" }}
            className={cn(
              "h-2 rounded-full",
              isFailed ? "bg-red-500" : "bg-blue-500",
            )}
          />
        </div>
      </div>

      {/* Stage checklist */}
      <div className="space-y-1.5">
        {STAGES.map((s) => {
          const isDone = progress > s.pct;
          const isCurrent = !isDone && progress >= s.pct - 15;

          return (
            <div key={s.label} className="flex items-center gap-2.5">
              {isDone ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-500 flex-shrink-0" />
              ) : isCurrent ? (
                <Loader2 className="h-4 w-4 text-blue-500 animate-spin flex-shrink-0" />
              ) : (
                <div className="h-4 w-4 rounded-full border-2 border-gray-200 flex-shrink-0" />
              )}
              <span
                className={cn(
                  "text-sm",
                  isDone
                    ? "text-gray-500 line-through"
                    : isCurrent
                    ? "text-gray-800 font-medium"
                    : "text-gray-400",
                )}
              >
                {s.label}
              </span>
            </div>
          );
        })}
      </div>

      {isFailed && (
        <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-3">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          Analysis failed. Please try uploading the contract again.
        </div>
      )}
    </div>
  );
}

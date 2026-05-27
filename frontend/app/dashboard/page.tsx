"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { FileText, Clock, AlertTriangle, ChevronRight, Trash2 } from "lucide-react";
import { DropZone } from "@/components/upload/DropZone";
import { UploadProgress } from "@/components/upload/UploadProgress";
import { RiskBadge } from "@/components/analysis/RiskBadge";
import { useContractStore } from "@/lib/store";
import {
  uploadContract,
  listContracts,
  getContractStatus,
  deleteContract,
} from "@/lib/api";
import { cn, formatDate, getContractTypeLabel } from "@/lib/utils";
import type { ContractListItem, RiskLevel } from "@/types";

const RISK_LEVEL_FOR_SCORE = (score: number | null): RiskLevel => {
  if (!score) return "LOW";
  if (score >= 7) return "CRITICAL";
  if (score >= 5) return "HIGH";
  if (score >= 3) return "MEDIUM";
  return "LOW";
};

export default function DashboardPage() {
  const router = useRouter();
  const [contracts, setContracts] = useState<ContractListItem[]>([]);
  const [currentContractId, setCurrentContractId] = useState<string | null>(null);
  const [processingStatus, setProcessingStatus] = useState<string>("");
  const [processingProgress, setProcessingProgress] = useState(0);
  const [isPolling, setIsPolling] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const { isUploading, setIsUploading, setUploadProgress } = useContractStore();

  // Load contract list on mount
  useEffect(() => {
    loadContracts();
  }, []);

  async function loadContracts() {
    try {
      const list = await listContracts();
      setContracts(list);
    } catch (e) {
      setLoadError("Could not connect to the backend. Make sure the server is running.");
    }
  }

  const pollStatus = useCallback(
    async (contractId: string) => {
      setIsPolling(true);
      const interval = setInterval(async () => {
        try {
          const status = await getContractStatus(contractId);
          setProcessingStatus(status.current_stage ?? "Processing…");
          setProcessingProgress(status.progress_pct);

          if (status.status === "COMPLETE") {
            clearInterval(interval);
            setIsPolling(false);
            setIsUploading(false);
            await loadContracts();
            router.push(`/dashboard/${contractId}`);
          } else if (status.status === "FAILED") {
            clearInterval(interval);
            setIsPolling(false);
            setIsUploading(false);
            setProcessingStatus("Analysis failed");
            await loadContracts();
          }
        } catch {
          clearInterval(interval);
          setIsPolling(false);
        }
      }, 2000); // Poll every 2 seconds
    },
    [router, setIsUploading],
  );

  async function handleFileAccepted(file: File) {
    setIsUploading(true);
    setLoadError(null);
    setProcessingProgress(0);
    setProcessingStatus("Uploading file…");

    try {
      const response = await uploadContract(file, (pct) => {
        setUploadProgress(pct);
        setProcessingStatus(`Uploading… ${pct}%`);
      });

      setCurrentContractId(response.contract_id);
      setProcessingStatus("Queued for analysis…");
      pollStatus(response.contract_id);
    } catch (e: any) {
      setIsUploading(false);
      setLoadError(e?.detail ?? e?.message ?? "Upload failed. Please try again.");
    }
  }

  async function handleDelete(contractId: string, e: React.MouseEvent) {
    e.stopPropagation();
    if (!confirm("Delete this contract and all its analysis data?")) return;
    try {
      await deleteContract(contractId);
      setContracts((prev) => prev.filter((c) => c.contract_id !== contractId));
    } catch {
      alert("Could not delete contract. Please try again.");
    }
  }

  return (
    <div className="space-y-8 max-w-4xl mx-auto">
      {/* Upload section */}
      <section>
        <h1 className="text-2xl font-black text-gray-900 mb-1">Analyse a Contract</h1>
        <p className="text-sm text-gray-500 mb-6">
          Upload any legal document — NDA, employment contract, SaaS agreement, lease.
          Full AI analysis in under 60 seconds.
        </p>

        {isUploading || isPolling ? (
          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
            <UploadProgress
              stage={processingStatus}
              progress={processingProgress}
              status={processingProgress === 0 && processingStatus.includes("fail") ? "FAILED" : "PROCESSING"}
            />
          </div>
        ) : (
          <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
            <DropZone onFileAccepted={handleFileAccepted} disabled={isUploading} />
          </div>
        )}

        {loadError && (
          <div className="mt-3 flex items-center gap-2 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-3">
            <AlertTriangle className="h-4 w-4 flex-shrink-0" />
            {loadError}
          </div>
        )}
      </section>

      {/* Contract history */}
      {contracts.length > 0 && (
        <section>
          <h2 className="text-lg font-bold text-gray-800 mb-4">Recent Contracts</h2>
          <div className="space-y-2">
            <AnimatePresence>
              {contracts.map((contract) => (
                <motion.div
                  key={contract.contract_id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  layout
                  onClick={() => {
                    if (contract.status === "COMPLETE") {
                      router.push(`/dashboard/${contract.contract_id}`);
                    }
                  }}
                  className={cn(
                    "bg-white rounded-xl border border-gray-200 p-4 flex items-center gap-4 shadow-sm transition-all",
                    contract.status === "COMPLETE"
                      ? "cursor-pointer hover:border-blue-300 hover:shadow-md"
                      : "cursor-default",
                  )}
                >
                  <FileText className="h-8 w-8 text-gray-300 flex-shrink-0" />

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="font-semibold text-gray-900 truncate text-sm">
                        {contract.filename}
                      </p>
                      {contract.contract_type && (
                        <span className="text-xs text-gray-500 bg-gray-100 rounded px-2 py-0.5">
                          {getContractTypeLabel(contract.contract_type)}
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-3 mt-1">
                      {contract.status === "COMPLETE" && contract.overall_risk_score != null ? (
                        <>
                          <RiskBadge
                            level={RISK_LEVEL_FOR_SCORE(contract.overall_risk_score)}
                            showDot={false}
                          />
                          <span className="text-xs text-gray-400">
                            Score: {contract.overall_risk_score.toFixed(1)}/10
                          </span>
                          {contract.critical_count > 0 && (
                            <span className="text-xs text-red-600 font-semibold">
                              {contract.critical_count} critical
                            </span>
                          )}
                        </>
                      ) : (
                        <span
                          className={cn(
                            "text-xs font-medium",
                            contract.status === "FAILED"
                              ? "text-red-500"
                              : "text-blue-500",
                          )}
                        >
                          {contract.status === "FAILED" ? "Analysis failed" : "Processing…"}
                        </span>
                      )}
                      <span className="text-xs text-gray-400 flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {formatDate(contract.analyzed_at)}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 flex-shrink-0">
                    <button
                      onClick={(e) => handleDelete(contract.contract_id, e)}
                      className="p-1.5 rounded-lg hover:bg-red-50 text-gray-400 hover:text-red-500 transition-colors"
                      title="Delete contract"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                    {contract.status === "COMPLETE" && (
                      <ChevronRight className="h-4 w-4 text-gray-300" />
                    )}
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </section>
      )}
    </div>
  );
}

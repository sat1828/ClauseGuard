"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import {
  FileText, LayoutDashboard, Clock, AlertTriangle,
  Shield, ChevronRight,
} from "lucide-react";
import { cn, formatDate, getContractTypeLabel } from "@/lib/utils";
import { useContractStore } from "@/lib/store";
import { listContracts } from "@/lib/api";
import type { RiskLevel } from "@/types";

const SCORE_LEVEL = (score: number | null): RiskLevel => {
  if (!score) return "LOW";
  if (score >= 7) return "CRITICAL";
  if (score >= 5) return "HIGH";
  if (score >= 3) return "MEDIUM";
  return "LOW";
};

const LEVEL_DOT: Record<RiskLevel, string> = {
  CRITICAL: "bg-red-500",
  HIGH: "bg-orange-500",
  MEDIUM: "bg-amber-400",
  LOW: "bg-emerald-500",
};

interface SidebarProps {
  className?: string;
}

export function Sidebar({ className }: SidebarProps) {
  const pathname = usePathname();
  const { contractList, setContractList } = useContractStore();

  useEffect(() => {
    listContracts()
      .then(setContractList)
      .catch(() => {}); // Sidebar errors are non-fatal
  }, [setContractList]);

  return (
    <aside
      className={cn(
        "w-64 flex-shrink-0 bg-white border-r border-gray-200 flex flex-col h-full",
        className,
      )}
    >
      {/* Nav */}
      <nav className="p-3 border-b border-gray-100">
        <Link
          href="/dashboard"
          className={cn(
            "flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
            pathname === "/dashboard"
              ? "bg-blue-50 text-blue-700"
              : "text-gray-600 hover:bg-gray-50 hover:text-gray-900",
          )}
        >
          <LayoutDashboard className="h-4 w-4" />
          Dashboard
        </Link>
      </nav>

      {/* Contract history */}
      <div className="flex-1 overflow-y-auto p-3">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider px-2 mb-2">
          Recent Contracts
        </p>

        {contractList.length === 0 ? (
          <div className="px-2 py-6 text-center">
            <FileText className="h-8 w-8 text-gray-200 mx-auto mb-2" />
            <p className="text-xs text-gray-400">No contracts yet</p>
          </div>
        ) : (
          <div className="space-y-1">
            {contractList.slice(0, 15).map((contract) => {
              const isActive = pathname.includes(contract.contract_id);
              const riskLevel = SCORE_LEVEL(contract.overall_risk_score);

              return (
                <Link
                  key={contract.contract_id}
                  href={
                    contract.status === "COMPLETE"
                      ? `/dashboard/${contract.contract_id}`
                      : "/dashboard"
                  }
                  className={cn(
                    "flex items-center gap-2.5 px-2 py-2 rounded-lg text-sm transition-colors group",
                    isActive
                      ? "bg-blue-50 text-blue-700"
                      : "text-gray-600 hover:bg-gray-50 hover:text-gray-900",
                    contract.status !== "COMPLETE" && "opacity-60 cursor-default",
                  )}
                >
                  {/* Risk indicator dot */}
                  <span
                    className={cn(
                      "w-1.5 h-1.5 rounded-full flex-shrink-0",
                      contract.status === "COMPLETE"
                        ? LEVEL_DOT[riskLevel]
                        : "bg-gray-300",
                    )}
                  />

                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-medium leading-tight">
                      {contract.filename.replace(/\.[^.]+$/, "")}
                    </p>
                    {contract.contract_type && (
                      <p className="text-[10px] text-gray-400 truncate">
                        {getContractTypeLabel(contract.contract_type)}
                      </p>
                    )}
                  </div>

                  <ChevronRight
                    className={cn(
                      "h-3.5 w-3.5 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity",
                      isActive && "opacity-100",
                    )}
                  />
                </Link>
              );
            })}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-gray-100">
        <div className="flex items-center gap-1.5 text-[10px] text-gray-400">
          <Shield className="h-3 w-3" />
          <span>Not legal advice</span>
        </div>
      </div>
    </aside>
  );
}

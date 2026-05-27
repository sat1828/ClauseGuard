"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Shield, LayoutDashboard, Upload } from "lucide-react";
import { DisclaimerBanner } from "@/components/layout/DisclaimerBanner";
import { cn } from "@/lib/utils";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <DisclaimerBanner />

      <header className="bg-white border-b border-gray-200 sticky top-[36px] z-30">
        <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <Shield className="h-5 w-5 text-blue-600" />
            <span className="font-black text-gray-900 tracking-tight">ClauseGuard</span>
          </Link>
          <nav className="flex items-center gap-1">
            <Link
              href="/dashboard"
              className={cn(
                "flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg font-medium transition-colors",
                pathname === "/dashboard"
                  ? "bg-blue-50 text-blue-700"
                  : "text-gray-600 hover:text-gray-900 hover:bg-gray-100",
              )}
            >
              <LayoutDashboard className="h-4 w-4" />
              Dashboard
            </Link>
          </nav>
        </div>
      </header>

      <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-8">
        {children}
      </main>
    </div>
  );
}

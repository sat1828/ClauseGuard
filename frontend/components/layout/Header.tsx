"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Shield, ChevronRight, Home } from "lucide-react";

interface HeaderProps {
  contractFilename?: string;
}

export function Header({ contractFilename }: HeaderProps) {
  const pathname = usePathname();

  // Build breadcrumb trail from pathname
  const crumbs = buildCrumbs(pathname, contractFilename);

  return (
    <header className="bg-white border-b border-gray-200 sticky top-0 z-30 h-14 flex items-center px-6">
      <div className="flex items-center gap-4 flex-1">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-1.5 text-blue-600 flex-shrink-0">
          <Shield className="h-5 w-5" />
          <span className="font-black text-gray-900 text-sm">ClauseGuard</span>
        </Link>

        {/* Breadcrumbs */}
        {crumbs.length > 0 && (
          <nav className="flex items-center gap-1 text-sm" aria-label="Breadcrumb">
            {crumbs.map((crumb, i) => (
              <span key={crumb.href} className="flex items-center gap-1">
                {i > 0 && <ChevronRight className="h-3.5 w-3.5 text-gray-300" />}
                {i === crumbs.length - 1 ? (
                  <span className="text-gray-800 font-medium truncate max-w-[200px]">
                    {crumb.label}
                  </span>
                ) : (
                  <Link
                    href={crumb.href}
                    className="text-gray-500 hover:text-gray-800 transition-colors"
                  >
                    {crumb.label}
                  </Link>
                )}
              </span>
            ))}
          </nav>
        )}
      </div>

      {/* Right side: user menu placeholder */}
      <div className="flex items-center gap-3">
        <span className="text-xs text-gray-400 bg-amber-50 border border-amber-200 rounded px-2 py-1 text-amber-700 hidden sm:block">
          Not legal advice
        </span>
      </div>
    </header>
  );
}

interface Crumb {
  label: string;
  href: string;
}

function buildCrumbs(pathname: string, contractFilename?: string): Crumb[] {
  const crumbs: Crumb[] = [];
  const parts = pathname.split("/").filter(Boolean);

  if (parts.length === 0) return crumbs;

  if (parts[0] === "dashboard") {
    crumbs.push({ label: "Dashboard", href: "/dashboard" });
  }

  if (parts.length >= 2 && parts[0] === "dashboard") {
    const contractId = parts[1];
    crumbs.push({
      label: contractFilename
        ? contractFilename.replace(/\.[^.]+$/, "")
        : "Analysis",
      href: `/dashboard/${contractId}`,
    });
  }

  if (parts.length >= 3 && parts[2] === "chat") {
    crumbs.push({
      label: "Ask Questions",
      href: pathname,
    });
  }

  return crumbs;
}

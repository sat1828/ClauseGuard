"use client";

/**
 * DisclaimerBanner
 * =================
 * Fixed to the top of every analysis page. Non-dismissable by design.
 * This is a legal protection requirement — do not add a close button.
 */

import { AlertTriangle } from "lucide-react";

export function DisclaimerBanner() {
  return (
    <div
      className="w-full bg-amber-50 border-b border-amber-200 py-2 px-4 z-50 sticky top-0"
      role="alert"
      aria-live="polite"
    >
      <div className="max-w-7xl mx-auto flex items-start gap-2">
        <AlertTriangle
          className="h-4 w-4 text-amber-600 flex-shrink-0 mt-0.5"
          aria-hidden="true"
        />
        <p className="text-xs text-amber-800 leading-relaxed">
          <strong>Legal Disclaimer:</strong> ClauseGuard is not a law firm and
          does not provide legal advice. All analysis is for informational
          purposes only and does not constitute legal counsel or create an
          attorney-client relationship.{" "}
          <strong>
            Always consult a qualified legal professional before making
            decisions based on any contract.
          </strong>
        </p>
      </div>
    </div>
  );
}

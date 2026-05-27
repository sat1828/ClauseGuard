"use client";

import { BookOpen } from "lucide-react";
import type { Citation } from "@/types";

interface CitationChipProps {
  citation: Citation;
  onClick?: () => void;
}

export function CitationChip({ citation, onClick }: CitationChipProps) {
  const pageDisplay =
    citation.page_range[0] === citation.page_range[1]
      ? `p.${citation.page_range[0]}`
      : `pp.${citation.page_range[0]}–${citation.page_range[1]}`;

  return (
    <button
      onClick={onClick}
      title={citation.relevant_excerpt}
      className="inline-flex items-center gap-1 px-2 py-0.5 bg-white border border-gray-300 hover:border-blue-400 hover:bg-blue-50 rounded-full text-[10px] text-gray-600 hover:text-blue-700 transition-colors font-medium"
    >
      <BookOpen className="h-2.5 w-2.5 flex-shrink-0" />
      <span>
        {citation.section_heading
          ? `${citation.section_heading.slice(0, 20)} · ${pageDisplay}`
          : pageDisplay}
      </span>
    </button>
  );
}

"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, FileText } from "lucide-react";
import { ChatInterface } from "@/components/chat/ChatInterface";
import { getChatHistory } from "@/lib/api";
import { useContractStore } from "@/lib/store";

export default function ChatPage() {
  const { contractId } = useParams<{ contractId: string }>();
  const { chatHistory, addChatMessage } = useContractStore();
  const [loaded, setLoaded] = useState(false);

  // Restore persisted chat history on mount
  useEffect(() => {
    if (chatHistory.length > 0) {
      setLoaded(true);
      return;
    }
    getChatHistory(contractId)
      .then((data) => {
        if (data.messages.length > 0) {
          data.messages.forEach((msg) => addChatMessage(msg));
        }
      })
      .finally(() => setLoaded(true));
  }, [contractId]);

  return (
    <div className="flex flex-col h-[calc(100vh-120px)] max-w-4xl mx-auto space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3 flex-shrink-0">
        <Link
          href={`/dashboard/${contractId}`}
          className="p-2 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-700 transition-colors"
        >
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div className="flex items-center gap-2">
          <FileText className="h-5 w-5 text-blue-600" />
          <div>
            <h1 className="text-lg font-black text-gray-900">Ask Your Contract</h1>
            <p className="text-xs text-gray-400">
              Answers are grounded in your contract only · Not legal advice
            </p>
          </div>
        </div>
      </div>

      {/* Chat interface takes remaining height */}
      <div className="flex-1 min-h-0">
        {loaded && (
          <ChatInterface
            contractId={contractId}
            onCitationClick={(page) => {
              // TODO: integrate with PDF viewer for page navigation
              console.log("Navigate to page:", page);
            }}
          />
        )}
      </div>
    </div>
  );
}

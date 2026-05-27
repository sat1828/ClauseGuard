"use client";

import { useEffect, useRef, useState } from "react";
import { Send, Loader2, MessageSquare, ExternalLink } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { useContractStore } from "@/lib/store";
import { streamChatMessage, getSuggestedQuestions } from "@/lib/api";
import { CitationChip } from "./CitationChip";
import type { ChatTurn, Citation } from "@/types";

interface ChatInterfaceProps {
  contractId: string;
  onCitationClick?: (page: number, chunkId: string) => void;
}

export function ChatInterface({ contractId, onCitationClick }: ChatInterfaceProps) {
  const [input, setInput] = useState("");
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const {
    chatHistory,
    isChatStreaming,
    addChatMessage,
    updateLastAssistantMessage,
    setChatStreaming,
  } = useContractStore();

  useEffect(() => {
    getSuggestedQuestions(contractId)
      .then((d) => setSuggestions(d.questions))
      .catch(() => {});
  }, [contractId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory, isChatStreaming]);

  async function sendMessage(text: string) {
    const message = text.trim();
    if (!message || isChatStreaming) return;

    setInput("");
    setSuggestions([]); // Hide suggestions after first message

    // Add user message
    addChatMessage({ role: "user", content: message });

    // Add empty assistant message (will be filled by streaming)
    addChatMessage({ role: "assistant", content: "" });
    setChatStreaming(true);

    let streamedContent = "";

    await streamChatMessage(
      contractId,
      message,
      chatHistory.filter((m) => m.role === "user" || m.role === "assistant"),
      {
        onToken: (token) => {
          streamedContent += token;
          updateLastAssistantMessage(streamedContent);
        },
        onDone: (response) => {
          updateLastAssistantMessage(
            response.answer,
            true,
            response.citations,
            response.confidence,
          );
          setChatStreaming(false);
        },
        onError: (error) => {
          updateLastAssistantMessage(
            `Error: ${error}. Please try again.`,
            true,
            [],
            "LOW",
          );
          setChatStreaming(false);
        },
      },
    );
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  }

  return (
    <div className="flex flex-col h-full bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-100 bg-gray-50/50 flex-shrink-0">
        <MessageSquare className="h-4 w-4 text-blue-600" />
        <h3 className="text-sm font-semibold text-gray-800">Ask Your Contract</h3>
        <span className="ml-auto text-xs text-gray-400 bg-amber-50 border border-amber-200 rounded px-2 py-0.5 text-amber-700">
          Not legal advice
        </span>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-0">
        {chatHistory.length === 0 && (
          <div className="text-center py-8 space-y-3">
            <MessageSquare className="h-10 w-10 text-gray-200 mx-auto" />
            <p className="text-sm text-gray-400">
              Ask anything about this contract — what clauses mean, what risks exist, or
              what you can negotiate.
            </p>
            {suggestions.length > 0 && (
              <div className="mt-4 space-y-2">
                <p className="text-xs text-gray-400 font-medium">Try asking:</p>
                {suggestions.map((q, i) => (
                  <button
                    key={i}
                    onClick={() => sendMessage(q)}
                    className="block w-full text-left text-xs bg-blue-50 hover:bg-blue-100 border border-blue-200 text-blue-700 rounded-lg px-3 py-2 transition-colors"
                  >
                    {q}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        <AnimatePresence initial={false}>
          {chatHistory.map((msg, idx) => (
            <ChatMessageBubble
              key={idx}
              message={msg}
              onCitationClick={onCitationClick}
              isStreaming={
                isChatStreaming &&
                idx === chatHistory.length - 1 &&
                msg.role === "assistant"
              }
            />
          ))}
        </AnimatePresence>

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="flex-shrink-0 border-t border-gray-100 p-3">
        <div className="flex gap-2 items-end">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about this contract… (Enter to send)"
            rows={2}
            disabled={isChatStreaming}
            className="flex-1 resize-none rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-700 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed"
          />
          <button
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || isChatStreaming}
            className="flex-shrink-0 h-[62px] w-10 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:bg-gray-200 disabled:cursor-not-allowed text-white flex items-center justify-center transition-colors"
          >
            {isChatStreaming ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </button>
        </div>
        <p className="text-[10px] text-gray-400 mt-1.5 text-center">
          Answers are grounded in your contract only · Always verify with a lawyer
        </p>
      </div>
    </div>
  );
}

interface ChatMessageBubbleProps {
  message: ChatTurn;
  isStreaming: boolean;
  onCitationClick?: (page: number, chunkId: string) => void;
}

function ChatMessageBubble({ message, isStreaming, onCitationClick }: ChatMessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn("flex", isUser ? "justify-end" : "justify-start")}
    >
      <div
        className={cn(
          "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed",
          isUser
            ? "bg-blue-600 text-white rounded-br-sm"
            : "bg-gray-100 text-gray-800 rounded-bl-sm",
        )}
      >
        {!isUser && (
          <p className="text-[10px] text-gray-400 font-semibold mb-1 uppercase tracking-wide">
            Based on this contract
          </p>
        )}

        <div className="whitespace-pre-wrap break-words">
          {message.content}
          {isStreaming && (
            <span className="inline-block w-1.5 h-4 bg-gray-400 ml-0.5 animate-pulse rounded-sm align-middle" />
          )}
        </div>

        {/* Citations */}
        {!isUser && message.citations && message.citations.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5 pt-2 border-t border-gray-200/50">
            {message.citations.map((citation: Citation, i: number) => (
              <CitationChip
                key={i}
                citation={citation}
                onClick={() =>
                  onCitationClick?.(citation.page_range[0], citation.chunk_id)
                }
              />
            ))}
          </div>
        )}

        {/* Confidence indicator */}
        {!isUser && message.confidence && message.confidence !== "HIGH" && (
          <div
            className={cn(
              "mt-2 text-[10px] rounded px-1.5 py-0.5 inline-block",
              message.confidence === "NOT_IN_DOCUMENT"
                ? "bg-red-100 text-red-600"
                : "bg-amber-100 text-amber-700",
            )}
          >
            {message.confidence === "NOT_IN_DOCUMENT"
              ? "⚠ Not found in contract"
              : message.confidence === "LOW"
              ? "Low confidence"
              : "Medium confidence"}
          </div>
        )}
      </div>
    </motion.div>
  );
}

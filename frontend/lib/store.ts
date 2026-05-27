/**
 * ClauseGuard Zustand Store
 * ==========================
 * Global state for contract, analysis results, and chat.
 * Uses immer middleware for ergonomic immutable updates.
 */

import { create } from "zustand";
import { devtools } from "zustand/middleware";
import { immer } from "zustand/middleware/immer";
import type {
  FullAnalysisResult,
  ChatTurn,
  ContractListItem,
  RiskAssessment,
  Citation,
} from "@/types";

interface ContractState {
  currentContractId: string | null;
  currentAnalysis: FullAnalysisResult | null;
  highlightedClause: RiskAssessment | null;
  highlightedPage: number | null;
  chatHistory: ChatTurn[];
  isChatStreaming: boolean;
  contractList: ContractListItem[];
  uploadProgress: number;
  isUploading: boolean;
  processingStage: string;
  processingProgress: number;
}

interface ContractActions {
  setCurrentContract: (id: string | null) => void;
  setAnalysis: (analysis: FullAnalysisResult | null) => void;
  setHighlightedClause: (clause: RiskAssessment | null, page?: number) => void;
  addChatMessage: (message: ChatTurn) => void;
  updateLastAssistantMessage: (
    content: string,
    finalize?: boolean,
    citations?: Citation[],
    confidence?: string
  ) => void;
  clearChatHistory: () => void;
  setChatStreaming: (streaming: boolean) => void;
  setContractList: (contracts: ContractListItem[]) => void;
  setUploadProgress: (pct: number) => void;
  setIsUploading: (v: boolean) => void;
  setProcessingStage: (stage: string, progress: number) => void;
  reset: () => void;
}

const initialState: ContractState = {
  currentContractId: null,
  currentAnalysis: null,
  highlightedClause: null,
  highlightedPage: null,
  chatHistory: [],
  isChatStreaming: false,
  contractList: [],
  uploadProgress: 0,
  isUploading: false,
  processingStage: "",
  processingProgress: 0,
};

export const useContractStore = create<ContractState & ContractActions>()(
  devtools(
    immer((set) => ({
      ...initialState,

      setCurrentContract: (id) =>
        set((state) => {
          if (id !== state.currentContractId) {
            state.currentAnalysis = null;
            state.chatHistory = [];
            state.highlightedClause = null;
            state.highlightedPage = null;
          }
          state.currentContractId = id;
        }),

      setAnalysis: (analysis) =>
        set((state) => {
          state.currentAnalysis = analysis;
        }),

      setHighlightedClause: (clause, page) =>
        set((state) => {
          state.highlightedClause = clause;
          state.highlightedPage = page ?? null;
        }),

      addChatMessage: (message) =>
        set((state) => {
          state.chatHistory.push(message);
        }),

      updateLastAssistantMessage: (content, finalize = false, citations, confidence) =>
        set((state) => {
          const lastIdx = state.chatHistory.length - 1;
          if (lastIdx >= 0 && state.chatHistory[lastIdx].role === "assistant") {
            state.chatHistory[lastIdx].content = content;
            if (finalize && citations !== undefined) {
              state.chatHistory[lastIdx].citations = citations;
            }
            if (finalize && confidence) {
              state.chatHistory[lastIdx].confidence = confidence as any;
            }
          }
        }),

      clearChatHistory: () =>
        set((state) => {
          state.chatHistory = [];
        }),

      setChatStreaming: (streaming) =>
        set((state) => {
          state.isChatStreaming = streaming;
        }),

      setContractList: (contracts) =>
        set((state) => {
          state.contractList = contracts;
        }),

      setUploadProgress: (pct) =>
        set((state) => {
          state.uploadProgress = pct;
        }),

      setIsUploading: (v) =>
        set((state) => {
          state.isUploading = v;
        }),

      setProcessingStage: (stage, progress) =>
        set((state) => {
          state.processingStage = stage;
          state.processingProgress = progress;
        }),

      reset: () => set(() => ({ ...initialState })),
    })),
    { name: "clauseguard-store" }
  )
);

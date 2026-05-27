"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, FileText, AlertCircle } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { cn, ACCEPTED_FILE_TYPES, MAX_FILE_SIZE, formatFileSize } from "@/lib/utils";

interface DropZoneProps {
  onFileAccepted: (file: File) => void;
  disabled?: boolean;
}

export function DropZone({ onFileAccepted, disabled }: DropZoneProps) {
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback(
    (accepted: File[], rejected: any[]) => {
      setError(null);
      if (rejected.length > 0) {
        const err = rejected[0]?.errors?.[0];
        if (err?.code === "file-too-large") {
          setError(`File is too large. Maximum size is 10MB.`);
        } else if (err?.code === "file-invalid-type") {
          setError("Only PDF, DOCX, and TXT files are supported.");
        } else {
          setError("File could not be accepted. Please try again.");
        }
        return;
      }
      if (accepted[0]) {
        onFileAccepted(accepted[0]);
      }
    },
    [onFileAccepted],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_FILE_TYPES,
    maxSize: MAX_FILE_SIZE,
    maxFiles: 1,
    disabled,
  });

  return (
    <div className="space-y-2">
      <div
        {...getRootProps()}
        className={cn(
          "relative border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-all duration-200",
          isDragActive
            ? "border-blue-500 bg-blue-50 scale-[1.01]"
            : "border-gray-300 hover:border-blue-400 hover:bg-gray-50/50",
          disabled && "pointer-events-none opacity-50",
        )}
      >
        <input {...getInputProps()} />
        <AnimatePresence mode="wait">
          {isDragActive ? (
            <motion.div
              key="dragging"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0 }}
              className="space-y-2"
            >
              <Upload className="h-10 w-10 text-blue-500 mx-auto" />
              <p className="text-blue-600 font-semibold">Drop your contract here</p>
            </motion.div>
          ) : (
            <motion.div
              key="idle"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="space-y-3"
            >
              <div className="flex justify-center gap-2">
                <FileText className="h-10 w-10 text-gray-300" />
              </div>
              <div>
                <p className="text-sm font-semibold text-gray-700">
                  Drop your contract here, or{" "}
                  <span className="text-blue-600 underline underline-offset-2">
                    browse files
                  </span>
                </p>
                <p className="text-xs text-gray-400 mt-1">
                  PDF, DOCX, or TXT · Max {formatFileSize(MAX_FILE_SIZE)}
                </p>
              </div>
              <p className="text-xs text-gray-400 italic">
                Employment agreements, NDAs, SaaS contracts, leases, service agreements
              </p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="flex items-center gap-2 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2"
          >
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            {error}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

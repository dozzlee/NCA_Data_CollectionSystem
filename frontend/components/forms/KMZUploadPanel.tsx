"use client";

import { useRef, useState } from "react";
import { Upload, FileCheck, AlertTriangle, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface KMZUpload {
  id: number;
  file_name: string;
  file_size: number;
  review_status: "PENDING" | "ACCEPTED" | "REJECTED";
  review_note?: string;
  uploaded_at: string;
}

interface KMZUploadPanelProps {
  submissionId: number;
  requirementId: number;
  category: string;
  description?: string;
  isRequired: boolean;
  uploads: KMZUpload[];
  onUpload: (file: File, requirementId: number) => Promise<void>;
  disabled?: boolean;
}

const STATUS_CONFIG = {
  PENDING: { label: "Awaiting NCA review", color: "text-[#7a5c00]", bg: "bg-[#fff3bf]" },
  ACCEPTED: { label: "Accepted by NCA", color: "text-[#1f7a4d]", bg: "bg-[#e5f4eb]" },
  REJECTED: { label: "Rejected by NCA", color: "text-[#E31937]", bg: "bg-[#ffe8e8]" },
};

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function KMZUploadPanel({
  submissionId,
  requirementId,
  category,
  description,
  isRequired,
  uploads,
  onUpload,
  disabled,
}: KMZUploadPanelProps) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);

  async function handleFile(file: File) {
    setError(null);
    if (!file.name.toLowerCase().endsWith(".kmz")) {
      setError("Only .kmz files are accepted.");
      return;
    }
    if (file.size > 50 * 1024 * 1024) {
      setError("File must be under 50MB.");
      return;
    }
    setUploading(true);
    try {
      await onUpload(file, requirementId);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Upload failed. Please try again.");
    } finally {
      setUploading(false);
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }

  return (
    <div className="rounded-[12px] border border-[#c3c6d0] bg-white p-4 space-y-3">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <p className="text-[13px] font-semibold text-[#191c1e]">
              KMZ Upload — {category}
            </p>
            {isRequired && (
              <span className="rounded-full bg-[#ffe8e8] px-2 py-0.5 text-[10px] font-semibold text-[#E31937]">
                Required
              </span>
            )}
          </div>
          {description && (
            <p className="text-[11px] text-[#737780] mt-0.5">{description}</p>
          )}
        </div>
      </div>

      {/* Existing uploads */}
      {uploads.length > 0 && (
        <div className="space-y-2">
          {uploads.map((u) => {
            const s = STATUS_CONFIG[u.review_status];
            return (
              <div key={u.id} className="flex items-center gap-3 rounded-[8px] border border-[#e6e8ea] px-3 py-2">
                <FileCheck size={14} className="shrink-0 text-[#0066cc]" />
                <div className="flex-1 min-w-0">
                  <p className="text-[12px] font-medium text-[#191c1e] truncate">{u.file_name}</p>
                  <p className="text-[11px] text-[#737780]">{formatBytes(u.file_size)}</p>
                </div>
                <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-semibold", s.bg, s.color)}>
                  {s.label}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Drop zone */}
      {!disabled && (
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          className={cn(
            "flex flex-col items-center justify-center gap-2 rounded-[8px] border-2 border-dashed px-4 py-6 transition-colors cursor-pointer",
            dragOver
              ? "border-[#0066cc] bg-[#0066cc]/5"
              : "border-[#c3c6d0] hover:border-[#0066cc] hover:bg-[#f7f9fb]"
          )}
          onClick={() => fileRef.current?.click()}
        >
          <Upload size={18} className="text-[#737780]" />
          <div className="text-center">
            <p className="text-[12px] font-medium text-[#191c1e]">
              {uploading ? "Uploading…" : "Drop .kmz file here or click to browse"}
            </p>
            <p className="text-[11px] text-[#737780]">KMZ format only · Max 50MB</p>
          </div>
          <input
            ref={fileRef}
            type="file"
            accept=".kmz"
            className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); }}
          />
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 rounded-[8px] bg-[#ffe8e8] px-3 py-2 text-[12px] text-[#E31937]">
          <AlertTriangle size={13} />
          {error}
        </div>
      )}
    </div>
  );
}

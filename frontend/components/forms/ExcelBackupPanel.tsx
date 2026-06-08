"use client";

import { useRef, useState } from "react";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";

interface ExcelBackup {
  id: number;
  file_name: string;
  file_size: number;
  uploaded_at: string;
  source_control_status: "STORED" | "SUPERSEDED";
}

interface ExcelBackupPanelProps {
  submissionId: number;
  backups: ExcelBackup[];
  onUploaded: () => void;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function ExcelBackupPanel({ submissionId, backups, onUploaded }: ExcelBackupPanelProps) {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const { toast } = useToast();

  async function uploadFile(file: File) {
    const ext = file.name.split(".").pop()?.toLowerCase();
    if (!ext || !["xlsx", "xls"].includes(ext)) {
      toast("Only .xlsx or .xls files are accepted.", "error");
      return;
    }
    setUploading(true);
    const form = new FormData();
    form.append("file", file);
    try {
      await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/submissions/${submissionId}/excel-backups/upload/`, {
        method: "POST",
        headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
        body: form,
      }).then(async (r) => {
        if (!r.ok) {
          const err = await r.json().catch(() => ({}));
          throw new Error(err.detail || "Upload failed.");
        }
      });
      toast("Excel backup uploaded.", "success");
      onUploaded();
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : "Upload failed.", "error");
    } finally {
      setUploading(false);
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) uploadFile(file);
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) uploadFile(file);
    e.target.value = "";
  }

  return (
    <div className="rounded-[12px] border border-[#c3c6d0] bg-[#f7f9fb] p-5 space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-[14px] font-semibold text-[#191c1e]">Excel Source Backup</h3>
          <p className="mt-0.5 text-[12px] text-[#43474f]">
            Stored for source control only — not used for analysis or calculations.
          </p>
        </div>
        <span className="shrink-0 rounded-full bg-[#e5f4eb] px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-[#1f7a4d]">
          Source only
        </span>
      </div>

      {/* Drop zone */}
      <div
        className={`flex flex-col items-center justify-center rounded-[8px] border-2 border-dashed px-6 py-8 text-center transition-colors cursor-pointer ${
          dragging ? "border-[#0066cc] bg-[#e8f1fb]" : "border-[#c3c6d0] hover:border-[#0066cc]/50"
        }`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
        aria-label="Upload Excel backup file"
      >
        <span className="text-[28px] mb-2" aria-hidden>📊</span>
        <p className="text-[13px] font-medium text-[#191c1e]">
          {uploading ? "Uploading…" : "Drop .xlsx / .xls here or click to browse"}
        </p>
        <p className="mt-1 text-[11px] text-[#737780]">Max 50 MB</p>
        <input
          ref={inputRef}
          type="file"
          accept=".xlsx,.xls"
          className="sr-only"
          onChange={handleChange}
        />
      </div>

      {/* Existing backups */}
      {backups.length > 0 && (
        <ul className="divide-y divide-[#eceef0]">
          {backups.map((b) => (
            <li key={b.id} className="flex items-center justify-between py-2.5 gap-3">
              <div className="min-w-0">
                <p className="truncate text-[13px] font-medium text-[#191c1e]">{b.file_name}</p>
                <p className="text-[11px] text-[#737780]">
                  {formatBytes(b.file_size)} · {new Date(b.uploaded_at).toLocaleDateString("en-GB")}
                </p>
              </div>
              {b.source_control_status === "SUPERSEDED" && (
                <span className="shrink-0 rounded-full bg-[#f2f4f6] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[#737780]">
                  Superseded
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

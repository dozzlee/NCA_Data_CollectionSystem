"use client";

import { useState } from "react";
import { Upload, AlertCircle, Check } from "lucide-react";

interface ExcelBackupFile {
  id: number;
  file_name: string;
  file_size: number;
  uploaded_at: string;
  source_control_status: string;
}

interface ExcelBackupPanelProps {
  submissionId: number;
  uploads: ExcelBackupFile[];
  onUpload: (file: File) => Promise<void>;
  disabled?: boolean;
  description?: string;
}

export function ExcelBackupPanel({
  submissionId,
  uploads,
  onUpload,
  disabled = false,
  description = "Upload an Excel file as a backup. This is stored for source control only and not analyzed.",
}: ExcelBackupPanelProps) {
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<"uploading" | "success" | "error" | null>(null);
  const [dragOver, setDragOver] = useState(false);

  async function handleFileSelect(file: File) {
    if (!file.name.match(/\.(xlsx?|xls)$/i)) {
      setUploadMsg("error");
      setTimeout(() => setUploadMsg(null), 3000);
      return;
    }

    setUploading(true);
    setUploadMsg("uploading");
    try {
      await onUpload(file);
      setUploadMsg("success");
      setTimeout(() => setUploadMsg(null), 2000);
    } catch {
      setUploadMsg("error");
      setTimeout(() => setUploadMsg(null), 3000);
    } finally {
      setUploading(false);
    }
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    const files = e.dataTransfer.files;
    if (files?.length) handleFileSelect(files[0]);
  }

  return (
    <div className="rounded-[12px] border border-[#e6e8ea] bg-[#f7f9fb] p-5 space-y-3">
      <div>
        <h3 className="text-[13px] font-semibold text-[#191c1e]">Excel Backup</h3>
        <p className="text-[12px] text-[#43474f] mt-0.5">{description}</p>
      </div>

      {/* Upload area */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={`rounded-[8px] border-2 border-dashed p-4 text-center transition-colors ${
          dragOver ? "border-[#0066cc] bg-[#e8f1fb]" : "border-[#c3c6d0]"
        } ${disabled ? "opacity-50 cursor-not-allowed" : ""}`}
      >
        <label className="flex flex-col items-center gap-2 cursor-pointer">
          <Upload size={18} className="text-[#737780]" />
          <div className="text-[12px]">
            <p className="font-medium text-[#191c1e]">Drop Excel file here or click to browse</p>
            <p className="text-[11px] text-[#737780]">.xlsx or .xls (max 50MB)</p>
          </div>
          <input
            type="file"
            accept=".xlsx,.xls,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel"
            onChange={(e) => e.target.files?.[0] && handleFileSelect(e.target.files[0])}
            disabled={disabled || uploading}
            className="hidden"
          />
        </label>
      </div>

      {/* Status messages */}
      {uploadMsg === "uploading" && (
        <div className="flex items-center gap-2 text-[12px] text-[#004999]">
          <div className="h-3 w-3 rounded-full border-2 border-[#0066cc] border-t-transparent animate-spin" />
          Uploading…
        </div>
      )}
      {uploadMsg === "success" && (
        <div className="flex items-center gap-2 text-[12px] text-[#1f7a4d] bg-[#e5f4eb] rounded-[6px] px-3 py-2">
          <Check size={14} />
          File uploaded successfully
        </div>
      )}
      {uploadMsg === "error" && (
        <div className="flex items-center gap-2 text-[12px] text-[#c0112a] bg-[#ffe8e8] rounded-[6px] px-3 py-2">
          <AlertCircle size={14} />
          Upload failed. Please try again.
        </div>
      )}

      {/* Previous uploads */}
      {uploads.length > 0 && (
        <div className="space-y-2 border-t border-[#eceef0] pt-3">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-[#737780]">Previous Uploads</p>
          <div className="space-y-1.5">
            {uploads.map((u) => (
              <div key={u.id} className="flex items-center justify-between bg-white rounded-[6px] px-3 py-2 text-[12px]">
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-[#191c1e] truncate">{u.file_name}</p>
                  <p className="text-[11px] text-[#737780]">
                    {(u.file_size / 1024 / 1024).toFixed(2)}MB • {new Date(u.uploaded_at).toLocaleDateString()}
                  </p>
                </div>
                <span className="ml-2 shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold bg-[#e5f4eb] text-[#1f7a4d]">
                  Stored
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

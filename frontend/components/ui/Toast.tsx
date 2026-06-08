"use client";

import { createContext, useCallback, useContext, useRef, useState } from "react";
import { cn } from "@/lib/utils";

type ToastVariant = "success" | "error" | "warning" | "info";

interface Toast {
  id: string;
  message: string;
  variant: ToastVariant;
}

interface ToastContextValue {
  toast: (message: string, variant?: ToastVariant) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}

const ICONS: Record<ToastVariant, string> = {
  success: "✓",
  error: "✕",
  warning: "!",
  info: "i",
};

const STYLES: Record<ToastVariant, string> = {
  success: "border-l-[#1f7a4d] bg-[#e5f4eb] text-[#1f7a4d]",
  error: "border-l-[#e31937] bg-[#ffe8e8] text-[#c0112a]",
  warning: "border-l-[#ffd100] bg-[#fff3bf] text-[#7a5c00]",
  info: "border-l-[#0066cc] bg-[#e8f1fb] text-[#004999]",
};

const ICON_BG: Record<ToastVariant, string> = {
  success: "bg-[#1f7a4d]/10",
  error: "bg-[#e31937]/10",
  warning: "bg-[#ffd100]/20",
  info: "bg-[#0066cc]/10",
};

function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: () => void }) {
  return (
    <div
      className={cn(
        "flex items-start gap-3 rounded-[8px] border border-transparent border-l-4 px-4 py-3 shadow-lg",
        "animate-in slide-in-from-bottom-2 fade-in duration-300",
        STYLES[toast.variant]
      )}
      style={{ minWidth: 280, maxWidth: 400 }}
      role="alert"
    >
      <span className={cn("flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-bold mt-0.5", ICON_BG[toast.variant])}>
        {ICONS[toast.variant]}
      </span>
      <p className="flex-1 text-[13px] font-medium leading-snug">{toast.message}</p>
      <button
        onClick={onDismiss}
        className="shrink-0 text-current opacity-50 hover:opacity-100 transition-opacity ml-1"
        aria-label="Dismiss"
      >
        ✕
      </button>
    </div>
  );
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    clearTimeout(timers.current[id]);
    delete timers.current[id];
  }, []);

  const toast = useCallback((message: string, variant: ToastVariant = "info") => {
    const id = crypto.randomUUID();
    setToasts((prev) => [...prev.slice(-4), { id, message, variant }]);
    timers.current[id] = setTimeout(() => dismiss(id), 4500);
  }, [dismiss]);

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div
        aria-live="polite"
        className="fixed bottom-6 right-6 z-50 flex flex-col gap-2"
      >
        {toasts.map((t) => (
          <ToastItem key={t.id} toast={t} onDismiss={() => dismiss(t.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

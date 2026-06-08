"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";

export default function MFAPage() {
  const [digits, setDigits] = useState(["", "", "", "", "", ""]);
  const [loading, setLoading] = useState(false);
  const inputs = useRef<(HTMLInputElement | null)[]>([]);
  const router = useRouter();
  const { toast } = useToast();

  function handleChange(index: number, val: string) {
    if (!/^\d?$/.test(val)) return;
    const next = [...digits];
    next[index] = val;
    setDigits(next);
    if (val && index < 5) inputs.current[index + 1]?.focus();
  }

  function handleKeyDown(index: number, e: React.KeyboardEvent) {
    if (e.key === "Backspace" && !digits[index] && index > 0) {
      inputs.current[index - 1]?.focus();
    }
  }

  function handlePaste(e: React.ClipboardEvent) {
    e.preventDefault();
    const pasted = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
    const next = [...digits];
    pasted.split("").forEach((ch, i) => { next[i] = ch; });
    setDigits(next);
    inputs.current[Math.min(pasted.length, 5)]?.focus();
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const code = digits.join("");
    if (code.length !== 6) return;
    setLoading(true);
    try {
      await api("/auth/mfa/verify/", { method: "POST", body: JSON.stringify({ code }) });
      router.push("/dashboard");
    } catch {
      toast("Invalid or expired code. Please try again.", "error");
      setDigits(["", "", "", "", "", ""]);
      inputs.current[0]?.focus();
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#f7f9fb]">
      <div className="w-full max-w-sm">
        {/* NCA brand mark */}
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-[12px] bg-[#001836]">
            <span className="text-[22px] font-bold text-[#ffd100]">N</span>
          </div>
          <h1 className="text-[24px] font-semibold text-[#191c1e]">Two-factor verification</h1>
          <p className="mt-2 text-[14px] text-[#43474f]">
            Enter the 6-digit code from your authenticator app.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="rounded-[16px] bg-white p-8 shadow-[0_16px_42px_rgba(0,45,91,0.10)]">
          {/* TOTP digit inputs */}
          <div className="flex justify-center gap-3" onPaste={handlePaste}>
            {digits.map((d, i) => (
              <input
                key={i}
                ref={(el) => { inputs.current[i] = el; }}
                type="text"
                inputMode="numeric"
                maxLength={1}
                value={d}
                onChange={(e) => handleChange(i, e.target.value)}
                onKeyDown={(e) => handleKeyDown(i, e)}
                autoFocus={i === 0}
                className="h-14 w-11 rounded-[8px] border border-[#c3c6d0] bg-[#f7f9fb] text-center text-[22px] font-semibold text-[#191c1e] transition-colors focus:border-[#0066cc] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#0066cc]/20"
                aria-label={`Digit ${i + 1}`}
              />
            ))}
          </div>

          <button
            type="submit"
            disabled={loading || digits.join("").length !== 6}
            className="mt-8 w-full rounded-[8px] bg-[#001836] px-4 py-3 text-[15px] font-semibold text-white transition-colors hover:bg-[#002d5b] focus:outline-none focus:ring-2 focus:ring-[#0066cc]/40 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "Verifying…" : "Verify"}
          </button>

          <p className="mt-5 text-center text-[13px] text-[#43474f]">
            Having trouble?{" "}
            <a href="/login" className="text-[#0066cc] hover:underline font-medium">
              Sign in again
            </a>
          </p>
        </form>
      </div>
    </div>
  );
}

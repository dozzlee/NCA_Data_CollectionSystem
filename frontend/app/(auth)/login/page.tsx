"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Eye, EyeOff, AlertCircle } from "lucide-react";
import { setAuthTokens } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const res = await fetch("/api/v1/auth/login/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (!res.ok) {
        const data = await res.json();
        const msg = data?.non_field_errors?.[0] ?? data?.detail ?? "Invalid credentials.";
        setError(msg);
        return;
      }

      const data = await res.json();
      setAuthTokens({ access: data.access, refresh: data.refresh });

      // Route by role
      const role: string = data.user?.role ?? "";
      if (role.startsWith("NCA")) {
        router.replace("/dashboard");
      } else {
        router.replace("/provider/dashboard");
      }
    } catch {
      setError("Connection failed. Please check your network and try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex" style={{
      background: "radial-gradient(ellipse at 20% 0%, rgba(0,102,204,0.10) 0%, transparent 50%), linear-gradient(135deg, #f7f9fb 0%, #eef3f8 100%)"
    }}>
      {/* Left — brand panel */}
      <div className="hidden lg:flex lg:w-[480px] xl:w-[560px] flex-col justify-between p-12"
        style={{ background: "linear-gradient(160deg, #002d5b 0%, #001836 100%)" }}>

        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-[10px] bg-[#E31937] text-[10px] font-bold text-white tracking-wider">
            NCA
          </div>
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.1em] text-white/50">National Communications Authority</p>
            <p className="text-[14px] font-semibold text-white">Data Collection System</p>
          </div>
        </div>

        <div className="space-y-6">
          <h1 className="text-[36px] font-semibold text-white leading-tight" style={{ letterSpacing: "-0.02em" }}>
            Secure regulatory data collection for Ghana.
          </h1>
          <p className="text-[15px] text-white/60 leading-relaxed max-w-[380px]">
            A traceable submission system for licensed providers and NCA review teams. Every form, every version, every action — on record.
          </p>
          <div className="grid grid-cols-1 gap-3">
            {[
              { label: "Manual web forms", desc: "Grouped sections, draft saving, required field validation" },
              { label: "Traceable review", desc: "Field statuses, correction tracking, audit trail" },
              { label: "Compliance monitoring", desc: "Due states, overdue alerts, email follow-up" },
            ].map(({ label, desc }) => (
              <div key={label} className="flex items-start gap-3 rounded-[10px] border border-white/10 bg-white/05 px-4 py-3">
                <div className="mt-0.5 h-2 w-2 rounded-full bg-[#0066cc] shrink-0" />
                <div>
                  <p className="text-[13px] font-semibold text-white">{label}</p>
                  <p className="text-[11px] text-white/50 mt-0.5">{desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <p className="text-[11px] text-white/30">
          National Communications Authority · Ghana · Regulatory Portal
        </p>
      </div>

      {/* Right — login form */}
      <div className="flex flex-1 items-center justify-center px-6 py-12">
        <div className="w-full max-w-[400px] space-y-6">

          {/* Mobile brand */}
          <div className="flex items-center gap-2.5 lg:hidden">
            <div className="flex h-8 w-8 items-center justify-center rounded-[8px] bg-[#E31937] text-[9px] font-bold text-white tracking-wider">NCA</div>
            <p className="text-[14px] font-semibold text-[#191c1e]">Data Collection System</p>
          </div>

          <div>
            <h2 className="text-[24px] font-semibold text-[#191c1e]" style={{ letterSpacing: "-0.01em" }}>Sign in</h2>
            <p className="text-[13px] text-[#737780] mt-1">Enter your NCA or provider credentials to continue.</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label className="block text-[13px] font-medium text-[#191c1e]">Email address</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                placeholder="you@example.com"
                className="w-full rounded-[8px] border border-[#c3c6d0] bg-white px-3 py-2.5 text-[13px] text-[#191c1e] placeholder:text-[#737780] transition-colors focus:border-[#0066cc] focus:outline-none focus:ring-2 focus:ring-[#0066cc]/20"
              />
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <label className="block text-[13px] font-medium text-[#191c1e]">Password</label>
                <button type="button" className="text-[12px] font-medium text-[#0066cc] hover:text-[#002d5b] transition-colors">
                  Forgot password?
                </button>
              </div>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                  placeholder="••••••••••••"
                  className="w-full rounded-[8px] border border-[#c3c6d0] bg-white px-3 py-2.5 pr-10 text-[13px] text-[#191c1e] placeholder:text-[#737780] transition-colors focus:border-[#0066cc] focus:outline-none focus:ring-2 focus:ring-[#0066cc]/20"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#737780] hover:text-[#43474f]"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-2 rounded-[8px] border border-[#E31937]/20 bg-[#ffe8e8] px-3 py-2.5 text-[12px] text-[#E31937]">
                <AlertCircle size={13} className="shrink-0" />
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-[8px] bg-[#002d5b] py-2.5 text-[14px] font-semibold text-white transition-colors hover:bg-[#001836] disabled:opacity-60"
            >
              {loading ? "Signing in…" : "Continue"}
            </button>
          </form>

          <p className="text-[11px] text-[#737780] text-center leading-relaxed">
            Multi-factor authentication, account lockout, and session timeout are enforced per NCA security policy.
          </p>
        </div>
      </div>
    </div>
  );
}

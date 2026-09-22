"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";

export default function ChangePasswordPage() {
  const router = useRouter();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault(); setError("");
    if (newPassword !== confirmPassword) { setError("The new passwords do not match."); return; }
    setSaving(true);
    try {
      await api.post("/auth/change-password/", { current_password: currentPassword, new_password: newPassword });
      const user = await api.get<{ role: string }>("/auth/me/");
      router.replace(user.role === "NCA_VIEWER" ? "/data-requests" : user.role.startsWith("NCA") ? "/dashboard" : "/provider/dashboard");
    } catch (exception) {
      setError(exception instanceof ApiError ? exception.message : "Password change failed.");
    } finally { setSaving(false); }
  }

  return <div className="flex min-h-screen items-center justify-center bg-[#f7f9fb] px-6">
    <form onSubmit={submit} className="w-full max-w-md space-y-4 rounded-[16px] border border-[#e6e8ea] bg-white p-8 shadow-sm">
      <div><h1 className="text-[22px] font-semibold text-[#191c1e]">Set a new password</h1>
        <p className="mt-1 text-[13px] text-[#737780]">Your administrator issued a temporary password. Replace it before continuing.</p></div>
      {[{label:"Temporary password",value:currentPassword,set:setCurrentPassword},{label:"New password",value:newPassword,set:setNewPassword},{label:"Confirm new password",value:confirmPassword,set:setConfirmPassword}].map((field) =>
        <label key={field.label} className="block text-[13px] font-medium text-[#191c1e]">{field.label}
          <input type="password" required minLength={12} value={field.value} onChange={(event)=>field.set(event.target.value)}
            className="mt-1.5 w-full rounded-[8px] border border-[#c3c6d0] px-3 py-2.5 focus:border-[#0066cc] focus:outline-none focus:ring-2 focus:ring-[#0066cc]/20" /></label>)}
      {error && <p className="rounded-[8px] bg-[#ffe8e8] px-3 py-2 text-[12px] text-[#c0112a]">{error}</p>}
      <button disabled={saving} className="w-full rounded-[8px] bg-[#002d5b] py-2.5 text-[14px] font-semibold text-white disabled:opacity-60">{saving ? "Saving…" : "Change password"}</button>
    </form>
  </div>;
}

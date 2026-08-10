"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { PaginatedResponse, ProviderProfile, User, UserRole } from "@/lib/types";
import { useCurrentUser } from "@/hooks/useCurrentUser";

export default function UsersPage() {
  const currentUser = useCurrentUser().data;
  const qc = useQueryClient();
  const [form, setForm] = useState({ email: "", name: "", role: "PROVIDER_DATA_ENTRY" as UserRole, organization_id: "", password: "" });
  const usersQ = useQuery({ queryKey: ["users"], queryFn: () => api.get<PaginatedResponse<User>>("/auth/users/"), enabled: currentUser?.role === "NCA_ADMIN" });
  const providersQ = useQuery({ queryKey: ["providers-for-users"], queryFn: () => api.get<PaginatedResponse<ProviderProfile>>("/providers/"), enabled: currentUser?.role === "NCA_ADMIN" });
  const create = useMutation({
    mutationFn: () => api.post("/auth/users/", {
      ...form,
      organization_id: form.role.startsWith("PROVIDER_") ? Number(form.organization_id) : null,
    }),
    onSuccess: () => { setForm({ email: "", name: "", role: "PROVIDER_DATA_ENTRY", organization_id: "", password: "" }); qc.invalidateQueries({ queryKey: ["users"] }); },
  });
  const toggle = useMutation({
    mutationFn: (user: User) => api.patch(`/auth/users/${user.id}/`, { is_active: !user.is_active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });
  if (currentUser?.role !== "NCA_ADMIN") return <p>Access denied.</p>;
  return <div className="space-y-6">
    <div><h1 className="text-[28px] font-semibold">Users</h1><p className="text-[13px] text-[#737780]">Manage NCA and provider workflow accounts.</p></div>
    <div className="grid grid-cols-2 gap-3 rounded-[14px] border bg-white p-5">
      <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Full name" className="rounded-[8px] border p-2 text-[13px]" />
      <input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="Email" type="email" className="rounded-[8px] border p-2 text-[13px]" />
      <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as UserRole })} className="rounded-[8px] border p-2 text-[13px]">
        <option value="PROVIDER_DATA_ENTRY">Provider Data Entry</option><option value="PROVIDER_APPROVER">Provider Approver</option><option value="NCA_OFFICER">NCA Officer</option><option value="NCA_ADMIN">System Administrator</option>
      </select>
      <select value={form.organization_id} onChange={(e) => setForm({ ...form, organization_id: e.target.value })} disabled={!form.role.startsWith("PROVIDER_")} className="rounded-[8px] border p-2 text-[13px]">
        <option value="">Select provider</option>{(providersQ.data?.results ?? []).map((provider) => <option key={provider.id} value={provider.organization}>{provider.registered_name}</option>)}
      </select>
      <input value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder="Temporary password" type="password" className="rounded-[8px] border p-2 text-[13px]" />
      <button onClick={() => create.mutate()} disabled={!form.email || !form.name || !form.password || (form.role.startsWith("PROVIDER_") && !form.organization_id)} className="rounded-[8px] bg-[#002d5b] p-2 text-[13px] font-semibold text-white disabled:opacity-40">Create account</button>
    </div>
    <div className="overflow-hidden rounded-[14px] border bg-white">{(usersQ.data?.results ?? []).map((user) => <div key={user.id} className="flex items-center justify-between border-b px-5 py-3">
      <div><p className="text-[13px] font-semibold">{user.name}</p><p className="text-[11px] text-[#737780]">{user.email} · {user.role.replaceAll("_", " ")} · {user.organization?.name ?? "NCA"}</p></div>
      <button onClick={() => toggle.mutate(user)} className={`rounded-full px-3 py-1 text-[11px] font-semibold ${user.is_active ? "bg-green-50 text-green-700" : "bg-gray-100 text-gray-600"}`}>{user.is_active ? "Active" : "Inactive"}</button>
    </div>)}</div>
  </div>;
}

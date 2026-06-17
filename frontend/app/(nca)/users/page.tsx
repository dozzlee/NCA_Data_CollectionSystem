"use client";

import { useState, useMemo } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import type { User, UserRole, ProviderProfile } from "@/lib/types";
import { PROVIDER_CATEGORY_LABELS } from "@/lib/utils";

const ROLES: { value: UserRole; label: string; group: string }[] = [
  { value:"NCA_ADMIN",           label:"System Administrator", group:"NCA" },
  { value:"NCA_OFFICER",         label:"NCA Officer",          group:"NCA" },
  { value:"PROVIDER_DATA_ENTRY", label:"Provider Data Entry",  group:"Provider" },
  { value:"PROVIDER_APPROVER",   label:"Provider Approver",    group:"Provider" },
];

const ROLE_COLORS: Record<UserRole, string> = {
  NCA_ADMIN:           "bg-[#ffe8e8] text-[#c0112a]",
  NCA_OFFICER:         "bg-[#e8f1fb] text-[#004999]",
  PROVIDER_DATA_ENTRY: "bg-[#f2f4f6] text-[#43474f]",
  PROVIDER_APPROVER:   "bg-[#e5f4eb] text-[#1f7a4d]",
};

const ROLE_LABELS: Record<UserRole, string> = {
  NCA_ADMIN:           "System Admin",
  NCA_OFFICER:         "NCA Officer",
  PROVIDER_DATA_ENTRY: "Data Entry",
  PROVIDER_APPROVER:   "Approver",
};

interface NewUserForm {
  name: string; email: string; password: string;
  role: UserRole; organization: string;
}

const EMPTY: NewUserForm = { name:"", email:"", password:"", role:"NCA_OFFICER", organization:"" };

const inp = "w-full rounded-[8px] border border-[#c3c6d0] px-3 py-2 text-[13px] text-[#191c1e] focus:border-[#0066cc] focus:outline-none focus:ring-2 focus:ring-[#0066cc]/20";
const lbl = "block text-[11px] font-semibold uppercase tracking-wide text-[#737780] mb-1";

export default function UsersPage() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const searchParams = useSearchParams();
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState<NewUserForm>(EMPTY);
  const [filterRole, setFilterRole] = useState(searchParams.get("role") ?? "");

  const queryString = useMemo(() => {
    const p = new URLSearchParams();
    if (filterRole) p.set("role", filterRole);
    return p.toString();
  }, [filterRole]);

  const { data, isLoading } = useQuery<{ results: User[] }>({
    queryKey: ["users", queryString],
    queryFn: () => api(`/auth/users/${queryString ? `?${queryString}` : ""}`),
  });

  const { data: providersData } = useQuery<{ results: ProviderProfile[] }>({
    queryKey: ["providers-all-for-users"],
    queryFn: () => api("/providers/"),
  });

  const createMut = useMutation({
    mutationFn: () => api("/auth/users/", {
      method: "POST",
      body: JSON.stringify({
        name: form.name, email: form.email, password: form.password,
        role: form.role, organization: form.organization || null,
      }),
    }),
    onSuccess: () => {
      toast("User created.", "success");
      setShowCreate(false); setForm(EMPTY);
      qc.invalidateQueries({ queryKey: ["users"] });
    },
    onError: () => toast("Failed to create user. Check that the email is unique.", "error"),
  });

  const toggleActiveMut = useMutation({
    mutationFn: (userId: string) =>
      api(`/auth/users/${userId}/toggle-active/`, { method: "POST" }),
    onSuccess: (data: { is_active: boolean; email: string }) => {
      toast(`${data.email} ${data.is_active ? "activated" : "deactivated"}.`, data.is_active ? "success" : "warning");
      qc.invalidateQueries({ queryKey: ["users"] });
    },
    onError: () => toast("Failed to update user.", "error"),
  });

  const users = data?.results ?? [];
  const isProviderRole = (role: UserRole) => role.startsWith("PROVIDER_");

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[28px] font-semibold text-[#191c1e]">User Management</h1>
          <p className="mt-1 text-[14px] text-[#43474f]">
            Create and manage accounts for all four roles. All actions are audited.
          </p>
        </div>
        <button onClick={() => setShowCreate(v => !v)}
          className="rounded-[8px] bg-[#001836] px-4 py-2 text-[13px] font-semibold text-white hover:bg-[#002d5b]">
          {showCreate ? "Cancel" : "+ New User"}
        </button>
      </div>

      {/* Role reference */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {ROLES.map(r => (
          <div key={r.value} className="rounded-[10px] border border-[#eceef0] bg-white px-4 py-3">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-[#737780] mb-0.5">{r.group}</p>
            <p className="text-[13px] font-semibold text-[#191c1e]">{r.label}</p>
          </div>
        ))}
      </div>

      {/* Create form */}
      {showCreate && (
        <form onSubmit={e => { e.preventDefault(); createMut.mutate(); }}
          className="rounded-[16px] border border-[#eceef0] bg-white p-6 space-y-4">
          <h2 className="text-[15px] font-semibold text-[#191c1e]">New User</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <div>
              <label className={lbl}>Full Name</label>
              <input className={inp} placeholder="e.g. Kwame Asante" required
                value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
            </div>
            <div>
              <label className={lbl}>Email Address</label>
              <input type="email" className={inp} placeholder="e.g. k.asante@nca.org.gh" required
                value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} />
            </div>
            <div>
              <label className={lbl}>Temporary Password</label>
              <input type="password" className={inp} placeholder="Min. 12 characters" required minLength={12}
                value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))} />
            </div>
            <div>
              <label className={lbl}>Role</label>
              <select className={inp} value={form.role}
                onChange={e => setForm(f => ({ ...f, role: e.target.value as UserRole, organization: "" }))}>
                {ROLES.map(r => (
                  <option key={r.value} value={r.value}>{r.group}: {r.label}</option>
                ))}
              </select>
            </div>
            {isProviderRole(form.role) ? (
              <div>
                <label className={lbl}>Provider Organisation</label>
                <select className={inp} required
                  value={form.organization}
                  onChange={e => setForm(f => ({ ...f, organization: e.target.value }))}>
                  <option value="">Select provider…</option>
                  {(providersData?.results ?? []).map(p => (
                    <option key={p.id} value={p.id}>
                      {p.registered_name} ({PROVIDER_CATEGORY_LABELS[p.category]})
                    </option>
                  ))}
                </select>
                <p className="text-[11px] text-[#737780] mt-1">Provider users only see their own organisation's data.</p>
              </div>
            ) : (
              <div>
                <label className={lbl}>Organisation</label>
                <input className={inp} value="NCA" disabled />
              </div>
            )}
          </div>
          <div className="rounded-[8px] bg-[#fff3bf] border border-[#ffd100]/50 px-4 py-3 text-[12px] text-[#7a5c00]">
            <p className="font-semibold">Admin configuration does not grant provider submission authority.</p>
            <p>System Administrators cannot submit regulatory data on behalf of providers.</p>
          </div>
          <button type="submit" disabled={createMut.isPending}
            className="rounded-[8px] bg-[#001836] px-5 py-2.5 text-[13px] font-semibold text-white hover:bg-[#002d5b] disabled:opacity-50">
            {createMut.isPending ? "Creating…" : "Create User"}
          </button>
        </form>
      )}

      {/* Filters */}
      <div className="flex gap-3">
        <select value={filterRole} onChange={e => setFilterRole(e.target.value)}
          className="rounded-[8px] border border-[#c3c6d0] px-3 py-2 text-[13px] focus:border-[#0066cc] focus:outline-none">
          <option value="">All roles</option>
          {ROLES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
        </select>
      </div>

      {/* Users table */}
      <div className="rounded-[16px] border border-[#eceef0] bg-white overflow-hidden">
        <table className="w-full text-left">
          <thead className="border-b border-[#eceef0] bg-[#f7f9fb]">
            <tr>
              {["Name","Email","Role","Organisation","Status",""].map(h => (
                <th key={h} className="px-5 py-3 text-[11px] font-semibold uppercase tracking-wide text-[#43474f]">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[#eceef0]">
            {isLoading
              ? Array.from({ length: 6 }).map((_, i) => (
                  <tr key={i}>{Array.from({ length: 6 }).map((_, j) => (
                    <td key={j} className="px-5 py-4"><Skeleton className="h-3.5 w-full" /></td>
                  ))}</tr>
                ))
              : users.length === 0
              ? <tr><td colSpan={6} className="px-5 py-10 text-center text-[14px] text-[#737780]">No users found.</td></tr>
              : users.map(u => (
                <tr key={u.id} className={`hover:bg-[#f7f9fb] transition-colors ${!u.is_active ? "opacity-50" : ""}`}>
                  <td className="px-5 py-3.5 text-[13px] font-medium text-[#191c1e]">{u.name}</td>
                  <td className="px-5 py-3.5 text-[13px] text-[#43474f]">{u.email}</td>
                  <td className="px-5 py-3.5">
                    <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${ROLE_COLORS[u.role as UserRole] ?? "bg-[#f2f4f6] text-[#43474f]"}`}>
                      {ROLE_LABELS[u.role as UserRole] ?? u.role}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 text-[13px] text-[#43474f]">
                    {u.organization?.name ?? "—"}
                  </td>
                  <td className="px-5 py-3.5">
                    <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${u.is_active ? "bg-[#e5f4eb] text-[#1f7a4d]" : "bg-[#f2f4f6] text-[#737780]"}`}>
                      {u.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-5 py-3.5">
                    <button
                      onClick={() => toggleActiveMut.mutate(u.id)}
                      disabled={toggleActiveMut.isPending}
                      className="text-[12px] font-medium text-[#0066cc] hover:underline disabled:opacity-50">
                      {u.is_active ? "Deactivate" : "Reactivate"}
                    </button>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

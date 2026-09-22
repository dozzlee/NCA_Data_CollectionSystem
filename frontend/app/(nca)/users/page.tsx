"use client";

import { Suspense, useState, useMemo } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import type { User, UserRole, ProviderProfile, NCADivision } from "@/lib/types";
import { PROVIDER_CATEGORY_LABELS } from "@/lib/utils";

const ROLES: { value: UserRole; label: string; group: string }[] = [
  { value:"NCA_ADMIN",           label:"System Administrator", group:"NCA" },
  { value:"NCA_OFFICER",         label:"NCA Officer",          group:"NCA" },
  { value:"NCA_VIEWER",          label:"NCA Data Requester",     group:"NCA" },
  { value:"PROVIDER_DATA_ENTRY", label:"Provider Data Entry",  group:"Provider" },
  { value:"PROVIDER_APPROVER",   label:"Provider Approver",    group:"Provider" },
];

const ROLE_COLORS: Record<UserRole, string> = {
  NCA_ADMIN:           "bg-[#ffe8e8] text-[#c0112a]",
  NCA_OFFICER:         "bg-[#e8f1fb] text-[#004999]",
  NCA_VIEWER:          "bg-[#eef2ff] text-[#3949ab]",
  PROVIDER_DATA_ENTRY: "bg-[#f2f4f6] text-[#43474f]",
  PROVIDER_APPROVER:   "bg-[#e5f4eb] text-[#1f7a4d]",
};

const ROLE_LABELS: Record<UserRole, string> = {
  NCA_ADMIN:           "System Admin",
  NCA_OFFICER:         "NCA Officer",
  NCA_VIEWER:          "Data Requester",
  PROVIDER_DATA_ENTRY: "Data Entry",
  PROVIDER_APPROVER:   "Approver",
};

interface NewUserForm {
  name: string; email: string; password: string;
  role: UserRole; organization: string; division: string; grade: string;
}

interface ToggleActiveResponse {
  is_active: boolean;
  email: string;
}

const EMPTY: NewUserForm = { name:"", email:"", password:"", role:"NCA_OFFICER", organization:"", division:"", grade:"" };

const inp = "w-full rounded-[8px] border border-[#c3c6d0] px-3 py-2 text-[13px] text-[#191c1e] focus:border-[#0066cc] focus:outline-none focus:ring-2 focus:ring-[#0066cc]/20";
const lbl = "block text-[11px] font-semibold uppercase tracking-wide text-[#737780] mb-1";

function UsersPageContent() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const searchParams = useSearchParams();
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState<NewUserForm>(EMPTY);
  const [newDivision, setNewDivision] = useState("");
  const [filterRole, setFilterRole] = useState(searchParams.get("role") ?? "");
  const [resetUser, setResetUser] = useState<User | null>(null);
  const [temporaryPassword, setTemporaryPassword] = useState("");

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

  const { data: divisionsData } = useQuery<{ results: NCADivision[] }>({
    queryKey: ["nca-divisions"],
    queryFn: () => api("/nca-divisions/"),
  });

  const createMut = useMutation({
    mutationFn: () => api("/auth/users/", {
      method: "POST",
      body: JSON.stringify({
        name: form.name, email: form.email, password: form.password,
        role: form.role, organization_id: form.organization || null,
        division_id: form.role === "NCA_VIEWER" ? Number(form.division) : null,
        grade: form.role === "NCA_VIEWER" ? form.grade : "",
      }),
    }),
    onSuccess: () => {
      toast("User created.", "success");
      setShowCreate(false); setForm(EMPTY);
      qc.invalidateQueries({ queryKey: ["users"] });
    },
    onError: () => toast("Failed to create user. Check that the email is unique.", "error"),
  });

  const createDivisionMut = useMutation({
    mutationFn: () => api("/nca-divisions/", {
      method: "POST",
      body: JSON.stringify({ name: newDivision.trim(), code: newDivision.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") }),
    }),
    onSuccess: () => { setNewDivision(""); qc.invalidateQueries({ queryKey: ["nca-divisions"] }); toast("Division added.", "success"); },
    onError: () => toast("Could not add division. Check that its name is unique.", "error"),
  });

  const toggleActiveMut = useMutation({
    mutationFn: (userId: string) =>
      api<ToggleActiveResponse>(`/auth/users/${userId}/toggle-active/`, { method: "POST" }),
    onSuccess: (data) => {
      toast(`${data.email} ${data.is_active ? "activated" : "deactivated"}.`, data.is_active ? "success" : "warning");
      qc.invalidateQueries({ queryKey: ["users"] });
    },
    onError: () => toast("Failed to update user.", "error"),
  });

  const resetPasswordMut = useMutation({
    mutationFn: () => api(`/auth/users/${resetUser?.id}/reset-password/`, {
      method: "POST",
      body: JSON.stringify({ temporary_password: temporaryPassword }),
    }),
    onSuccess: () => {
      toast("Temporary password issued. The user must change it at next sign-in.", "success");
      setResetUser(null); setTemporaryPassword("");
    },
    onError: (error: Error) => toast(error.message || "Password could not be reset.", "error"),
  });

  const users = data?.results ?? [];
  const isProviderRole = (role: UserRole) => role.startsWith("PROVIDER_");

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[28px] font-semibold text-[#191c1e]">User Management</h1>
          <p className="mt-1 text-[14px] text-[#43474f]">
            Create and manage accounts for all five roles. All actions are audited.
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
      <div className="rounded-[16px] border border-[#eceef0] bg-white p-5">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div><h2 className="text-[15px] font-semibold">NCA divisions</h2><p className="mt-1 text-[12px] text-[#737780]">Managed values used when creating data requester accounts.</p></div>
          <form className="flex gap-2" onSubmit={e => { e.preventDefault(); if(newDivision.trim()) createDivisionMut.mutate(); }}>
            <input className={inp} required value={newDivision} onChange={e => setNewDivision(e.target.value)} placeholder="Division name" />
            <button disabled={createDivisionMut.isPending} className="shrink-0 rounded-[8px] bg-[#0066cc] px-4 py-2 text-[13px] font-semibold text-white">Add division</button>
          </form>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">{(divisionsData?.results ?? []).map(d => <span key={d.id} className={`rounded-full px-3 py-1 text-[12px] ${d.is_active?"bg-[#e8f1fb] text-[#004999]":"bg-[#f2f4f6] text-[#737780]"}`}>{d.name}</span>)}</div>
      </div>
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
                onChange={e => setForm(f => ({ ...f, role: e.target.value as UserRole, organization: "", division: "", grade: "" }))}>
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
                  {(providersData?.results ?? []).filter(p => p.organization_id).map(p => (
                    <option key={p.id} value={p.organization_id ?? ""}>
                      {p.registered_name} ({PROVIDER_CATEGORY_LABELS[p.category]})
                    </option>
                  ))}
                </select>
                <p className="text-[11px] text-[#737780] mt-1">Provider users only see data belonging to their organisation.</p>
              </div>
            ) : (
              <div>
                <label className={lbl}>Organisation</label>
                <input className={inp} value="NCA" disabled />
              </div>
            )}
            {form.role === "NCA_VIEWER" && <>
              <div>
                <label className={lbl}>NCA Division</label>
                <select className={inp} required value={form.division} onChange={e => setForm(f => ({ ...f, division: e.target.value }))}>
                  <option value="">Select division…</option>
                  {(divisionsData?.results ?? []).filter(d => d.is_active).map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
                </select>
              </div>
              <div>
                <label className={lbl}>Grade</label>
                <input className={inp} required value={form.grade} onChange={e => setForm(f => ({ ...f, grade: e.target.value }))} placeholder="e.g. Principal Manager" />
              </div>
            </>}
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

      {resetUser && (
        <form onSubmit={e => { e.preventDefault(); resetPasswordMut.mutate(); }} className="rounded-[16px] border border-[#0066cc]/30 bg-[#f4f8fd] p-5">
          <div className="flex flex-wrap items-end gap-4">
            <div className="min-w-[260px] flex-1">
              <h2 className="text-[15px] font-semibold">Reset password for {resetUser.name}</h2>
              <p className="mt-1 text-[12px] text-[#737780]">Set a temporary password. No forms, submissions, provider information or other portal data will be changed.</p>
              <label className={`${lbl} mt-4`}>Temporary password</label>
              <input type="password" required minLength={8} autoComplete="new-password" className={inp} value={temporaryPassword} onChange={e => setTemporaryPassword(e.target.value)} />
            </div>
            <button type="button" onClick={() => { setResetUser(null); setTemporaryPassword(""); }} className="rounded-[8px] border border-[#c3c6d0] bg-white px-4 py-2 text-[13px]">Cancel</button>
            <button type="submit" disabled={resetPasswordMut.isPending} className="rounded-[8px] bg-[#002d5b] px-4 py-2 text-[13px] font-semibold text-white disabled:opacity-50">{resetPasswordMut.isPending ? "Resetting…" : "Issue temporary password"}</button>
          </div>
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
                    {u.role === "NCA_VIEWER" ? `${u.division?.name ?? "Profile incomplete"}${u.grade ? ` · ${u.grade}` : ""}` : (u.organization?.name ?? "NCA")}
                  </td>
                  <td className="px-5 py-3.5">
                    <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${u.is_active ? "bg-[#e5f4eb] text-[#1f7a4d]" : "bg-[#f2f4f6] text-[#737780]"}`}>
                      {u.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-3"><button type="button" onClick={() => { setResetUser(u); setTemporaryPassword(""); }} className="text-[12px] font-medium text-[#0066cc] hover:underline">Reset password</button><button
                      onClick={() => toggleActiveMut.mutate(u.id)}
                      disabled={toggleActiveMut.isPending}
                      className="text-[12px] font-medium text-[#0066cc] hover:underline disabled:opacity-50">
                      {u.is_active ? "Deactivate" : "Reactivate"}
                    </button></div>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function UsersPage() {
  return (
    <Suspense fallback={null}>
      <UsersPageContent />
    </Suspense>
  );
}

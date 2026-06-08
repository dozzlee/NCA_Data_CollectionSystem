"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import type { ReportingPeriod, Frequency } from "@/lib/types";

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "bg-[#f2f4f6] text-[#43474f]",
  ACTIVE: "bg-[#e5f4eb] text-[#1f7a4d]",
  CLOSED: "bg-[#ffe8e8] text-[#c0112a]",
};

const FREQUENCIES: Frequency[] = ["MONTHLY", "SEMI_ANNUAL", "ANNUAL"];
const FREQ_LABELS: Record<Frequency, string> = {
  MONTHLY: "Monthly",
  SEMI_ANNUAL: "Semi-Annual",
  ANNUAL: "Annual",
};

interface CreatePeriodForm {
  name: string;
  frequency: Frequency;
  year: string;
  month: string;
  opens_at: string;
  due_at: string;
}

const EMPTY_FORM: CreatePeriodForm = {
  name: "", frequency: "ANNUAL", year: String(new Date().getFullYear()),
  month: "", opens_at: "", due_at: "",
};

export default function PeriodsPage() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState<CreatePeriodForm>(EMPTY_FORM);

  const { data, isLoading } = useQuery<{ results: ReportingPeriod[] }>({
    queryKey: ["periods"],
    queryFn: () => api("/periods/?ordering=-year"),
  });

  const createMutation = useMutation({
    mutationFn: (data: Partial<ReportingPeriod>) =>
      api("/periods/", { method: "POST", body: JSON.stringify(data) }),
    onSuccess: () => {
      toast("Period created.", "success");
      setShowCreate(false);
      setForm(EMPTY_FORM);
      qc.invalidateQueries({ queryKey: ["periods"] });
    },
    onError: () => toast("Failed to create period.", "error"),
  });

  function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    createMutation.mutate({
      name: form.name,
      frequency: form.frequency,
      year: Number(form.year),
      month: form.month ? Number(form.month) : null,
      opens_at: form.opens_at,
      due_at: form.due_at,
      status: "DRAFT",
    } as unknown as Partial<ReportingPeriod>);
  }

  const periods = data?.results ?? [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-[28px] font-semibold text-[#191c1e]">Reporting Periods</h1>
          <p className="mt-1 text-[14px] text-[#43474f]">Manage data collection windows and submission deadlines.</p>
        </div>
        <button
          onClick={() => setShowCreate((v) => !v)}
          className="rounded-[8px] bg-[#001836] px-4 py-2 text-[13px] font-semibold text-white transition-colors hover:bg-[#002d5b]"
        >
          {showCreate ? "Cancel" : "+ New Period"}
        </button>
      </div>

      {/* Create form */}
      {showCreate && (
        <form
          onSubmit={handleCreate}
          className="rounded-[16px] border border-[#eceef0] bg-white p-6 space-y-4"
        >
          <h2 className="text-[16px] font-semibold text-[#191c1e]">New Reporting Period</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[
              { key: "name", label: "Period Name", type: "text", placeholder: "e.g. Q1 2026 Annual" },
              { key: "year", label: "Year", type: "number", placeholder: "2026" },
              { key: "opens_at", label: "Opens At", type: "datetime-local", placeholder: "" },
              { key: "due_at", label: "Due At", type: "datetime-local", placeholder: "" },
            ].map(({ key, label, type, placeholder }) => (
              <div key={key}>
                <label className="text-[11px] font-semibold uppercase tracking-wide text-[#737780]">{label}</label>
                <input
                  type={type}
                  value={(form as Record<string, string>)[key]}
                  onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                  placeholder={placeholder}
                  required={key !== "month"}
                  className="mt-1 w-full rounded-[8px] border border-[#c3c6d0] px-3 py-2 text-[13px] text-[#191c1e] focus:border-[#0066cc] focus:outline-none focus:ring-2 focus:ring-[#0066cc]/20"
                />
              </div>
            ))}
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wide text-[#737780]">Frequency</label>
              <select
                value={form.frequency}
                onChange={(e) => setForm((f) => ({ ...f, frequency: e.target.value as Frequency }))}
                className="mt-1 w-full rounded-[8px] border border-[#c3c6d0] px-3 py-2 text-[13px] text-[#191c1e] focus:border-[#0066cc] focus:outline-none"
              >
                {FREQUENCIES.map((f) => (
                  <option key={f} value={f}>{FREQ_LABELS[f]}</option>
                ))}
              </select>
            </div>
            {form.frequency === "MONTHLY" && (
              <div>
                <label className="text-[11px] font-semibold uppercase tracking-wide text-[#737780]">Month (1–12)</label>
                <input
                  type="number"
                  min={1} max={12}
                  value={form.month}
                  onChange={(e) => setForm((f) => ({ ...f, month: e.target.value }))}
                  className="mt-1 w-full rounded-[8px] border border-[#c3c6d0] px-3 py-2 text-[13px] text-[#191c1e] focus:border-[#0066cc] focus:outline-none"
                />
              </div>
            )}
          </div>
          <button
            type="submit"
            disabled={createMutation.isPending}
            className="rounded-[8px] bg-[#001836] px-5 py-2.5 text-[13px] font-semibold text-white hover:bg-[#002d5b] disabled:opacity-50"
          >
            {createMutation.isPending ? "Creating…" : "Create Period"}
          </button>
        </form>
      )}

      {/* Periods list */}
      <div className="rounded-[16px] border border-[#eceef0] bg-white overflow-hidden">
        <table className="w-full text-left">
          <thead className="border-b border-[#eceef0] bg-[#f7f9fb]">
            <tr>
              {["Period", "Frequency", "Opens", "Due", "Status", ""].map((h) => (
                <th key={h} className="px-5 py-3 text-[11px] font-semibold uppercase tracking-wide text-[#43474f]">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[#eceef0]">
            {isLoading
              ? Array.from({ length: 4 }).map((_, i) => (
                  <tr key={i}>
                    {Array.from({ length: 6 }).map((_, j) => (
                      <td key={j} className="px-5 py-4"><Skeleton className="h-3.5 w-full" /></td>
                    ))}
                  </tr>
                ))
              : periods.length === 0
              ? (
                <tr>
                  <td colSpan={6} className="px-5 py-10 text-center text-[14px] text-[#737780]">
                    No periods yet. Create one to get started.
                  </td>
                </tr>
              )
              : periods.map((p) => (
                <tr key={p.id} className="hover:bg-[#f7f9fb] transition-colors">
                  <td className="px-5 py-3.5">
                    <p className="text-[13px] font-medium text-[#191c1e]">{p.name}</p>
                    <p className="text-[11px] text-[#737780]">{p.year}{p.month ? ` / M${p.month}` : ""}</p>
                  </td>
                  <td className="px-5 py-3.5 text-[13px] text-[#43474f]">{FREQ_LABELS[p.frequency]}</td>
                  <td className="px-5 py-3.5 text-[13px] text-[#43474f]">
                    {new Date(p.opens_at).toLocaleDateString("en-GB")}
                  </td>
                  <td className="px-5 py-3.5 text-[13px] text-[#43474f]">
                    {new Date(p.due_at).toLocaleDateString("en-GB")}
                  </td>
                  <td className="px-5 py-3.5">
                    <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${STATUS_COLORS[p.status]}`}>
                      {p.status}
                    </span>
                  </td>
                  <td className="px-5 py-3.5">
                    <Link
                      href={`/periods/${p.id}`}
                      className="text-[13px] font-medium text-[#0066cc] hover:underline"
                    >
                      View →
                    </Link>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

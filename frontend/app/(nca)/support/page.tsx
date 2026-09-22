"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Skeleton } from "@/components/ui/Skeleton";

type Ticket = { id: number; title: string; description: string; severity: string; status: string; reporter_name: string; assigned_to_name: string; assigned_team: string; reported_at: string; sla_due_at: string | null; resolution_note: string };
type Feedback = { id: number; submitted_by_name: string; submitted_by_email: string; organization: string; category_label: string; subject: string; message: string; submitted_at: string; acknowledged: boolean; acknowledged_at: string | null };
type Tab = "support" | "feedback";

export default function SupportPage() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("support");
  const tickets = useQuery<Ticket[]>({ queryKey: ["support-tickets"], queryFn: () => api.get("/issues/") });
  const feedback = useQuery<Feedback[]>({ queryKey: ["provider-feedback"], queryFn: () => api.get("/feedback/"), enabled: tab === "feedback" });
  const acknowledge = useMutation({
    mutationFn: (id: number) => api.post(`/feedback/${id}/acknowledge/`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["provider-feedback"] }),
  });

  async function act(id: number, action: string) {
    const note = ["UPDATE", "RESOLVE"].includes(action) ? window.prompt(action === "RESOLVE" ? "Resolution note" : "Requester update") : "";
    if (["UPDATE", "RESOLVE"].includes(action) && !note?.trim()) return;
    await api.post(`/issues/${id}/actions/`, { action, note });
    await qc.invalidateQueries({ queryKey: ["support-tickets"] });
  }

  return <div className="space-y-5">
    <div><h1 className="text-[22px] font-semibold text-[#191c1e]">NCA Support</h1><p className="mt-1 text-[13px] text-[#737780]">Review provider feedback or manage technical support tickets.</p></div>
    <div className="flex w-fit overflow-hidden rounded-[8px] border border-[#c3c6d0]" role="tablist" aria-label="Support views">
      <button role="tab" aria-selected={tab === "feedback"} onClick={() => setTab("feedback")} className={`px-5 py-2 text-[13px] font-medium ${tab === "feedback" ? "bg-[#001836] text-white" : "bg-white text-[#43474f]"}`}>Feedback</button>
      <button role="tab" aria-selected={tab === "support"} onClick={() => setTab("support")} className={`px-5 py-2 text-[13px] font-medium ${tab === "support" ? "bg-[#001836] text-white" : "bg-white text-[#43474f]"}`}>Support Queue</button>
    </div>

    {tab === "support" && <section role="tabpanel" className="space-y-4">
      <div><h2 className="text-[16px] font-semibold">Support Queue</h2><p className="mt-1 text-[12px] text-[#737780]">Internal ownership, acknowledgement, SLA and resolution history.</p></div>
      {tickets.isLoading ? <Skeleton className="h-64 w-full" /> : <div className="overflow-hidden rounded-[14px] border border-[#e6e8ea] bg-white"><div className="divide-y divide-[#f2f4f6]">
        {(tickets.data ?? []).map(ticket => <div key={ticket.id} className="p-5"><div className="flex items-start gap-4"><div className="flex-1"><div className="flex items-center gap-2"><p className="text-[13px] font-semibold">#{ticket.id} {ticket.title}</p><span className="rounded bg-[#f2f4f6] px-2 py-0.5 text-[10px]">{ticket.severity}</span><span className="text-[10px] font-semibold text-[#0066cc]">{ticket.status}</span></div><p className="mt-1 text-[12px] text-[#43474f]">{ticket.description}</p><p className="mt-2 text-[10px] text-[#737780]">Reported by {ticket.reporter_name} · Team {ticket.assigned_team || "Unassigned"} · SLA {ticket.sla_due_at ? new Date(ticket.sla_due_at).toLocaleString() : "Not set"}</p></div><div className="flex gap-1.5"><button onClick={() => act(ticket.id,"ACKNOWLEDGE")} className="rounded border px-2 py-1 text-[10px]">Acknowledge</button><button onClick={() => act(ticket.id,"UPDATE")} className="rounded border px-2 py-1 text-[10px]">Update</button><button onClick={() => act(ticket.id,"RESOLVE")} className="rounded border border-[#1f7a4d] px-2 py-1 text-[10px] text-[#1f7a4d]">Resolve</button></div></div></div>)}
        {!tickets.data?.length && <p className="p-10 text-center text-[13px] text-[#737780]">No support tickets.</p>}
      </div></div>}
    </section>}

    {tab === "feedback" && <section role="tabpanel" className="space-y-4">
      <div><h2 className="text-[16px] font-semibold">Provider feedback</h2><p className="mt-1 text-[12px] text-[#737780]">Feedback is collected and acknowledged; it is not managed as a technical support ticket.</p></div>
      {feedback.isLoading && <Skeleton className="h-64 w-full" />}
      {feedback.isError && <div className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-700">Feedback could not be loaded. <button className="font-semibold underline" onClick={() => feedback.refetch()}>Retry</button></div>}
      {!feedback.isLoading && !feedback.isError && <div className="overflow-x-auto rounded-[14px] border border-[#e6e8ea] bg-white"><table className="w-full min-w-[980px] text-left text-[12px]"><thead className="bg-[#f7f9fb] text-[10px] uppercase text-[#737780]"><tr><th className="px-4 py-3">Feedback ID</th><th className="px-4 py-3">Submitted by</th><th className="px-4 py-3">Provider</th><th className="px-4 py-3">Category</th><th className="px-4 py-3">Feedback</th><th className="px-4 py-3">Submitted</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Action</th></tr></thead><tbody className="divide-y divide-[#eceef0]">{(feedback.data ?? []).map(item => <tr key={item.id} className="align-top"><td className="px-4 py-4 font-semibold">#{item.id}</td><td className="px-4 py-4"><p className="font-medium">{item.submitted_by_name}</p><p className="text-[10px] text-[#737780]">{item.submitted_by_email}</p></td><td className="px-4 py-4">{item.organization || "—"}</td><td className="px-4 py-4">{item.category_label}</td><td className="max-w-md px-4 py-4"><p className="font-semibold">{item.subject}</p><p className="mt-1 whitespace-pre-wrap text-[#43474f]">{item.message}</p></td><td className="whitespace-nowrap px-4 py-4">{new Date(item.submitted_at).toLocaleString()}</td><td className="px-4 py-4"><span className={`rounded-full px-2 py-1 text-[10px] font-semibold ${item.acknowledged ? "bg-green-50 text-green-700" : "bg-amber-50 text-amber-700"}`}>{item.acknowledged ? "Received" : "Awaiting receipt"}</span>{item.acknowledged_at && <p className="mt-2 text-[10px] text-[#737780]">{new Date(item.acknowledged_at).toLocaleString()}</p>}</td><td className="px-4 py-4">{item.acknowledged ? <span className="text-[11px] text-[#737780]">Provider notified</span> : <button disabled={acknowledge.isPending} onClick={() => acknowledge.mutate(item.id)} className="whitespace-nowrap rounded-[7px] bg-[#001836] px-3 py-2 text-[11px] font-semibold text-white disabled:opacity-50">Notify provider received</button>}</td></tr>)}</tbody></table>{!feedback.data?.length && <p className="p-10 text-center text-[13px] text-[#737780]">No provider feedback submitted yet.</p>}</div>}
    </section>}
  </div>;
}

"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Skeleton } from "@/components/ui/Skeleton";

type Ticket = { id: number; title: string; description: string; severity: string; status: string; reporter_name: string;
  assigned_to_name: string; assigned_team: string; reported_at: string; sla_due_at: string | null; resolution_note: string };

export default function SupportPage() {
  const qc = useQueryClient();
  const query = useQuery<Ticket[]>({ queryKey: ["support-tickets"], queryFn: () => api.get("/issues/") });
  async function act(id: number, action: string) {
    const note = ["UPDATE", "RESOLVE"].includes(action) ? window.prompt(action === "RESOLVE" ? "Resolution note" : "Requester update") : "";
    if (["UPDATE", "RESOLVE"].includes(action) && !note?.trim()) return;
    await api.post(`/issues/${id}/actions/`, { action, note });
    await qc.invalidateQueries({ queryKey: ["support-tickets"] });
  }
  if (query.isLoading) return <Skeleton className="h-64 w-full" />;
  return <div className="space-y-5">
    <div><h1 className="text-[22px] font-semibold text-[#191c1e]">Support Queue</h1><p className="mt-1 text-[13px] text-[#737780]">Internal ownership, acknowledgement, SLA and resolution history.</p></div>
    <div className="overflow-hidden rounded-[14px] border border-[#e6e8ea] bg-white">
      <div className="divide-y divide-[#f2f4f6]">
        {(query.data ?? []).map(ticket => <div key={ticket.id} className="p-5">
          <div className="flex items-start gap-4"><div className="flex-1"><div className="flex items-center gap-2"><p className="text-[13px] font-semibold">#{ticket.id} {ticket.title}</p><span className="rounded bg-[#f2f4f6] px-2 py-0.5 text-[10px]">{ticket.severity}</span><span className="text-[10px] font-semibold text-[#0066cc]">{ticket.status}</span></div>
          <p className="mt-1 text-[12px] text-[#43474f]">{ticket.description}</p><p className="mt-2 text-[10px] text-[#737780]">Reported by {ticket.reporter_name} · Team {ticket.assigned_team || "Unassigned"} · SLA {ticket.sla_due_at ? new Date(ticket.sla_due_at).toLocaleString() : "Not set"}</p></div>
          <div className="flex gap-1.5"><button onClick={() => act(ticket.id,"ACKNOWLEDGE")} className="rounded border px-2 py-1 text-[10px]">Acknowledge</button><button onClick={() => act(ticket.id,"UPDATE")} className="rounded border px-2 py-1 text-[10px]">Update</button><button onClick={() => act(ticket.id,"RESOLVE")} className="rounded border border-[#1f7a4d] px-2 py-1 text-[10px] text-[#1f7a4d]">Resolve</button></div></div>
        </div>)}
        {!query.data?.length && <p className="p-10 text-center text-[13px] text-[#737780]">No support tickets.</p>}
      </div>
    </div>
  </div>;
}

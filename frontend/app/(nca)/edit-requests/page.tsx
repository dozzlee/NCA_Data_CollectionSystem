"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { EditRequest, PaginatedResponse } from "@/lib/types";

export default function NCAEditRequestsPage() {
  const qc = useQueryClient();
  const [notes, setNotes] = useState<Record<number, string>>({});
  const query = useQuery({ queryKey: ["nca-edit-requests"], queryFn: () => api.get<PaginatedResponse<EditRequest>>("/edit-requests/") });
  const decide = useMutation({
    mutationFn: ({ id, decision }: { id: number; decision: "approve" | "deny" }) => api.post(`/edit-requests/${id}/${decision}/`, { decision_note: notes[id] ?? "" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["nca-edit-requests"] }),
  });
  return <div className="space-y-6">
    <div><h1 className="text-[28px] font-semibold">Provider Edit Requests</h1><p className="text-[13px] text-[#737780]">Approve or deny requests to reopen official submissions.</p></div>
    {(query.data?.results ?? []).map((item) => <section key={item.id} className="rounded-[14px] border bg-white p-5">
      <div className="flex justify-between"><div><h2 className="text-[14px] font-semibold">{item.provider_name} · {item.form_name}</h2><p className="text-[11px] text-[#737780]">{item.period_name} · Version {item.version}</p></div><span className="text-[11px] font-bold">{item.status}</span></div>
      <p className="mt-3 text-[13px]">{item.reason}</p>
      {item.status === "PENDING" ? <><textarea value={notes[item.id] ?? ""} onChange={(event) => setNotes((current) => ({ ...current, [item.id]: event.target.value }))} placeholder="Decision note" rows={2} className="mt-3 w-full rounded-[8px] border p-3 text-[12px]" />
        <div className="mt-3 flex justify-end gap-2"><button onClick={() => decide.mutate({ id: item.id, decision: "deny" })} className="rounded-[8px] border border-[#E31937] px-4 py-2 text-[12px] font-semibold text-[#E31937]">Deny</button><button onClick={() => decide.mutate({ id: item.id, decision: "approve" })} className="rounded-[8px] bg-[#1f7a4d] px-4 py-2 text-[12px] font-semibold text-white">Approve and reopen</button></div></>
        : item.decision_note && <p className="mt-2 text-[12px] text-[#43474f]">Decision: {item.decision_note}</p>}
    </section>)}
  </div>;
}

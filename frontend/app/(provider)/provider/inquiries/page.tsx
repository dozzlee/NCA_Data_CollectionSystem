"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";
import type { User } from "@/lib/types";

const CATEGORIES = [
  { value:"GENERAL",    label:"General Question" },
  { value:"BUG",        label:"Technical Issue / Bug" },
  { value:"USABILITY",  label:"Usability Feedback" },
  { value:"FEATURE",    label:"Feature Request" },
  { value:"OTHER",      label:"Other" },
];

const SEVERITIES = [
  { value:"LOW",      label:"Low — not blocking" },
  { value:"MEDIUM",   label:"Medium — causing difficulty" },
  { value:"HIGH",     label:"High — blocking my submission" },
  { value:"CRITICAL", label:"Critical — system error" },
];

type Mode = "feedback" | "issue";
type FeedbackRecord = { id:number; category_label:string; subject:string; message:string; submitted_at:string; acknowledged:boolean; acknowledged_at:string|null };

const inp = "w-full rounded-[8px] border border-[#c3c6d0] bg-white px-3 py-2 text-[13px] text-[#191c1e] placeholder:text-[#737780] focus:border-[#0066cc] focus:outline-none focus:ring-2 focus:ring-[#0066cc]/20";
const lbl = "block text-[12px] font-semibold text-[#43474f] mb-1";

export default function InquiriesPage() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { data: user } = useQuery<User>({ queryKey: ["me"], queryFn: () => api("/auth/me/") });
  const isDataEntry = user?.role === "PROVIDER_DATA_ENTRY";
  const [mode, setMode] = useState<Mode>("feedback");
  const activeMode: Mode = isDataEntry ? "issue" : mode;
  const modes: Mode[] = isDataEntry ? ["issue"] : ["feedback", "issue"];
  const [feedbackForm, setFeedbackForm] = useState({ category:"GENERAL", subject:"", message:"" });
  const [issueForm, setIssueForm] = useState({ title:"", description:"", severity:"MEDIUM", page_url: typeof window !== "undefined" ? window.location.href : "" });
  const { data: issues } = useQuery<Array<{id:number;title:string;severity:string;status:string;reported_at:string;assigned_team:string;acknowledged_at:string|null;sla_due_at:string|null;resolution_note:string;history:Array<{id:number;event_type:string;note:string;actor:string;created_at:string}>}>>({ queryKey:["my-technical-issues"], queryFn:() => api("/issues/") });
  const { data: feedbackHistory } = useQuery<FeedbackRecord[]>({
    queryKey:["my-feedback"], queryFn:() => api("/feedback/"), enabled: user?.role === "PROVIDER_APPROVER",
  });

  const feedbackMut = useMutation({
    mutationFn: () => api("/feedback/", { method:"POST", body: JSON.stringify(feedbackForm) }),
    onSuccess: () => {
      toast("Feedback submitted. Thank you.", "success");
      setFeedbackForm({ category:"GENERAL", subject:"", message:"" });
      queryClient.invalidateQueries({ queryKey:["my-feedback"] });
    },
    onError: () => toast("Failed to submit. Please try again.", "error"),
  });

  const issueMut = useMutation({
    mutationFn: () => api("/issues/", { method:"POST", body: JSON.stringify({ ...issueForm, page_url: window.location.href }) }),
    onSuccess: () => {
      toast("Issue reported. The NCA technical team has been notified.", "success");
      setIssueForm({ title:"", description:"", severity:"MEDIUM", page_url:"" });
      queryClient.invalidateQueries({ queryKey:["my-technical-issues"] });
    },
    onError: () => toast("Failed to submit. Please try again.", "error"),
  });

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-[28px] font-semibold text-[#191c1e]">Inquiries & Support</h1>
        <p className="mt-1 text-[14px] text-[#43474f]">
          {isDataEntry ? "Report technical system issues. Compliance and general inquiries must be sent by your Provider Approver." : "Report a technical issue or send an authenticated inquiry to NCA."}
        </p>
      </div>

      {/* Tab toggle */}
      <div className="flex rounded-[8px] border border-[#c3c6d0] overflow-hidden w-fit">
        {modes.map(m => (
          <button key={m} onClick={() => setMode(m)}
            className={`px-5 py-2 text-[13px] font-medium transition-colors ${
              activeMode === m
                ? "bg-[#001836] text-white"
                : "bg-white text-[#43474f] hover:bg-[#f2f4f6]"
            }`}>
            {m === "feedback" ? "Send Feedback" : "Report an Issue"}
          </button>
        ))}
      </div>

      {activeMode === "feedback" ? (
        <form onSubmit={e => { e.preventDefault(); feedbackMut.mutate(); }}
          className="rounded-[16px] border border-[#eceef0] bg-white p-6 space-y-4">
          <h2 className="text-[15px] font-semibold text-[#191c1e]">Feedback</h2>

          <div>
            <label className={lbl}>Category</label>
            <select value={feedbackForm.category}
              onChange={e => setFeedbackForm(p => ({ ...p, category: e.target.value }))}
              className={inp}>
              {CATEGORIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
          </div>
          <div>
            <label className={lbl}>Subject</label>
            <input required className={inp} placeholder="Brief subject"
              value={feedbackForm.subject}
              onChange={e => setFeedbackForm(p => ({ ...p, subject: e.target.value }))} />
          </div>
          <div>
            <label className={lbl}>Message</label>
            <textarea required className={inp} rows={5} placeholder="Describe your feedback in detail…"
              value={feedbackForm.message}
              onChange={e => setFeedbackForm(p => ({ ...p, message: e.target.value }))} />
          </div>
          <button type="submit" disabled={feedbackMut.isPending}
            className="rounded-[8px] bg-[#001836] px-5 py-2.5 text-[13px] font-semibold text-white hover:bg-[#002d5b] disabled:opacity-50">
            {feedbackMut.isPending ? "Submitting…" : "Submit Feedback"}
          </button>
        </form>
      ) : (
        <form onSubmit={e => { e.preventDefault(); issueMut.mutate(); }}
          className="rounded-[16px] border border-[#eceef0] bg-white p-6 space-y-4">
          <h2 className="text-[15px] font-semibold text-[#191c1e]">Report a Technical Issue</h2>

          <div>
            <label className={lbl}>Issue Title</label>
            <input required className={inp} placeholder="e.g. Cannot save section 3 of MNO Monthly form"
              value={issueForm.title}
              onChange={e => setIssueForm(p => ({ ...p, title: e.target.value }))} />
          </div>
          <div>
            <label className={lbl}>Severity</label>
            <select value={issueForm.severity}
              onChange={e => setIssueForm(p => ({ ...p, severity: e.target.value }))}
              className={inp}>
              {SEVERITIES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
          </div>
          <div>
            <label className={lbl}>Description</label>
            <textarea required className={inp} rows={6}
              placeholder="Describe exactly what happened, what you expected, and what steps led to the issue…"
              value={issueForm.description}
              onChange={e => setIssueForm(p => ({ ...p, description: e.target.value }))} />
          </div>

          <div className="rounded-[8px] bg-[#f7f9fb] border border-[#eceef0] px-4 py-3 text-[12px] text-[#43474f]">
            <p className="font-semibold mb-0.5">Your current page URL will be included automatically.</p>
            <p>The NCA technical team will be notified and will follow up via your registered email if needed.</p>
          </div>

          <button type="submit" disabled={issueMut.isPending}
            className="rounded-[8px] bg-[#e31937] px-5 py-2.5 text-[13px] font-semibold text-white hover:bg-[#c0112a] disabled:opacity-50">
            {issueMut.isPending ? "Reporting…" : "Report Issue"}
          </button>
        </form>
      )}

      <section className="rounded-2xl border bg-white p-6">
        <h2 className="font-semibold">My technical issues</h2><p className="mt-1 text-xs text-[#737780]">Status and updates from the existing support process.</p>
        <div className="mt-4 space-y-3">{!issues?.length ? <p className="rounded-lg bg-[#f7f9fb] p-4 text-sm text-[#737780]">No technical issues reported yet.</p> : issues.map((issue) => <details key={issue.id} className="rounded-lg border p-4"><summary className="cursor-pointer list-none"><div className="flex items-center justify-between gap-3"><div><p className="text-sm font-medium">#{issue.id} · {issue.title}</p><p className="mt-1 text-xs text-[#737780]">Reported {new Date(issue.reported_at).toLocaleString()} · {issue.severity}</p></div><span className="rounded-full bg-[#e8f1fb] px-2 py-1 text-xs font-semibold text-[#004999]">{issue.status.replaceAll("_", " ")}</span></div></summary><div className="mt-4 border-t pt-3 text-xs text-[#43474f]"><p>Assigned team: {issue.assigned_team || "Awaiting assignment"}</p>{issue.sla_due_at && <p>SLA target: {new Date(issue.sla_due_at).toLocaleString()}</p>}{issue.resolution_note && <p className="mt-2 rounded bg-green-50 p-2">Resolution: {issue.resolution_note}</p>}<div className="mt-3 space-y-2">{issue.history.map((event) => <div key={event.id}><strong>{event.event_type.replaceAll("_", " ")}</strong> · {event.actor} · {new Date(event.created_at).toLocaleString()}<p>{event.note}</p></div>)}</div></div></details>)}</div>
      </section>

      {!isDataEntry && <section className="rounded-2xl border bg-white p-6">
        <h2 className="font-semibold">My feedback</h2>
        <p className="mt-1 text-xs text-[#737780]">See whether NCA has received your submitted feedback.</p>
        <div className="mt-4 space-y-3">{!feedbackHistory?.length ? <p className="rounded-lg bg-[#f7f9fb] p-4 text-sm text-[#737780]">No feedback submitted yet.</p> : feedbackHistory.map((item) => <div key={item.id} className="rounded-lg border p-4"><div className="flex items-start justify-between gap-4"><div><p className="text-sm font-semibold">#{item.id} · {item.subject}</p><p className="mt-1 text-xs text-[#737780]">{item.category_label} · Submitted {new Date(item.submitted_at).toLocaleString()}</p></div><span className={`whitespace-nowrap rounded-full px-2 py-1 text-xs font-semibold ${item.acknowledged ? "bg-green-50 text-green-700" : "bg-amber-50 text-amber-700"}`}>{item.acknowledged ? "Received by NCA" : "Awaiting receipt"}</span></div><p className="mt-3 whitespace-pre-wrap text-sm text-[#43474f]">{item.message}</p>{item.acknowledged_at && <p className="mt-2 text-xs text-[#737780]">Acknowledged {new Date(item.acknowledged_at).toLocaleString()}</p>}</div>)}</div>
      </section>}
    </div>
  );
}

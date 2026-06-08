"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/Toast";

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

const inp = "w-full rounded-[8px] border border-[#c3c6d0] bg-white px-3 py-2 text-[13px] text-[#191c1e] placeholder:text-[#737780] focus:border-[#0066cc] focus:outline-none focus:ring-2 focus:ring-[#0066cc]/20";
const lbl = "block text-[12px] font-semibold text-[#43474f] mb-1";

export default function InquiriesPage() {
  const { toast } = useToast();
  const [mode, setMode] = useState<Mode>("feedback");
  const [feedbackForm, setFeedbackForm] = useState({ category:"GENERAL", subject:"", message:"" });
  const [issueForm, setIssueForm] = useState({ title:"", description:"", severity:"MEDIUM", page_url: typeof window !== "undefined" ? window.location.href : "" });

  const feedbackMut = useMutation({
    mutationFn: () => api("/feedback/", { method:"POST", body: JSON.stringify(feedbackForm) }),
    onSuccess: () => {
      toast("Feedback submitted. Thank you.", "success");
      setFeedbackForm({ category:"GENERAL", subject:"", message:"" });
    },
    onError: () => toast("Failed to submit. Please try again.", "error"),
  });

  const issueMut = useMutation({
    mutationFn: () => api("/issues/", { method:"POST", body: JSON.stringify({ ...issueForm, page_url: window.location.href }) }),
    onSuccess: () => {
      toast("Issue reported. The NCA technical team has been notified.", "success");
      setIssueForm({ title:"", description:"", severity:"MEDIUM", page_url:"" });
    },
    onError: () => toast("Failed to submit. Please try again.", "error"),
  });

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-[28px] font-semibold text-[#191c1e]">Inquiries & Support</h1>
        <p className="mt-1 text-[14px] text-[#43474f]">
          Report a technical issue or send feedback to NCA. Our team will follow up if needed.
        </p>
      </div>

      {/* Tab toggle */}
      <div className="flex rounded-[8px] border border-[#c3c6d0] overflow-hidden w-fit">
        {(["feedback","issue"] as Mode[]).map(m => (
          <button key={m} onClick={() => setMode(m)}
            className={`px-5 py-2 text-[13px] font-medium transition-colors ${
              mode === m
                ? "bg-[#001836] text-white"
                : "bg-white text-[#43474f] hover:bg-[#f2f4f6]"
            }`}>
            {m === "feedback" ? "Send Feedback" : "Report an Issue"}
          </button>
        ))}
      </div>

      {mode === "feedback" ? (
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
    </div>
  );
}

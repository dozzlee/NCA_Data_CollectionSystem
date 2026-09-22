"use client";

import { useEffect, useState } from "react";
import { Copy, ExternalLink, X } from "lucide-react";
import { api } from "@/lib/api";

export interface EmailHandoff {
  id:number;
  event:number;
  submission:number;
  action:string;
  recipients:Array<{email:string;name:string;role?:string}>;
  subject:string;
  body:string;
  status:"AVAILABLE"|"OPENED"|"DEFERRED";
}

export function EmailHandoffModal({submissionId,eventId,onClose}:{submissionId:number;eventId:number;onClose:()=>void}) {
  const [draft,setDraft]=useState<EmailHandoff|null>(null);
  const [error,setError]=useState("");
  const [copied,setCopied]=useState<"subject"|"message"|null>(null);
  useEffect(()=>{let active=true;api.post<EmailHandoff>(`/submissions/${submissionId}/communications/email-handoff/`,{event_id:eventId}).then(value=>{if(!active)return;setDraft(value);}).catch(value=>active&&setError(value instanceof Error?value.message:"The email draft could not be prepared."));return()=>{active=false};},[eventId,submissionId]);
  async function updateStatus(status:"OPENED"|"DEFERRED") { if(!draft)return; try{await api.patch(`/submissions/${submissionId}/communications/email-handoff/${draft.id}/`,{status});}catch{/* Handoff remains optional and must never affect the completed action. */} }
  async function copy(value:string,kind:"subject"|"message"){
    try {
      let copiedSuccessfully=false;
      if (navigator.clipboard?.writeText) {
        try { await navigator.clipboard.writeText(value); copiedSuccessfully=true; } catch { /* Use the legacy fallback below. */ }
      }
      if (!copiedSuccessfully) {
        const node=document.createElement("textarea");node.value=value;node.setAttribute("readonly","");node.style.position="fixed";node.style.left="-9999px";node.style.opacity="0";
        document.body.appendChild(node);node.focus();node.select();copiedSuccessfully=document.execCommand("copy");node.remove();
      }
      if (!copiedSuccessfully) throw new Error("copy unavailable");
      setCopied(kind);window.setTimeout(()=>setCopied(null),1400);
    } catch { setError("Copy failed. Select the text and copy it manually; the completed action is unaffected."); }
  }
  async function openEmail(){
    if(!draft)return;
    await updateStatus("OPENED");
    const recipients=draft.recipients.map(item=>encodeURIComponent(item.email)).join(",");
    const query=`subject=${encodeURIComponent(draft.subject)}&body=${encodeURIComponent(draft.body)}`;
    window.location.href=`mailto:${recipients}?${query}`;
  }
  async function defer(){await updateStatus("DEFERRED");onClose();}
  return <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/45 p-4"><div role="dialog" aria-modal="true" aria-label="Email handoff" className="max-h-[92vh] w-full max-w-3xl overflow-y-auto rounded-2xl bg-white shadow-2xl">
    <header className="flex items-start justify-between border-b p-5"><div><h2 className="text-lg font-semibold">Action completed successfully</h2><p className="mt-1 text-sm text-[#43474f]">The portal action and internal notification are complete. This external email has not been sent.</p></div><button type="button" onClick={defer} aria-label="Close"><X size={18}/></button></header>
    <div className="space-y-4 p-5">{error?<div className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">{error}<p className="mt-1">You can close this window; the completed action is unaffected.</p></div>:!draft?<p className="text-sm text-[#004999]">Preparing email draft…</p>:<>
      <div className="rounded-lg border bg-[#f8fafc] p-3 text-sm text-[#191c1e]"><p className="text-xs font-semibold uppercase text-[#737780]">To</p><p className="mt-1 break-words">{draft.recipients.map(item=>item.email).join(", ")}</p></div>
      <div className="rounded-lg border bg-[#f8fafc] p-3"><div className="flex items-center justify-between gap-2"><p className="text-xs font-semibold uppercase text-[#737780]">Subject</p><button type="button" onClick={()=>copy(draft.subject,"subject")} className={`flex items-center gap-1 rounded-lg border px-3 py-1 text-xs ${copied==="subject"?"border-green-600 bg-green-50 text-green-700":"bg-white"}`} title="Copy subject" aria-live="polite">{copied==="subject"?"Copied":<><Copy size={15}/>Copy</>}</button></div><p className="mt-1 text-sm text-[#191c1e]">{draft.subject}</p></div>
      <div className="rounded-lg border bg-[#f8fafc] p-3"><div className="flex items-center justify-between gap-2"><p className="text-xs font-semibold uppercase text-[#737780]">Email body</p><button type="button" onClick={()=>copy(draft.body,"message")} className={`flex items-center gap-1 rounded-lg border px-3 py-1 text-xs ${copied==="message"?"border-green-600 bg-green-50 text-green-700":"bg-white"}`} title="Copy message" aria-live="polite">{copied==="message"?"Copied":<><Copy size={15}/>Copy</>}</button></div><pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap font-sans text-sm leading-6 text-[#191c1e]">{draft.body}</pre></div>
    </>}</div>
    <footer className="flex flex-wrap items-center justify-between gap-2 border-t p-4"><p className="text-xs text-[#737780]">You can edit the recipient, subject, and message after opening your email application.</p><div className="flex gap-2"><button type="button" onClick={defer} className="rounded-lg border px-4 py-2 text-sm">Not now</button><button type="button" disabled={!draft} onClick={openEmail} className="flex items-center gap-2 rounded-lg bg-[#002d5b] px-5 py-2 text-sm font-semibold text-white disabled:opacity-40"><ExternalLink size={15}/>Open in Email</button></div></footer>
  </div></div>;
}

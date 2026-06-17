"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { Skeleton } from "@/components/ui/Skeleton";
import { WorkflowBadge, DueStateBadge } from "@/components/ui/Badge";
import { useToast } from "@/components/ui/Toast";
import type { ProviderProfile, ExpectedSubmission } from "@/lib/types";
import { PROVIDER_CATEGORY_LABELS } from "@/lib/utils";

interface ProviderContact {
  id: number; name: string; designation: string;
  email: string; phone: string; is_active: boolean;
}
interface ProviderDetail extends ProviderProfile { contacts: ProviderContact[]; }
type Tab = "overview" | "submissions" | "contacts";

const STATUS_SNAPSHOT = [
  { key:"APPROVED",              label:"Approved",         color:"#e5f4eb", text:"#1f7a4d" },
  { key:"SUBMITTED",             label:"Submitted",        color:"#e8f1fb", text:"#004999" },
  { key:"UNDER_REVIEW",          label:"Under Review",     color:"#e8f1fb", text:"#004999" },
  { key:"CORRECTION_REQUESTED",  label:"Correction Req.",  color:"#ffe8e8", text:"#c0112a" },
  { key:"PENDING_APPROVAL",      label:"Pending Approval", color:"#fff3bf", text:"#7a5c00" },
  { key:"DRAFT",                 label:"In Progress",      color:"#f2f4f6", text:"#43474f" },
  { key:"NOT_STARTED",           label:"Not Started",      color:"#f2f4f6", text:"#737780" },
];

function Field({ label, value }: { label: string; value?: string | null }) {
  return (
    <div>
      <dt className="text-[11px] font-semibold uppercase tracking-wide text-[#737780]">{label}</dt>
      <dd className="mt-0.5 text-[14px] text-[#191c1e]">{value || <span className="text-[#737780]">—</span>}</dd>
    </div>
  );
}

export default function ProviderDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { toast } = useToast();
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("overview");
  const [editMode, setEditMode] = useState(false);
  const [form, setForm] = useState<Partial<ProviderProfile>>({});
  const [addingContact, setAddingContact] = useState(false);
  const [newContact, setNewContact] = useState({ name:"", designation:"", email:"", phone:"" });

  const { data: provider, isLoading } = useQuery<ProviderDetail>({
    queryKey: ["provider", id],
    queryFn: () => api(`/providers/${id}/`),
    onSuccess: (d: ProviderDetail) => setForm(d),
  });

  const { data: subsData, isLoading: subsLoading } = useQuery<{ results: ExpectedSubmission[] }>({
    queryKey: ["provider-submissions", id],
    queryFn: () => api(`/expected-submissions/?provider=${id}&ordering=-period__due_at`),
    enabled: !!provider,
  });

  const submissions = subsData?.results ?? [];
  const total = submissions.length;
  const approved = submissions.filter(s => s.workflow_status === "APPROVED").length;
  const overdue  = submissions.filter(s => s.due_state === "OVERDUE" && s.workflow_status !== "APPROVED").length;
  const completionRate = total ? Math.round((approved / total) * 100) : 0;

  const statusCounts: Record<string, number> = {};
  submissions.forEach(s => { statusCounts[s.workflow_status] = (statusCounts[s.workflow_status] ?? 0) + 1; });

  const updateMutation = useMutation({
    mutationFn: (data: Partial<ProviderProfile>) =>
      api(`/providers/${id}/`, { method:"PATCH", body:JSON.stringify(data) }),
    onSuccess: () => { toast("Provider updated.","success"); setEditMode(false); qc.invalidateQueries({ queryKey:["provider",id] }); },
    onError: () => toast("Failed to save changes.","error"),
  });

  const addContactMutation = useMutation({
    mutationFn: (data: typeof newContact) =>
      api(`/providers/${id}/contacts/`, { method:"POST", body:JSON.stringify(data) }),
    onSuccess: () => {
      toast("Contact added.","success"); setAddingContact(false);
      setNewContact({ name:"", designation:"", email:"", phone:"" });
      qc.invalidateQueries({ queryKey:["provider",id] });
    },
    onError: () => toast("Failed to add contact.","error"),
  });

  const inp = "w-full rounded-[8px] border border-[#c3c6d0] px-3 py-2 text-[13px] text-[#191c1e] focus:border-[#0066cc] focus:outline-none focus:ring-2 focus:ring-[#0066cc]/20";

  if (isLoading) return (
    <div className="space-y-6">
      <Skeleton className="h-8 w-64" />
      <div className="grid grid-cols-4 gap-4">{Array.from({length:4}).map((_,i)=><Skeleton key={i} className="h-20"/>)}</div>
      <div className="grid grid-cols-2 gap-4">{Array.from({length:6}).map((_,i)=><Skeleton key={i} className="h-12"/>)}</div>
    </div>
  );
  if (!provider) return <p className="text-[14px] text-[#737780]">Provider not found.</p>;

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <Link href="/providers" className="text-[13px] font-medium text-[#0066cc] hover:underline mb-2 inline-block">
            ← Back to Providers
          </Link>
          <p className="text-[13px] font-medium text-[#737780] mb-1">
            <Link href="/providers" className="hover:text-[#0066cc]">Providers</Link> /
          </p>
          <h1 className="text-[28px] font-semibold text-[#191c1e]">{provider.registered_name}</h1>
          {provider.trade_name && <p className="text-[14px] text-[#43474f]">Trading as {provider.trade_name}</p>}
          <div className="flex items-center gap-2 mt-1.5">
            <span className="rounded-full bg-[#e8f1fb] px-2.5 py-0.5 text-[11px] font-semibold text-[#004999] uppercase tracking-wide">
              {PROVIDER_CATEGORY_LABELS[provider.category]}
            </span>
            <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${
              provider.status==="ACTIVE"    ? "bg-[#e5f4eb] text-[#1f7a4d]" :
              provider.status==="SUSPENDED" ? "bg-[#fff3bf] text-[#7a5c00]" :
                                              "bg-[#f2f4f6] text-[#737780]"
            }`}>{provider.status}</span>
          </div>
        </div>
        {tab === "overview" && (
          <div className="flex gap-2">
            {editMode && (
              <button onClick={() => setEditMode(false)}
                className="rounded-[8px] border border-[#c3c6d0] px-4 py-2 text-[13px] font-medium text-[#43474f] hover:bg-[#f2f4f6]">
                Cancel
              </button>
            )}
            <button
              onClick={() => editMode ? updateMutation.mutate(form) : setEditMode(true)}
              disabled={updateMutation.isPending}
              className="rounded-[8px] bg-[#001836] px-4 py-2 text-[13px] font-semibold text-white hover:bg-[#002d5b] disabled:opacity-50">
              {editMode ? (updateMutation.isPending ? "Saving…" : "Save Changes") : "Edit Profile"}
            </button>
          </div>
        )}
      </div>

      {/* Snapshot stats — always visible at top */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          { label:"Total Submissions", value:String(total),            bg:"#f2f4f6", text:"#191c1e" },
          { label:"Approved",          value:String(approved),         bg:"#e5f4eb", text:"#1f7a4d" },
          { label:"Completion Rate",   value:`${completionRate}%`,     bg:"#e8f1fb", text:"#004999" },
          { label:"Overdue",           value:String(overdue),          bg:overdue>0?"#ffe8e8":"#f2f4f6", text:overdue>0?"#c0112a":"#737780" },
        ].map(({label,value,bg,text}) => (
          <div key={label} className="rounded-[12px] px-4 py-3 cursor-pointer" style={{background:bg}}
            onClick={() => setTab("submissions")}>
            <p className="text-[24px] font-bold" style={{color:text}}>{value}</p>
            <p className="text-[11px] font-semibold uppercase tracking-wide text-[#43474f]">{label}</p>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex border-b border-[#eceef0]">
        {([["overview","Profile & Licence"],["submissions","Submission History"],["contacts","Contacts"]] as [Tab,string][]).map(([t,label])=>(
          <button key={t} onClick={()=>setTab(t)}
            className={`px-5 py-3 text-[13px] font-medium border-b-2 transition-colors ${
              tab===t ? "border-[#001836] text-[#191c1e]" : "border-transparent text-[#737780] hover:text-[#43474f]"
            }`}>
            {label}
            {t==="submissions" && total>0 && (
              <span className="ml-1.5 rounded-full bg-[#f2f4f6] px-1.5 py-0.5 text-[10px] font-bold text-[#43474f]">{total}</span>
            )}
          </button>
        ))}
      </div>

      {/* ── Profile tab ── */}
      {tab==="overview" && (
        <div className="space-y-6">
          <div className="rounded-[16px] border border-[#eceef0] bg-white p-6">
            <h2 className="text-[15px] font-semibold text-[#191c1e] mb-5">Profile</h2>
            {editMode ? (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                {([
                  ["registered_name","Registered Name"],["trade_name","Trade Name"],
                  ["primary_email","Primary Email"],["primary_phone","Primary Phone"],
                  ["website","Website"],["physical_address","Physical Address"],
                  ["digital_address","Digital Address"],["postal_address","Postal Address"],
                ] as const).map(([key,label])=>(
                  <div key={key}>
                    <label className="text-[11px] font-semibold uppercase tracking-wide text-[#737780]">{label}</label>
                    <input type="text" className={`mt-1 ${inp}`}
                      value={(form as Record<string,string>)[key]??""}
                      onChange={e=>setForm(f=>({...f,[key]:e.target.value}))} />
                  </div>
                ))}
              </div>
            ) : (
              <dl className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
                <Field label="Primary Email"    value={provider.primary_email} />
                <Field label="Primary Phone"    value={provider.primary_phone} />
                <Field label="Website"          value={provider.website} />
                <Field label="Physical Address" value={provider.physical_address} />
                <Field label="Digital Address"  value={provider.digital_address} />
                <Field label="Postal Address"   value={provider.postal_address} />
              </dl>
            )}
          </div>
          <div className="rounded-[16px] border border-[#eceef0] bg-white p-6">
            <h2 className="text-[15px] font-semibold text-[#191c1e] mb-5">Licence</h2>
            <dl className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
              <Field label="Licence Type"   value={provider.licence_type} />
              <Field label="Licence Number" value={provider.licence_number} />
              <Field label="Issue Date"     value={provider.licence_issue_date??undefined} />
              <Field label="Expiry Date"    value={provider.licence_expiry_date??undefined} />
            </dl>
          </div>
        </div>
      )}

      {/* ── Submissions tab ── */}
      {tab==="submissions" && (
        <div className="space-y-4">
          {!subsLoading && submissions.length>0 && (
            <div className="flex flex-wrap gap-2">
              {STATUS_SNAPSHOT.map(s => {
                const count = statusCounts[s.key]??0;
                if (!count) return null;
                return (
                  <span key={s.key} className="rounded-full px-3 py-1 text-[12px] font-semibold"
                    style={{background:s.color,color:s.text}}>
                    {s.label}: {count}
                  </span>
                );
              })}
            </div>
          )}
          <div className="rounded-[16px] border border-[#eceef0] bg-white overflow-hidden">
            <table className="w-full text-left">
              <thead className="border-b border-[#eceef0] bg-[#f7f9fb]">
                <tr>
                  {["Period","Form","Due Date","Status","Due State","Officer",""].map(h=>(
                    <th key={h} className="px-5 py-3 text-[11px] font-semibold uppercase tracking-wide text-[#43474f]">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[#eceef0]">
                {subsLoading
                  ? Array.from({length:5}).map((_,i)=>(
                      <tr key={i}>{Array.from({length:7}).map((_,j)=>(
                        <td key={j} className="px-5 py-3.5"><Skeleton className="h-3.5 w-full"/></td>
                      ))}</tr>
                    ))
                  : submissions.length===0
                  ? <tr><td colSpan={7} className="px-5 py-12 text-center text-[14px] text-[#737780]">
                      No submissions yet. Submissions appear once this provider is included in an active reporting period.
                    </td></tr>
                  : submissions.map(s=>(
                    <tr key={s.id} className="hover:bg-[#f7f9fb] transition-colors">
                      <td className="px-5 py-3.5 text-[13px] font-medium text-[#191c1e]">{s.period_name}</td>
                      <td className="px-5 py-3.5">
                        <p className="text-[13px] text-[#191c1e]">{s.form_name}</p>
                        <p className="text-[11px] font-mono text-[#737780]">{s.form_code}</p>
                      </td>
                      <td className="px-5 py-3.5 text-[12px] text-[#737780]">
                        {s.due_at ? new Date(s.due_at).toLocaleDateString("en-GB",{day:"numeric",month:"short",year:"numeric"}) : "—"}
                      </td>
                      <td className="px-5 py-3.5"><WorkflowBadge status={s.workflow_status}/></td>
                      <td className="px-5 py-3.5"><DueStateBadge state={s.due_state}/></td>
                      <td className="px-5 py-3.5 text-[13px] text-[#43474f]">{s.assigned_officer_name??"—"}</td>
                      <td className="px-5 py-3.5">
                        <Link href={`/submissions/${s.id}/review`}
                          className="text-[13px] font-medium text-[#0066cc] hover:underline">Review →</Link>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Contacts tab ── */}
      {tab==="contacts" && (
        <div className="rounded-[16px] border border-[#eceef0] bg-white p-6">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-[15px] font-semibold text-[#191c1e]">Contacts</h2>
            <button onClick={()=>setAddingContact(v=>!v)}
              className="text-[13px] font-medium text-[#0066cc] hover:underline">
              {addingContact?"Cancel":"+ Add Contact"}
            </button>
          </div>
          {addingContact && (
            <div className="mb-5 rounded-[12px] border border-[#c3c6d0] bg-[#f7f9fb] p-4 space-y-3">
              <div className="grid grid-cols-2 gap-3">
                {(["name","designation","email","phone"] as const).map(f=>(
                  <input key={f} type={f==="email"?"email":"text"}
                    placeholder={f.charAt(0).toUpperCase()+f.slice(1)}
                    value={newContact[f]}
                    onChange={e=>setNewContact(c=>({...c,[f]:e.target.value}))}
                    className="rounded-[8px] border border-[#c3c6d0] px-3 py-2 text-[13px] focus:border-[#0066cc] focus:outline-none"/>
                ))}
              </div>
              <button onClick={()=>addContactMutation.mutate(newContact)}
                disabled={addContactMutation.isPending||!newContact.name||!newContact.email}
                className="rounded-[8px] bg-[#001836] px-4 py-2 text-[13px] font-semibold text-white hover:bg-[#002d5b] disabled:opacity-50">
                {addContactMutation.isPending?"Adding…":"Add Contact"}
              </button>
            </div>
          )}
          {provider.contacts.length===0
            ? <p className="text-[14px] text-[#737780]">No contacts on file.</p>
            : <div className="divide-y divide-[#eceef0]">
                {provider.contacts.map(c=>(
                  <div key={c.id} className="py-4 flex items-start justify-between gap-4">
                    <div>
                      <p className="text-[14px] font-medium text-[#191c1e]">{c.name}</p>
                      <p className="text-[12px] text-[#43474f]">{c.designation}</p>
                      <p className="text-[12px] text-[#737780]">{c.email} · {c.phone}</p>
                    </div>
                    {!c.is_active && (
                      <span className="text-[11px] font-semibold uppercase text-[#737780] bg-[#f2f4f6] px-2 py-0.5 rounded-full">Inactive</span>
                    )}
                  </div>
                ))}
              </div>
          }
        </div>
      )}
    </div>
  );
}

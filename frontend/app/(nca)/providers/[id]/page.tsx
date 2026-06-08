"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import type { ProviderProfile } from "@/lib/types";
import { PROVIDER_CATEGORY_LABELS } from "@/lib/utils";

interface ProviderContact {
  id: number;
  name: string;
  designation: string;
  email: string;
  phone: string;
  notification_role: string;
  is_active: boolean;
}

interface ProviderDetail extends ProviderProfile {
  contacts: ProviderContact[];
}

function Field({ label, value }: { label: string; value: string | null | undefined }) {
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
  const [editMode, setEditMode] = useState(false);
  const [form, setForm] = useState<Partial<ProviderProfile>>({});
  const [addingContact, setAddingContact] = useState(false);
  const [newContact, setNewContact] = useState({ name: "", designation: "", email: "", phone: "" });

  const { data: provider, isLoading } = useQuery<ProviderDetail>({
    queryKey: ["provider", id],
    queryFn: () => api(`/providers/${id}/`),
    onSuccess: (d: ProviderDetail) => setForm(d),
  });

  const updateMutation = useMutation({
    mutationFn: (data: Partial<ProviderProfile>) => api(`/providers/${id}/`, { method: "PATCH", body: JSON.stringify(data) }),
    onSuccess: () => {
      toast("Provider updated.", "success");
      setEditMode(false);
      qc.invalidateQueries({ queryKey: ["provider", id] });
    },
    onError: () => toast("Failed to save changes.", "error"),
  });

  const addContactMutation = useMutation({
    mutationFn: (data: typeof newContact) =>
      api(`/providers/${id}/contacts/`, { method: "POST", body: JSON.stringify(data) }),
    onSuccess: () => {
      toast("Contact added.", "success");
      setAddingContact(false);
      setNewContact({ name: "", designation: "", email: "", phone: "" });
      qc.invalidateQueries({ queryKey: ["provider", id] });
    },
    onError: () => toast("Failed to add contact.", "error"),
  });

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-2 gap-4">
          {Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-12" />)}
        </div>
      </div>
    );
  }

  if (!provider) return <p className="text-[14px] text-[#737780]">Provider not found.</p>;

  return (
    <div className="space-y-8 max-w-4xl">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-[28px] font-semibold text-[#191c1e]">{provider.registered_name}</h1>
          {provider.trade_name && (
            <p className="text-[14px] text-[#43474f]">Trading as {provider.trade_name}</p>
          )}
          <p className="mt-1 text-[12px] font-semibold uppercase tracking-wide text-[#0066cc]">
            {PROVIDER_CATEGORY_LABELS[provider.category]}
          </p>
        </div>
        <button
          onClick={() => (editMode ? updateMutation.mutate(form) : setEditMode(true))}
          className="rounded-[8px] bg-[#001836] px-4 py-2 text-[13px] font-semibold text-white transition-colors hover:bg-[#002d5b] disabled:opacity-50"
          disabled={updateMutation.isPending}
        >
          {editMode ? (updateMutation.isPending ? "Saving…" : "Save Changes") : "Edit Provider"}
        </button>
      </div>

      {/* Profile card */}
      <div className="rounded-[16px] border border-[#eceef0] bg-white p-6">
        <h2 className="text-[16px] font-semibold text-[#191c1e] mb-5">Profile</h2>
        {editMode ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {(
              [
                { key: "registered_name", label: "Registered Name" },
                { key: "trade_name", label: "Trade Name" },
                { key: "primary_email", label: "Primary Email" },
                { key: "primary_phone", label: "Primary Phone" },
                { key: "website", label: "Website" },
                { key: "physical_address", label: "Physical Address" },
                { key: "digital_address", label: "Digital Address" },
                { key: "postal_address", label: "Postal Address" },
              ] as const
            ).map(({ key, label }) => (
              <div key={key}>
                <label className="text-[11px] font-semibold uppercase tracking-wide text-[#737780]">{label}</label>
                <input
                  type="text"
                  value={(form as Record<string, string>)[key] ?? ""}
                  onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                  className="mt-1 w-full rounded-[8px] border border-[#c3c6d0] px-3 py-2 text-[13px] text-[#191c1e] focus:border-[#0066cc] focus:outline-none focus:ring-2 focus:ring-[#0066cc]/20"
                />
              </div>
            ))}
          </div>
        ) : (
          <dl className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
            <Field label="Primary Email" value={provider.primary_email} />
            <Field label="Primary Phone" value={provider.primary_phone} />
            <Field label="Website" value={provider.website} />
            <Field label="Physical Address" value={provider.physical_address} />
            <Field label="Digital Address" value={provider.digital_address} />
            <Field label="Postal Address" value={provider.postal_address} />
          </dl>
        )}
      </div>

      {/* Licence card */}
      <div className="rounded-[16px] border border-[#eceef0] bg-white p-6">
        <h2 className="text-[16px] font-semibold text-[#191c1e] mb-5">Licence</h2>
        <dl className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Licence Type" value={provider.licence_type} />
          <Field label="Licence Number" value={provider.licence_number} />
          <Field label="Issue Date" value={provider.licence_issue_date ?? undefined} />
          <Field label="Expiry Date" value={provider.licence_expiry_date ?? undefined} />
        </dl>
      </div>

      {/* Contacts card */}
      <div className="rounded-[16px] border border-[#eceef0] bg-white p-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-[16px] font-semibold text-[#191c1e]">Contacts</h2>
          <button
            onClick={() => setAddingContact((v) => !v)}
            className="text-[13px] font-medium text-[#0066cc] hover:underline"
          >
            {addingContact ? "Cancel" : "+ Add Contact"}
          </button>
        </div>

        {addingContact && (
          <div className="mb-5 rounded-[12px] border border-[#c3c6d0] bg-[#f7f9fb] p-4 space-y-3">
            <div className="grid grid-cols-2 gap-3">
              {(["name", "designation", "email", "phone"] as const).map((f) => (
                <input
                  key={f}
                  type={f === "email" ? "email" : "text"}
                  placeholder={f.charAt(0).toUpperCase() + f.slice(1)}
                  value={newContact[f]}
                  onChange={(e) => setNewContact((c) => ({ ...c, [f]: e.target.value }))}
                  className="rounded-[8px] border border-[#c3c6d0] px-3 py-2 text-[13px] text-[#191c1e] focus:border-[#0066cc] focus:outline-none"
                />
              ))}
            </div>
            <button
              onClick={() => addContactMutation.mutate(newContact)}
              disabled={addContactMutation.isPending || !newContact.name || !newContact.email}
              className="rounded-[8px] bg-[#001836] px-4 py-2 text-[13px] font-semibold text-white hover:bg-[#002d5b] disabled:opacity-50"
            >
              {addContactMutation.isPending ? "Adding…" : "Add Contact"}
            </button>
          </div>
        )}

        {provider.contacts.length === 0 ? (
          <p className="text-[14px] text-[#737780]">No contacts on file.</p>
        ) : (
          <div className="divide-y divide-[#eceef0]">
            {provider.contacts.map((c) => (
              <div key={c.id} className="py-4 flex items-start justify-between gap-4">
                <div>
                  <p className="text-[14px] font-medium text-[#191c1e]">{c.name}</p>
                  <p className="text-[12px] text-[#43474f]">{c.designation}</p>
                  <p className="text-[12px] text-[#737780]">{c.email} · {c.phone}</p>
                </div>
                {!c.is_active && (
                  <span className="text-[11px] font-semibold uppercase tracking-wide text-[#737780] bg-[#f2f4f6] px-2 py-0.5 rounded-full">
                    Inactive
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

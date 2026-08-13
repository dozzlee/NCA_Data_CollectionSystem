"use client";

import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { api } from "@/lib/api";

interface SubmissionNotice {
  id: number;
  submission: number;
  expected_submission: number;
  title: string;
  message: string;
  is_read: boolean;
  created_at: string;
  form_code: string;
  provider_name: string;
  event: number;
}

export default function ProviderNotificationsPage() {
  const queryClient = useQueryClient();
  const query = useQuery<{ results: SubmissionNotice[] }>({
    queryKey: ["submission-notifications"],
    queryFn: () => api("/submission-notifications/"),
  });

  async function markAll() {
    await api.post("/submission-notifications/mark-all-read/");
    await queryClient.invalidateQueries({ queryKey: ["submission-notifications"] });
    await queryClient.invalidateQueries({ queryKey: ["submission-notification-summary"] });
  }

  const notices = query.data?.results ?? [];
  return (
    <div className="mx-auto max-w-4xl space-y-5 py-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Submission notifications</h1>
          <p className="mt-1 text-sm text-[#737780]">Provider approval, correction and NCA workflow updates.</p>
        </div>
        {notices.some((item) => !item.is_read) && (
          <button onClick={markAll} className="text-sm font-semibold text-[#0066cc]">Mark all read</button>
        )}
      </div>
      {query.isLoading && <div className="rounded-xl bg-white p-8 text-sm text-[#737780]">Loading notifications…</div>}
      {!query.isLoading && !notices.length && (
        <div className="rounded-xl border bg-white p-12 text-center">
          <Bell className="mx-auto text-[#737780]" />
          <p className="mt-3 font-semibold">No submission updates yet</p>
        </div>
      )}
      <div className="space-y-3">
        {notices.map((item) => (
          <Link
            key={item.id}
            href={`/provider/submissions/${item.expected_submission}`}
            onClick={async () => {
              if (!item.is_read) { await api.post(`/submission-notifications/${item.id}/mark-read/`); await queryClient.invalidateQueries({ queryKey:["submission-notification-summary"] }); }
            }}
            className={`block rounded-xl border p-5 ${item.is_read ? "bg-white" : "border-[#0066cc] bg-[#f4f8fd]"}`}
          >
            <div className="flex justify-between gap-4">
              <div>
                <p className="font-semibold">{item.title}</p>
                <p className="mt-1 text-sm text-[#43474f]">{item.message}</p>
                <p className="mt-2 text-xs text-[#737780]">{item.form_code} · {item.provider_name}</p>
              </div>
              <time className="text-xs text-[#737780]">{new Date(item.created_at).toLocaleDateString()}</time>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

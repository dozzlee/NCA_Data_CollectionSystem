"use client";

import { useState } from "react";
import Link from "next/link";
import { Bell } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Notification } from "@/lib/types";

interface NotificationResponse {
  unread_count: number;
  results: Notification[];
}

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: ["notifications"],
    queryFn: () => api.get<NotificationResponse>("/notifications/"),
    refetchInterval: 60000,
  });
  const readOne = useMutation({
    mutationFn: (id: number) => api.patch(`/notifications/${id}/read/`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });
  const readAll = useMutation({
    mutationFn: () => api.post("/notifications/read-all/"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((value) => !value)}
        className="relative flex h-8 w-8 items-center justify-center rounded-[8px] text-[#43474f] hover:bg-[#eceef0]"
        aria-label={`Notifications${query.data?.unread_count ? `, ${query.data.unread_count} unread` : ""}`}
        aria-expanded={open}
      >
        <Bell size={16} />
        {!!query.data?.unread_count && (
          <span className="absolute -right-1 -top-1 min-w-4 rounded-full bg-[#E31937] px-1 text-center text-[9px] font-bold text-white">
            {query.data.unread_count > 9 ? "9+" : query.data.unread_count}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 top-10 z-50 w-[360px] overflow-hidden rounded-[12px] border border-[#dfe2e6] bg-white shadow-xl">
          <div className="flex items-center justify-between border-b border-[#eceef0] px-4 py-3">
            <p className="text-[14px] font-semibold text-[#191c1e]">Notifications</p>
            {!!query.data?.unread_count && (
              <button onClick={() => readAll.mutate()} className="text-[11px] font-medium text-[#0066cc]">
                Mark all read
              </button>
            )}
          </div>
          <div className="max-h-[420px] overflow-y-auto">
            {!query.data?.results.length ? (
              <p className="px-4 py-10 text-center text-[13px] text-[#737780]">You are all caught up.</p>
            ) : query.data.results.map((item) => (
              <Link
                key={item.id}
                href={item.target_url || "#"}
                onClick={() => {
                  if (!item.is_read) readOne.mutate(item.id);
                  setOpen(false);
                }}
                className={`block border-b border-[#f0f1f2] px-4 py-3 hover:bg-[#f7f9fb] ${item.is_read ? "" : "bg-[#eef5fc]"}`}
              >
                <div className="flex items-start gap-2">
                  {!item.is_read && <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-[#0066cc]" />}
                  <div>
                    <p className="text-[12px] font-semibold text-[#191c1e]">{item.title}</p>
                    <p className="mt-0.5 text-[11px] leading-relaxed text-[#43474f]">{item.message}</p>
                    <p className="mt-1 text-[10px] text-[#737780]">
                      {new Date(item.created_at).toLocaleString("en-GB")}
                    </p>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

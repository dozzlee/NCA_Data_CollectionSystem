"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Skeleton } from "@/components/ui/Skeleton";
import type { FormalSubmission } from "@/lib/types";

export default function FormalSubmissionRedirectPage() {
  const params = useParams();
  const router = useRouter();
  const id = Number(params.id);
  const query = useQuery<FormalSubmission>({
    queryKey: ["provider-formal-submission", id],
    queryFn: () => api(`/provider-submissions/${id}/`),
    enabled: Number.isInteger(id) && id > 0,
  });
  useEffect(() => {
    if (query.data) router.replace(`/provider/submissions/${query.data.expected}?version=${query.data.id}`);
  }, [query.data, router]);
  if (query.isError || !Number.isInteger(id)) return <div className="rounded-xl border bg-white p-8 text-sm text-[#c5221f]">This submission could not be loaded.</div>;
  return <div className="space-y-3 rounded-xl border bg-white p-8"><Skeleton className="h-6 w-56"/><Skeleton className="h-4 w-80"/></div>;
}

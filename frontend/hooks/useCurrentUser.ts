import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { User } from "@/lib/types";

export function useCurrentUser() {
  return useQuery({
    queryKey: ["current-user"],
    queryFn: () => api.get<User>("/auth/me/"),
    staleTime: 5 * 60 * 1000,
  });
}

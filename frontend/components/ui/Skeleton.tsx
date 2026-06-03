import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "animate-pulse rounded-[8px] bg-[#e6e8ea]",
        className
      )}
    />
  );
}

"use client";

import { cn } from "@/lib/utils";

interface ChartShellProps {
  className?: string;
  children: React.ReactNode;
}

export function ChartShell({ className, children }: ChartShellProps) {
  return (
    <div
      className={cn(
        "h-[320px] rounded-[1.5rem] border border-white/10 bg-black/20 p-3 md:p-4",
        className,
      )}
    >
      {children}
    </div>
  );
}

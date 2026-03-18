import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";

import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: string;
  delta: string;
  direction: "up" | "down" | "neutral";
  icon?: React.ReactNode;
}

const directionStyles = {
  up: "text-accent",
  down: "text-rose",
  neutral: "text-slate-400",
};

const directionIcons = {
  up: ArrowUpRight,
  down: ArrowDownRight,
  neutral: Minus,
};

export function StatCard({
  label,
  value,
  delta,
  direction,
  icon,
}: StatCardProps) {
  const DirIcon = directionIcons[direction];

  return (
    <div className="panel relative overflow-hidden px-5 py-4">
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent/40 to-transparent" />
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-medium uppercase tracking-[0.16em] text-muted">
          {label}
        </p>
        {icon && (
          <div className="text-muted/60">{icon}</div>
        )}
      </div>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-white md:text-3xl">
        {value}
      </p>
      <div className="mt-2 flex items-center gap-1.5">
        <DirIcon
          className={cn("h-3.5 w-3.5", directionStyles[direction])}
        />
        <span
          className={cn(
            "text-xs font-medium",
            directionStyles[direction],
          )}
        >
          {delta}
        </span>
      </div>
    </div>
  );
}

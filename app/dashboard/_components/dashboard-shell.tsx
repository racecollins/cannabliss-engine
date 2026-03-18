"use client";

import { RefreshCw } from "lucide-react";

interface DashboardShellProps {
  title: string;
  subtitle: string;
  statusPills?: React.ReactNode;
  children: React.ReactNode;
}

export function DashboardShell({
  title,
  subtitle,
  statusPills,
  children,
}: DashboardShellProps) {
  return (
    <main className="min-h-screen px-4 py-6 sm:px-6 lg:px-10 lg:py-8">
      <div className="mx-auto max-w-[1400px] space-y-6">
        {/* Minimal header */}
        <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight text-white md:text-4xl">
              {title}
            </h1>
            <p className="mt-1 text-sm text-slate-400">{subtitle}</p>
          </div>
          <div className="flex items-center gap-3">
            {statusPills}
            <button
              type="button"
              className="inline-flex h-9 items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 text-xs font-medium text-slate-300 transition hover:bg-white/10"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Refresh
            </button>
          </div>
        </header>
        {children}
      </div>
    </main>
  );
}

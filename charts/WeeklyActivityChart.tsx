"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { WeeklyActivityEntry } from "@/types";
import { formatCompactDate } from "@/utils/formatters";

import { ChartShell } from "./chart-shell";

interface WeeklyActivityChartProps {
  data: WeeklyActivityEntry[];
}

export function WeeklyActivityChart({ data }: WeeklyActivityChartProps) {
  return (
    <ChartShell className="h-[280px]">
      <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={220}>
        <BarChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
          <CartesianGrid stroke="rgba(255,255,255,0.08)" vertical={false} />
          <XAxis
            dataKey="weekStart"
            tickFormatter={formatCompactDate}
            tick={{ fill: "#8fa8a0", fontSize: 12 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: "#8fa8a0", fontSize: 12 }}
            axisLine={false}
            tickLine={false}
            width={36}
          />
          <Tooltip
            cursor={{ fill: "rgba(255,255,255,0.03)" }}
            contentStyle={{
              background: "#0b1412",
              border: "1px solid rgba(255,255,255,0.08)",
              borderRadius: "16px",
              color: "#eff8f2",
            }}
            labelFormatter={(label) => formatCompactDate(String(label))}
          />
          <Legend wrapperStyle={{ color: "#cbd5e1", fontSize: "12px" }} />
          <Bar dataKey="additions" stackId="activity" fill="#7ef0b2" radius={[6, 6, 0, 0]} />
          <Bar dataKey="removals" stackId="activity" fill="#f48ca9" radius={[6, 6, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </ChartShell>
  );
}

"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { FollowerHistoryPoint } from "@/types";
import { formatCompactDate, formatCompactNumber, formatNumber } from "@/utils/formatters";

import { ChartShell } from "./chart-shell";

interface FollowerGrowthChartProps {
  data: FollowerHistoryPoint[];
}

export function FollowerGrowthChart({ data }: FollowerGrowthChartProps) {
  return (
    <ChartShell>
      <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={240}>
        <LineChart data={data} margin={{ top: 10, right: 8, left: -18, bottom: 0 }}>
          <defs>
            <linearGradient id="followerLine" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#7ef0b2" />
              <stop offset="100%" stopColor="#7bd6ff" />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="rgba(255,255,255,0.08)" vertical={false} />
          <XAxis
            dataKey="date"
            tickFormatter={formatCompactDate}
            tick={{ fill: "#8fa8a0", fontSize: 12 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tickFormatter={formatCompactNumber}
            tick={{ fill: "#8fa8a0", fontSize: 12 }}
            axisLine={false}
            tickLine={false}
            width={52}
          />
          <Tooltip
            cursor={{ stroke: "rgba(255,255,255,0.08)", strokeWidth: 1 }}
            contentStyle={{
              background: "#0b1412",
              border: "1px solid rgba(255,255,255,0.08)",
              borderRadius: "16px",
              color: "#eff8f2",
            }}
            formatter={(value) => [formatNumber(Number(value ?? 0)), "Followers"]}
            labelFormatter={(label) => formatCompactDate(String(label))}
          />
          <Line
            type="monotone"
            dataKey="followers"
            stroke="url(#followerLine)"
            strokeWidth={3}
            dot={false}
            activeDot={{ r: 5, fill: "#7ef0b2", stroke: "#07110f", strokeWidth: 2 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </ChartShell>
  );
}

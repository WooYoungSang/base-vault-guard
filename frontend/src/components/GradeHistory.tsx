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
import { GradeRecord } from "@/lib/api";

export function GradeHistory({ history }: { history: GradeRecord[] }) {
  if (history.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-slate-500">
        No grade history available yet.
      </p>
    );
  }

  const data = [...history]
    .reverse()
    .map((r) => ({
      date: new Date(r.recorded_at).toLocaleDateString(),
      score: r.score,
      grade: r.grade,
    }));

  return (
    <div>
      <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-slate-400">
        Score History
      </h3>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis dataKey="date" tick={{ fill: "#94a3b8", fontSize: 11 }} />
          <YAxis
            domain={[0, 100]}
            tick={{ fill: "#94a3b8", fontSize: 11 }}
            tickFormatter={(v) => `${v}`}
          />
          <Tooltip
            contentStyle={{
              background: "#0f172a",
              border: "1px solid #1e293b",
              borderRadius: 8,
            }}
            formatter={(v: number, _: string, p: { payload?: { grade?: string } }) => [
              `${v}${p?.payload?.grade ? ` (${p.payload.grade})` : ""}`,
              "Score",
            ]}
          />
          <Line
            type="monotone"
            dataKey="score"
            stroke="#10b981"
            strokeWidth={2}
            dot={{ fill: "#10b981", r: 3 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

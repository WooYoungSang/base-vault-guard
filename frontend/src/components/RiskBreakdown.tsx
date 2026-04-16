"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { RiskProfile } from "@/lib/api";

const RISK_LABELS: Record<keyof Omit<RiskProfile, "sufficient_data">, string> = {
  utilization: "Utilization",
  tvl_change_7d: "TVL Change 7d",
  oracle_risk_score: "Oracle Risk",
  audit_score: "Audit Score",
  drawdown_max: "Max Drawdown",
};

export function RiskBreakdown({ risk }: { risk: RiskProfile }) {
  const data = (
    Object.keys(RISK_LABELS) as Array<keyof typeof RISK_LABELS>
  ).map((key) => ({
    name: RISK_LABELS[key],
    value: Number((risk[key] * 100).toFixed(1)),
  }));

  return (
    <div>
      <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-slate-400">
        Risk Breakdown
      </h3>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} layout="vertical" margin={{ left: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis
            type="number"
            domain={[0, 100]}
            tick={{ fill: "#94a3b8", fontSize: 11 }}
            tickFormatter={(v) => `${v}%`}
          />
          <YAxis
            type="category"
            dataKey="name"
            tick={{ fill: "#94a3b8", fontSize: 11 }}
            width={100}
          />
          <Tooltip
            formatter={(v: number) => [`${v}%`, ""]}
            contentStyle={{
              background: "#0f172a",
              border: "1px solid #1e293b",
              borderRadius: 8,
            }}
          />
          <Bar dataKey="value" fill="#3b82f6" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

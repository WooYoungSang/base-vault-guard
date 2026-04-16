"use client";

import Link from "next/link";
import { ScoredVault } from "@/lib/api";
import { SafetyBadge } from "./SafetyBadge";

function fmt(n: number, decimals = 1) {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toFixed(decimals)}`;
}

export function VaultTable({ vaults }: { vaults: ScoredVault[] }) {
  if (vaults.length === 0) {
    return (
      <p className="py-12 text-center text-slate-500">No vaults found.</p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-800">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-800 bg-slate-900 text-left text-xs uppercase tracking-wider text-slate-500">
            <th className="px-4 py-3">Grade</th>
            <th className="px-4 py-3">Protocol</th>
            <th className="px-4 py-3">Asset</th>
            <th className="px-4 py-3">TVL</th>
            <th className="px-4 py-3">APY</th>
            <th className="px-4 py-3">Utilization</th>
            <th className="px-4 py-3">Score</th>
            <th className="px-4 py-3"></th>
          </tr>
        </thead>
        <tbody>
          {vaults.map((sv) => (
            <tr
              key={sv.vault.address}
              className="border-b border-slate-800/50 transition-colors hover:bg-slate-900/50"
            >
              <td className="px-4 py-3">
                <SafetyBadge grade={sv.grade} />
              </td>
              <td className="px-4 py-3 font-medium capitalize text-white">
                {sv.vault.protocol.replace("_", " ")}
              </td>
              <td className="px-4 py-3 text-slate-300">{sv.vault.asset}</td>
              <td className="px-4 py-3 text-slate-300">
                {sv.vault.tvl_usd > 0 ? fmt(sv.vault.tvl_usd) : "—"}
              </td>
              <td className="px-4 py-3 font-medium text-emerald-400">
                {sv.vault.apy.toFixed(2)}%
              </td>
              <td className="px-4 py-3">
                <div className="flex items-center gap-2">
                  <div className="h-1.5 w-16 rounded-full bg-slate-800">
                    <div
                      className="h-1.5 rounded-full bg-blue-500"
                      style={{
                        width: `${(sv.vault.utilization_rate * 100).toFixed(0)}%`,
                      }}
                    />
                  </div>
                  <span className="text-slate-400">
                    {(sv.vault.utilization_rate * 100).toFixed(0)}%
                  </span>
                </div>
              </td>
              <td className="px-4 py-3 text-slate-300">{sv.score.toFixed(1)}</td>
              <td className="px-4 py-3">
                <Link
                  href={`/vaults/${sv.vault.address}`}
                  className="text-blue-400 hover:text-blue-300 text-xs"
                >
                  Details →
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

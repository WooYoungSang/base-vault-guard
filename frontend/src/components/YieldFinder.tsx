"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { SafetyBadge } from "./SafetyBadge";

const GRADES = ["A", "B", "C", "D", "F"];

export function YieldFinder() {
  const [minGrade, setMinGrade] = useState("B");

  const { data, isLoading, error } = useQuery({
    queryKey: ["safe-yield", minGrade],
    queryFn: () => api.safeYield(minGrade),
  });

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <span className="text-sm text-slate-400">Minimum grade:</span>
        {GRADES.map((g) => (
          <button
            key={g}
            onClick={() => setMinGrade(g)}
            className={`rounded-lg px-3 py-1 text-sm font-medium transition-colors ${
              minGrade === g
                ? "bg-blue-600 text-white"
                : "bg-slate-800 text-slate-400 hover:bg-slate-700"
            }`}
          >
            {g}
          </button>
        ))}
      </div>

      {isLoading && (
        <div className="space-y-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-16 animate-pulse rounded-xl bg-slate-800" />
          ))}
        </div>
      )}

      {error && (
        <p className="text-red-400 text-sm">Failed to load yields. Is the API running?</p>
      )}

      {data && (
        <>
          <p className="mb-4 text-sm text-slate-500">
            {data.total} vault{data.total !== 1 ? "s" : ""} with grade{" "}
            {minGrade} or better
          </p>
          <div className="space-y-3">
            {data.items.map((sv) => (
              <div
                key={sv.vault.address}
                className="flex items-center justify-between rounded-xl border border-slate-800 bg-slate-900 px-5 py-4"
              >
                <div className="flex items-center gap-4">
                  <SafetyBadge grade={sv.grade} />
                  <div>
                    <p className="font-medium text-white">
                      {sv.vault.asset}
                      <span className="ml-2 text-xs text-slate-500 capitalize">
                        {sv.vault.protocol.replace("_", " ")}
                      </span>
                    </p>
                    <p className="text-xs text-slate-500 font-mono">
                      {sv.vault.address.slice(0, 10)}…
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-xl font-bold text-emerald-400">
                    {sv.vault.apy.toFixed(2)}%
                  </p>
                  <p className="text-xs text-slate-500">APY</p>
                </div>
              </div>
            ))}
          </div>
          {data.items.length === 0 && (
            <p className="py-12 text-center text-slate-500">
              No vaults meet this safety threshold.
            </p>
          )}
        </>
      )}
    </div>
  );
}

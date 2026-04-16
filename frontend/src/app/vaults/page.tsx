"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { VaultTable } from "@/components/VaultTable";

const PROTOCOLS = ["", "morpho", "aave_v3", "compound_v3", "aerodrome"];
const GRADES = ["", "A", "B", "C", "D", "F"];

export default function VaultsPage() {
  const [protocol, setProtocol] = useState("");
  const [grade, setGrade] = useState("");
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 20;

  const { data, isLoading, error } = useQuery({
    queryKey: ["vaults", protocol, grade, page],
    queryFn: () =>
      api.listVaults({
        protocol: protocol || undefined,
        grade: grade || undefined,
        page,
        page_size: PAGE_SIZE,
      }),
  });

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 1;

  return (
    <div className="mx-auto max-w-7xl px-4 py-10">
      <h1 className="mb-6 text-3xl font-bold text-white">All Vaults</h1>

      {/* Filters */}
      <div className="mb-6 flex flex-wrap gap-4">
        <div>
          <label className="mb-1 block text-xs text-slate-500">Protocol</label>
          <select
            value={protocol}
            onChange={(e) => { setProtocol(e.target.value); setPage(1); }}
            className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-300 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            {PROTOCOLS.map((p) => (
              <option key={p} value={p}>
                {p || "All protocols"}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate-500">Grade</label>
          <select
            value={grade}
            onChange={(e) => { setGrade(e.target.value); setPage(1); }}
            className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-300 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            {GRADES.map((g) => (
              <option key={g} value={g}>
                {g || "All grades"}
              </option>
            ))}
          </select>
        </div>
      </div>

      {isLoading && (
        <div className="space-y-2">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-12 animate-pulse rounded-lg bg-slate-800" />
          ))}
        </div>
      )}

      {error && (
        <p className="text-red-400">Failed to load vaults. Is the API running?</p>
      )}

      {data && (
        <>
          <p className="mb-3 text-sm text-slate-500">{data.total} vaults</p>
          <VaultTable vaults={data.items} />

          {totalPages > 1 && (
            <div className="mt-6 flex justify-center gap-2">
              <button
                disabled={page === 1}
                onClick={() => setPage((p) => p - 1)}
                className="rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-400 disabled:opacity-40 hover:border-slate-500 hover:text-white transition-colors"
              >
                ← Prev
              </button>
              <span className="flex items-center px-3 text-sm text-slate-500">
                {page} / {totalPages}
              </span>
              <button
                disabled={page === totalPages}
                onClick={() => setPage((p) => p + 1)}
                className="rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-400 disabled:opacity-40 hover:border-slate-500 hover:text-white transition-colors"
              >
                Next →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

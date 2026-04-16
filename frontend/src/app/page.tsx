import Link from "next/link";
import { api } from "@/lib/api";
import { VaultTable } from "@/components/VaultTable";

export default async function HomePage() {
  let vaults = null;
  let error = false;

  try {
    const data = await api.listVaults({ page_size: 10 });
    vaults = data.items;
  } catch {
    error = true;
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-12">
      {/* Hero */}
      <div className="mb-14 text-center">
        <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-blue-800 bg-blue-950/50 px-4 py-1.5 text-sm text-blue-300">
          <span className="inline-block h-2 w-2 rounded-full bg-blue-400 animate-pulse" />
          Live on Base
        </div>
        <h1 className="mb-4 text-5xl font-bold tracking-tight text-white">
          DeFi Vault Safety Scoring
        </h1>
        <p className="mx-auto mb-8 max-w-xl text-lg text-slate-400">
          AI-powered safety grades for Morpho, Aave v3, Compound v3, and
          Aerodrome vaults on Base. Find the best yields without the hidden
          risks.
        </p>
        <div className="flex justify-center gap-4">
          <Link
            href="/safe-yield"
            className="rounded-xl bg-blue-600 px-6 py-3 font-semibold text-white transition-colors hover:bg-blue-500"
          >
            Find Safe Yields
          </Link>
          <Link
            href="/vaults"
            className="rounded-xl border border-slate-700 px-6 py-3 font-semibold text-slate-300 transition-colors hover:border-slate-500 hover:text-white"
          >
            Browse Vaults
          </Link>
        </div>
      </div>

      {/* Grade legend */}
      <div className="mb-10 flex flex-wrap justify-center gap-3 text-sm">
        {[
          ["A", "Excellent", "text-emerald-400"],
          ["B", "Good", "text-blue-400"],
          ["C", "Fair", "text-yellow-400"],
          ["D", "Poor", "text-orange-400"],
          ["F", "Unsafe", "text-red-400"],
        ].map(([grade, label, color]) => (
          <div
            key={grade}
            className="flex items-center gap-2 rounded-lg border border-slate-800 bg-slate-900 px-3 py-1.5"
          >
            <span className={`font-bold ${color}`}>{grade}</span>
            <span className="text-slate-500">{label}</span>
          </div>
        ))}
      </div>

      {/* Top vaults */}
      <div>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-white">Top Vaults</h2>
          <Link href="/vaults" className="text-sm text-blue-400 hover:text-blue-300">
            View all →
          </Link>
        </div>

        {error && (
          <div className="rounded-xl border border-slate-800 bg-slate-900 p-8 text-center text-slate-500">
            Could not connect to the API. Start the backend with{" "}
            <code className="text-slate-300">uvicorn vault_guard.api:app</code>
          </div>
        )}

        {vaults && <VaultTable vaults={vaults} />}
      </div>
    </div>
  );
}

import { notFound } from "next/navigation";
import { api } from "@/lib/api";
import { SafetyBadge } from "@/components/SafetyBadge";
import { RiskBreakdown } from "@/components/RiskBreakdown";
import { GradeHistory } from "@/components/GradeHistory";

export default async function VaultDetailPage({
  params,
}: {
  params: { address: string };
}) {
  let vault = null;
  let history = null;

  try {
    [vault, history] = await Promise.all([
      api.getVault(params.address),
      api.getVaultHistory(params.address),
    ]);
  } catch {
    notFound();
  }

  if (!vault) notFound();

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      {/* Header */}
      <div className="mb-8 flex items-start gap-4">
        <SafetyBadge grade={vault.grade} />
        <div>
          <h1 className="text-2xl font-bold text-white">
            {vault.vault.asset}
            <span className="ml-3 text-base font-normal text-slate-500 capitalize">
              {vault.vault.protocol.replace("_", " ")}
            </span>
          </h1>
          <p className="mt-1 font-mono text-sm text-slate-500">{vault.vault.address}</p>
        </div>
      </div>

      {/* Stat cards */}
      <div className="mb-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
        {[
          ["Safety Score", `${vault.score.toFixed(1)} / 100`, "text-white"],
          ["Grade", vault.grade, "text-white"],
          ["APY", `${vault.vault.apy.toFixed(2)}%`, "text-emerald-400"],
          [
            "TVL",
            vault.vault.tvl_usd > 0
              ? `$${(vault.vault.tvl_usd / 1_000_000).toFixed(1)}M`
              : "—",
            "text-white",
          ],
        ].map(([label, value, color]) => (
          <div
            key={label}
            className="rounded-xl border border-slate-800 bg-slate-900 p-4"
          >
            <p className="text-xs text-slate-500">{label}</p>
            <p className={`mt-1 text-2xl font-bold ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Risk breakdown */}
        <div className="rounded-xl border border-slate-800 bg-slate-900 p-6">
          <RiskBreakdown risk={vault.risk} />
        </div>

        {/* Grade history */}
        <div className="rounded-xl border border-slate-800 bg-slate-900 p-6">
          <GradeHistory history={history?.history ?? []} />
        </div>
      </div>

      {/* Disclaimer */}
      <p className="mt-6 text-xs text-slate-600">{vault.disclaimer}</p>
    </div>
  );
}

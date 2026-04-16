import { YieldFinder } from "@/components/YieldFinder";

export default function SafeYieldPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <div className="mb-8">
        <h1 className="mb-2 text-3xl font-bold text-white">Safe Yield Finder</h1>
        <p className="text-slate-400">
          Filter vaults by minimum safety grade, sorted by APY. Only vaults with
          sufficient data and verified safety profiles are shown.
        </p>
      </div>
      <YieldFinder />
    </div>
  );
}

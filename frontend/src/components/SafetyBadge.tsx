const GRADE_STYLES: Record<string, string> = {
  A: "bg-emerald-900 text-emerald-300 ring-emerald-700",
  B: "bg-blue-900 text-blue-300 ring-blue-700",
  C: "bg-yellow-900 text-yellow-300 ring-yellow-700",
  D: "bg-orange-900 text-orange-300 ring-orange-700",
  F: "bg-red-900 text-red-300 ring-red-700",
  Unrated: "bg-slate-800 text-slate-400 ring-slate-600",
};

export function SafetyBadge({ grade }: { grade: string }) {
  const styles = GRADE_STYLES[grade] ?? GRADE_STYLES["Unrated"];
  return (
    <span
      className={`inline-flex items-center justify-center w-8 h-8 rounded-full text-sm font-bold ring-1 ${styles}`}
    >
      {grade === "Unrated" ? "?" : grade}
    </span>
  );
}

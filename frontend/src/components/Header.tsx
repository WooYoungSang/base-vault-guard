import Link from "next/link";

export function Header() {
  return (
    <header className="sticky top-0 z-50 border-b border-slate-800 bg-slate-950/90 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
        <Link href="/" className="flex items-center gap-2 font-bold text-white">
          <span className="text-2xl">🛡️</span>
          <span>Base Vault Guard</span>
        </Link>
        <nav className="flex gap-6 text-sm text-slate-400">
          <Link href="/vaults" className="hover:text-white transition-colors">
            Vaults
          </Link>
          <Link href="/safe-yield" className="hover:text-white transition-colors">
            Safe Yield
          </Link>
        </nav>
      </div>
    </header>
  );
}

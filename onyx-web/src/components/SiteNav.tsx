import { useState } from "react";
import { Link } from "react-router-dom";
import { Menu, X, Github } from "lucide-react";

type NavAnchor = { kind: "anchor"; href: string; label: string };
type NavRoute = { kind: "route"; to: string; label: string };
const NAV_LINKS: ReadonlyArray<NavAnchor | NavRoute> = [
  { kind: "anchor", href: "#demo", label: "Demo" },
  { kind: "anchor", href: "#pricing", label: "Pricing" },
  { kind: "anchor", href: "#install", label: "Install" },
  { kind: "route", to: "/face", label: "Try Live" },
  { kind: "route", to: "/ecosystem", label: "Ecosystem" },
];

export default function SiteNav() {
  const [open, setOpen] = useState(false);

  return (
    <nav className="fixed top-0 w-full z-50 bg-onyx-bg/80 backdrop-blur-xl border-b border-onyx-border/20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2.5 group">
          <div className="w-8 h-8 rounded-lg bg-onyx-accent/15 flex items-center justify-center border border-onyx-accent/30 group-hover:bg-onyx-accent/25 transition-colors">
            <span className="text-onyx-accent font-bold text-sm">O</span>
          </div>
          <span className="font-mono font-bold text-white text-lg tracking-tight">
            Onyx<span className="text-onyx-accent">Kraken</span>
          </span>
        </Link>

        <div className="hidden md:flex items-center gap-6 text-sm font-mono">
          {NAV_LINKS.map((l) =>
            l.kind === "route" ? (
              <Link
                key={l.label}
                to={l.to}
                className="text-onyx-text-dim hover:text-white transition-colors"
              >
                {l.label}
              </Link>
            ) : (
              <a
                key={l.label}
                href={l.href}
                className="text-onyx-text-dim hover:text-white transition-colors"
              >
                {l.label}
              </a>
            )
          )}
          <a
            href="https://github.com/20TwentyVizion/OnyxKraken-Public"
            target="_blank" rel="noopener"
            className="inline-flex items-center gap-1.5 text-onyx-text-dim hover:text-white transition-colors"
          >
            <Github size={14} /> GitHub
          </a>
          <a
            href="#install"
            className="px-4 py-2 rounded-lg bg-onyx-accent text-onyx-bg font-bold hover:bg-onyx-accent/90 transition-colors"
          >
            Install
          </a>
        </div>

        <button
          onClick={() => setOpen(!open)}
          className="md:hidden text-onyx-text-dim hover:text-white"
          aria-label="Toggle menu"
        >
          {open ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      {open && (
        <div className="md:hidden border-t border-onyx-border/20 bg-onyx-bg/95 backdrop-blur-xl px-4 py-4 space-y-3">
          {NAV_LINKS.map((l) =>
            l.kind === "route" ? (
              <Link
                key={l.label}
                to={l.to}
                onClick={() => setOpen(false)}
                className="block text-sm font-mono text-onyx-text-dim hover:text-white transition-colors"
              >
                {l.label}
              </Link>
            ) : (
              <a
                key={l.label}
                href={l.href}
                onClick={() => setOpen(false)}
                className="block text-sm font-mono text-onyx-text-dim hover:text-white transition-colors"
              >
                {l.label}
              </a>
            )
          )}
          <a
            href="https://github.com/20TwentyVizion/OnyxKraken-Public"
            target="_blank" rel="noopener"
            className="block text-sm font-mono text-onyx-text-dim hover:text-white"
          >
            GitHub
          </a>
        </div>
      )}
    </nav>
  );
}

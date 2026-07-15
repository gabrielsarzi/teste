"use client";

import { useState } from "react";
import { SECTION_LABELS, type Section, type Site } from "@/lib/types";

export function SiteHeader({
  site,
  sections,
}: {
  site: Site;
  sections: Section[];
}) {
  const [open, setOpen] = useState(false);
  const navItems = sections.filter((s) => s.key !== "hero");

  return (
    <header className="sticky top-0 z-20 border-b border-zinc-100 bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
        <a href="#hero" className="text-lg font-bold">
          {site.name}
        </a>

        <nav className="hidden gap-6 sm:flex">
          {navItems.map((section) => (
            <a
              key={section.key}
              href={`#${section.key}`}
              className="text-sm font-medium text-zinc-600 transition hover:text-primary"
            >
              {SECTION_LABELS[section.key]}
            </a>
          ))}
        </nav>

        <button
          onClick={() => setOpen(!open)}
          className="text-2xl leading-none sm:hidden"
          aria-label="Abrir menu"
        >
          {open ? "×" : "☰"}
        </button>
      </div>

      {open && (
        <nav className="flex flex-col border-t border-zinc-100 px-6 py-2 sm:hidden">
          {navItems.map((section) => (
            <a
              key={section.key}
              href={`#${section.key}`}
              onClick={() => setOpen(false)}
              className="py-3 text-sm font-medium text-zinc-700"
            >
              {SECTION_LABELS[section.key]}
            </a>
          ))}
        </nav>
      )}
    </header>
  );
}

import Link from "next/link";
import { createClient } from "@/lib/supabase/server";
import { getSiteForCurrentUser } from "@/lib/queries";
import { SECTION_LABELS, type Section } from "@/lib/types";
import { toggleSection } from "@/app/admin/actions";

export const dynamic = "force-dynamic";

export default async function AdminDashboard() {
  const site = await getSiteForCurrentUser();

  if (!site) {
    return (
      <p className="text-zinc-600">
        Seu usuário ainda não está vinculado a nenhum site. Fale com o suporte.
      </p>
    );
  }

  const supabase = await createClient();
  const { data } = await supabase
    .from("sections")
    .select("*")
    .eq("site_id", site.id)
    .order("position", { ascending: true });
  const sections: Section[] = data ?? [];

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">{site.name}</h1>
          <p className="text-sm text-zinc-500">
            {site.published ? "Site publicado" : "Site despublicado (oculto)"}
          </p>
        </div>
        <div className="flex gap-2 text-sm">
          <a
            href={`/${site.slug}`}
            target="_blank"
            className="rounded-lg border border-zinc-300 px-4 py-2 hover:bg-white"
          >
            Ver site
          </a>
          <a
            href={`/${site.slug}/bio`}
            target="_blank"
            className="rounded-lg border border-zinc-300 px-4 py-2 hover:bg-white"
          >
            Ver bio
          </a>
        </div>
      </div>

      <h2 className="mt-8 text-lg font-semibold">Seções da página</h2>
      <p className="text-sm text-zinc-500">
        Ative ou desative o que aparece no site e edite o conteúdo de cada
        parte.
      </p>

      <ul className="mt-4 divide-y divide-zinc-100 overflow-hidden rounded-2xl border border-zinc-200 bg-white">
        {sections.map((section) => (
          <li
            key={section.key}
            className="flex items-center justify-between gap-4 px-5 py-4"
          >
            <div>
              <p className="font-medium">{SECTION_LABELS[section.key]}</p>
              <p className="text-xs text-zinc-400">
                {section.enabled ? "Visível no site" : "Oculta"}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <form action={toggleSection}>
                <input type="hidden" name="key" value={section.key} />
                <input
                  type="hidden"
                  name="enabled"
                  value={String(!section.enabled)}
                />
                <button
                  type="submit"
                  role="switch"
                  aria-checked={section.enabled}
                  className={`relative h-6 w-11 rounded-full transition ${
                    section.enabled ? "bg-emerald-500" : "bg-zinc-300"
                  }`}
                >
                  <span
                    className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${
                      section.enabled ? "left-[22px]" : "left-0.5"
                    }`}
                  />
                </button>
              </form>
              <Link
                href={`/admin/secoes/${section.key}`}
                className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm hover:bg-zinc-50"
              >
                Editar
              </Link>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

import { createClient } from "@/lib/supabase/server";
import { getSiteForCurrentUser } from "@/lib/queries";
import type { BioLink, BioPage } from "@/lib/types";
import {
  addBioLink,
  deleteBioLink,
  updateBioLink,
  updateBioPage,
} from "@/app/admin/actions";
import { ImageUploadField } from "@/components/admin/ImageUploadField";

export const dynamic = "force-dynamic";

const inputClass =
  "mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2";

export default async function AdminBioPage() {
  const site = await getSiteForCurrentUser();
  if (!site) {
    return <p className="text-zinc-600">Nenhum site vinculado.</p>;
  }

  const supabase = await createClient();
  const [{ data: bioData }, { data: linksData }] = await Promise.all([
    supabase.from("bio_pages").select("*").eq("site_id", site.id).maybeSingle(),
    supabase
      .from("bio_links")
      .select("*")
      .eq("site_id", site.id)
      .order("position", { ascending: true }),
  ]);
  const bio = bioData as BioPage | null;
  const links: BioLink[] = linksData ?? [];

  if (!bio) return <p className="text-zinc-600">Página bio não encontrada.</p>;

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-2xl font-bold">Página de links (bio)</h1>
      <p className="text-sm text-zinc-500">
        A página estilo &quot;link na bio&quot; fica em /{site.slug}/bio
      </p>

      <form
        action={updateBioPage}
        className="mt-6 rounded-2xl border border-zinc-200 bg-white p-6"
      >
        <label className="flex items-center gap-3 text-sm font-medium">
          <input
            type="checkbox"
            name="enabled"
            defaultChecked={bio.enabled}
            className="h-4 w-4"
          />
          Página bio ativa
        </label>

        <label className="mt-4 block text-sm font-medium">
          Nome exibido
          <input
            name="display_name"
            defaultValue={bio.display_name}
            className={inputClass}
          />
        </label>

        <label className="mt-4 block text-sm font-medium">
          Frase curta (opcional)
          <input
            name="tagline"
            defaultValue={bio.tagline}
            className={inputClass}
          />
        </label>

        <ImageUploadField
          name="avatar_url"
          label="Foto / avatar"
          siteId={site.id}
          defaultValue={bio.avatar_url}
        />

        <button
          type="submit"
          className="mt-6 rounded-lg bg-zinc-900 px-8 py-2.5 font-medium text-white transition hover:bg-zinc-700"
        >
          Salvar
        </button>
      </form>

      <h2 className="mt-10 text-lg font-semibold">Links</h2>
      <div className="mt-3 flex flex-col gap-3">
        {links.map((link) => (
          <div
            key={link.id}
            className="rounded-2xl border border-zinc-200 bg-white p-4"
          >
            <form
              action={updateBioLink}
              className="flex flex-col gap-2 sm:flex-row sm:items-center"
            >
              <input type="hidden" name="id" value={link.id} />
              <input
                type="hidden"
                name="position"
                value={String(link.position)}
              />
              <input
                name="label"
                defaultValue={link.label}
                placeholder="Texto do botão"
                className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm"
              />
              <input
                name="url"
                defaultValue={link.url}
                placeholder="https://..."
                className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm"
              />
              <label className="flex shrink-0 items-center gap-1.5 text-sm">
                <input
                  type="checkbox"
                  name="enabled"
                  defaultChecked={link.enabled}
                  className="h-4 w-4"
                />
                Ativo
              </label>
              <button
                type="submit"
                className="shrink-0 rounded-lg border border-zinc-300 px-4 py-2 text-sm hover:bg-zinc-50"
              >
                Salvar
              </button>
            </form>
            <form action={deleteBioLink} className="mt-2 text-right">
              <input type="hidden" name="id" value={link.id} />
              <button className="text-xs text-red-600 hover:underline">
                Excluir link
              </button>
            </form>
          </div>
        ))}
      </div>

      <form
        action={addBioLink}
        className="mt-4 flex flex-col gap-2 rounded-2xl border border-dashed border-zinc-300 p-4 sm:flex-row"
      >
        <input
          name="label"
          placeholder="Texto do botão (ex: Peça pelo WhatsApp)"
          required
          className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm"
        />
        <input
          name="url"
          placeholder="https://..."
          required
          className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm"
        />
        <button
          type="submit"
          className="shrink-0 rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700"
        >
          + Adicionar
        </button>
      </form>
    </div>
  );
}

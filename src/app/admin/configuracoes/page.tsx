import { getSiteForCurrentUser } from "@/lib/queries";
import { updateSiteSettings } from "@/app/admin/actions";

export const dynamic = "force-dynamic";

export default async function AdminSettingsPage() {
  const site = await getSiteForCurrentUser();
  if (!site) {
    return <p className="text-zinc-600">Nenhum site vinculado.</p>;
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-2xl font-bold">Configurações do site</h1>

      <form
        action={updateSiteSettings}
        className="mt-6 rounded-2xl border border-zinc-200 bg-white p-6"
      >
        <label className="block text-sm font-medium">
          Nome do negócio
          <input
            name="name"
            defaultValue={site.name}
            className="mt-1 w-full rounded-lg border border-zinc-300 px-3 py-2"
          />
        </label>

        <label className="mt-4 block text-sm font-medium">
          Cor principal
          <input
            type="color"
            name="primary"
            defaultValue={site.theme.primary}
            className="mt-1 h-10 w-20 cursor-pointer rounded border border-zinc-300"
          />
        </label>

        <label className="mt-6 flex items-center gap-3 text-sm font-medium">
          <input
            type="checkbox"
            name="published"
            defaultChecked={site.published}
            className="h-4 w-4"
          />
          Site publicado (visível para qualquer pessoa)
        </label>

        <div className="mt-6 rounded-lg bg-zinc-50 p-4 text-sm text-zinc-600">
          <p>
            <span className="font-medium">Endereço do site:</span> /{site.slug}
          </p>
          <p className="mt-1">
            <span className="font-medium">Domínio próprio:</span>{" "}
            {site.custom_domain ?? "não configurado (fale com o suporte)"}
          </p>
        </div>

        <button
          type="submit"
          className="mt-6 rounded-lg bg-zinc-900 px-8 py-2.5 font-medium text-white transition hover:bg-zinc-700"
        >
          Salvar
        </button>
      </form>
    </div>
  );
}

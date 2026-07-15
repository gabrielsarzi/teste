import { notFound } from "next/navigation";
import {
  getBioPage,
  getEnabledBioLinks,
  getPublishedSite,
} from "@/lib/queries";

export const dynamic = "force-dynamic";

export default async function BioPageRoute({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const site = await getPublishedSite(slug);
  if (!site) notFound();

  const bio = await getBioPage(site.id);
  if (!bio) notFound();

  const links = await getEnabledBioLinks(site.id);

  return (
    <main
      className="flex min-h-screen flex-col items-center bg-zinc-950 px-6 py-16 text-white"
      style={{ "--primary": site.theme.primary } as React.CSSProperties}
    >
      <div className="flex w-full max-w-md flex-col items-center gap-6">
        {bio.avatar_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={bio.avatar_url}
            alt={bio.display_name}
            className="h-24 w-24 rounded-full border-2 border-primary object-cover"
          />
        ) : (
          <div className="flex h-24 w-24 items-center justify-center rounded-full bg-primary text-3xl font-bold">
            {bio.display_name.charAt(0).toUpperCase()}
          </div>
        )}

        <div className="text-center">
          <h1 className="text-xl font-bold">{bio.display_name}</h1>
          {bio.tagline && (
            <p className="mt-1 text-sm text-zinc-400">{bio.tagline}</p>
          )}
        </div>

        <div className="flex w-full flex-col gap-3">
          {links.map((link) => (
            <a
              key={link.id}
              href={link.url}
              target="_blank"
              rel="noopener noreferrer"
              className="w-full rounded-full border border-zinc-700 bg-zinc-900 px-6 py-4 text-center font-medium transition hover:border-primary hover:bg-zinc-800"
            >
              {link.label}
            </a>
          ))}
        </div>

        <a
          href={`/${site.slug}`}
          className="mt-4 text-xs text-zinc-500 transition hover:text-zinc-300"
        >
          {site.name}
        </a>
      </div>
    </main>
  );
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const site = await getPublishedSite(slug);
  return { title: site ? `${site.name} — Links` : "Página não encontrada" };
}

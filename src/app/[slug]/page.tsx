import { notFound } from "next/navigation";
import { getEnabledSections, getPublishedSite } from "@/lib/queries";
import { SectionRenderer } from "@/components/SectionRenderer";
import { SiteHeader } from "@/components/SiteHeader";

export const dynamic = "force-dynamic";

export default async function PublicSitePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const site = await getPublishedSite(slug);
  if (!site) notFound();

  const sections = await getEnabledSections(site.id);

  return (
    <div style={{ "--primary": site.theme.primary } as React.CSSProperties}>
      <SiteHeader site={site} sections={sections} />
      <main>
        <SectionRenderer sections={sections} />
      </main>
      <footer className="border-t border-zinc-100 px-6 py-8 text-center text-sm text-zinc-500">
        © {new Date().getFullYear()} {site.name}
      </footer>
    </div>
  );
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const site = await getPublishedSite(slug);
  return { title: site?.name ?? "Site não encontrado" };
}

import { createClient } from "@/lib/supabase/server";
import type { BioLink, BioPage, Section, Site } from "@/lib/types";

/** Busca um site publicado pelo slug (para as páginas públicas). */
export async function getPublishedSite(slug: string): Promise<Site | null> {
  const supabase = await createClient();
  const { data } = await supabase
    .from("sites")
    .select("*")
    .eq("slug", slug)
    .eq("published", true)
    .maybeSingle();
  return data;
}

/** Seções habilitadas de um site, já ordenadas. */
export async function getEnabledSections(siteId: string): Promise<Section[]> {
  const supabase = await createClient();
  const { data } = await supabase
    .from("sections")
    .select("*")
    .eq("site_id", siteId)
    .eq("enabled", true)
    .order("position", { ascending: true });
  return data ?? [];
}

export async function getBioPage(siteId: string): Promise<BioPage | null> {
  const supabase = await createClient();
  const { data } = await supabase
    .from("bio_pages")
    .select("*")
    .eq("site_id", siteId)
    .eq("enabled", true)
    .maybeSingle();
  return data;
}

export async function getEnabledBioLinks(siteId: string): Promise<BioLink[]> {
  const supabase = await createClient();
  const { data } = await supabase
    .from("bio_links")
    .select("*")
    .eq("site_id", siteId)
    .eq("enabled", true)
    .order("position", { ascending: true });
  return data ?? [];
}

/** Site que o usuário logado administra (primeiro vínculo em site_members). */
export async function getSiteForCurrentUser(): Promise<Site | null> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return null;

  const { data: membership } = await supabase
    .from("site_members")
    .select("site_id")
    .eq("user_id", user.id)
    .limit(1)
    .maybeSingle();
  if (!membership) return null;

  const { data: site } = await supabase
    .from("sites")
    .select("*")
    .eq("id", membership.site_id)
    .maybeSingle();
  return site;
}

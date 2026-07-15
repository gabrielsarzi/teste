"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { getSiteForCurrentUser } from "@/lib/queries";
import type { SectionContentMap, SectionKey, Site } from "@/lib/types";
import { SECTION_KEYS } from "@/lib/types";

async function requireSite(): Promise<Site> {
  const site = await getSiteForCurrentUser();
  if (!site) redirect("/login");
  return site;
}

export async function signOut() {
  const supabase = await createClient();
  await supabase.auth.signOut();
  redirect("/login");
}

export async function toggleSection(formData: FormData) {
  const site = await requireSite();
  const key = String(formData.get("key"));
  const enabled = formData.get("enabled") === "true";

  const supabase = await createClient();
  await supabase
    .from("sections")
    .update({ enabled })
    .eq("site_id", site.id)
    .eq("key", key);

  revalidatePath("/admin");
  revalidatePath(`/${site.slug}`);
}

function buildSectionContent(
  key: SectionKey,
  formData: FormData
): SectionContentMap[SectionKey] {
  const f = (name: string) => String(formData.get(name) ?? "").trim();

  switch (key) {
    case "hero":
      return {
        title: f("title"),
        subtitle: f("subtitle"),
        image_url: f("image_url"),
        cta_label: f("cta_label"),
        cta_url: f("cta_url"),
      };
    case "about":
      return { title: f("title"), text: f("text"), image_url: f("image_url") };
    case "services":
      return { title: f("title"), items: parseJsonArray(f("items_json")) };
    case "gallery":
      return { title: f("title"), images: parseJsonArray(f("images_json")) };
    case "location":
      return {
        title: f("title"),
        address: f("address"),
        maps_embed_url: f("maps_embed_url"),
      };
    case "contact":
      return {
        title: f("title"),
        phone: f("phone"),
        whatsapp: f("whatsapp"),
        email: f("email"),
        instagram: f("instagram"),
        facebook: f("facebook"),
      };
  }
}

function parseJsonArray(raw: string) {
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export async function updateSectionContent(formData: FormData) {
  const site = await requireSite();
  const key = String(formData.get("key")) as SectionKey;
  if (!SECTION_KEYS.includes(key)) return;

  const content = buildSectionContent(key, formData);

  const supabase = await createClient();
  await supabase
    .from("sections")
    .update({ content })
    .eq("site_id", site.id)
    .eq("key", key);

  revalidatePath("/admin");
  revalidatePath(`/${site.slug}`);
  redirect("/admin");
}

export async function updateSiteSettings(formData: FormData) {
  const site = await requireSite();

  const supabase = await createClient();
  await supabase
    .from("sites")
    .update({
      name: String(formData.get("name") ?? site.name).trim() || site.name,
      published: formData.get("published") === "on",
      theme: { primary: String(formData.get("primary") ?? "#0ea5e9") },
    })
    .eq("id", site.id);

  revalidatePath("/admin/configuracoes");
  revalidatePath(`/${site.slug}`);
}

export async function updateBioPage(formData: FormData) {
  const site = await requireSite();

  const supabase = await createClient();
  await supabase
    .from("bio_pages")
    .update({
      enabled: formData.get("enabled") === "on",
      display_name: String(formData.get("display_name") ?? "").trim(),
      tagline: String(formData.get("tagline") ?? "").trim(),
      avatar_url: String(formData.get("avatar_url") ?? "").trim(),
    })
    .eq("site_id", site.id);

  revalidatePath("/admin/bio");
  revalidatePath(`/${site.slug}/bio`);
}

export async function addBioLink(formData: FormData) {
  const site = await requireSite();
  const label = String(formData.get("label") ?? "").trim();
  const url = String(formData.get("url") ?? "").trim();
  if (!label || !url) return;

  const supabase = await createClient();
  const { data: last } = await supabase
    .from("bio_links")
    .select("position")
    .eq("site_id", site.id)
    .order("position", { ascending: false })
    .limit(1)
    .maybeSingle();

  await supabase.from("bio_links").insert({
    site_id: site.id,
    label,
    url,
    position: (last?.position ?? -1) + 1,
  });

  revalidatePath("/admin/bio");
  revalidatePath(`/${site.slug}/bio`);
}

export async function updateBioLink(formData: FormData) {
  const site = await requireSite();
  const id = String(formData.get("id"));

  const supabase = await createClient();
  await supabase
    .from("bio_links")
    .update({
      label: String(formData.get("label") ?? "").trim(),
      url: String(formData.get("url") ?? "").trim(),
      position: Number(formData.get("position") ?? 0),
      enabled: formData.get("enabled") === "on",
    })
    .eq("id", id)
    .eq("site_id", site.id);

  revalidatePath("/admin/bio");
  revalidatePath(`/${site.slug}/bio`);
}

export async function deleteBioLink(formData: FormData) {
  const site = await requireSite();
  const id = String(formData.get("id"));

  const supabase = await createClient();
  await supabase.from("bio_links").delete().eq("id", id).eq("site_id", site.id);

  revalidatePath("/admin/bio");
  revalidatePath(`/${site.slug}/bio`);
}

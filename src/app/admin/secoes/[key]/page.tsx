import Link from "next/link";
import { notFound } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { getSiteForCurrentUser } from "@/lib/queries";
import {
  SECTION_KEYS,
  SECTION_LABELS,
  type Section,
  type SectionContentMap,
  type SectionKey,
} from "@/lib/types";
import { updateSectionContent } from "@/app/admin/actions";
import { ImageUploadField } from "@/components/admin/ImageUploadField";
import { ServicesEditor } from "@/components/admin/ServicesEditor";
import { GalleryEditor } from "@/components/admin/GalleryEditor";

export const dynamic = "force-dynamic";

const inputClass =
  "mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2";

function Field({
  label,
  name,
  defaultValue,
  placeholder,
}: {
  label: string;
  name: string;
  defaultValue: string;
  placeholder?: string;
}) {
  return (
    <label className="mt-4 block text-sm font-medium">
      {label}
      <input
        name={name}
        defaultValue={defaultValue}
        placeholder={placeholder}
        className={inputClass}
      />
    </label>
  );
}

export default async function EditSectionPage({
  params,
}: {
  params: Promise<{ key: string }>;
}) {
  const { key } = await params;
  if (!SECTION_KEYS.includes(key as SectionKey)) notFound();
  const sectionKey = key as SectionKey;

  const site = await getSiteForCurrentUser();
  if (!site) notFound();

  const supabase = await createClient();
  const { data } = await supabase
    .from("sections")
    .select("*")
    .eq("site_id", site.id)
    .eq("key", sectionKey)
    .maybeSingle();
  const section = data as Section | null;
  if (!section) notFound();

  return (
    <div className="mx-auto max-w-2xl">
      <Link href="/admin" className="text-sm text-zinc-500 hover:underline">
        ← Voltar
      </Link>
      <h1 className="mt-2 text-2xl font-bold">
        Editar: {SECTION_LABELS[sectionKey]}
      </h1>

      <form
        action={updateSectionContent}
        className="mt-6 rounded-2xl border border-zinc-200 bg-white p-6"
      >
        <input type="hidden" name="key" value={sectionKey} />
        <SectionFields sectionKey={sectionKey} section={section} site={site} />

        <button
          type="submit"
          className="mt-8 w-full rounded-lg bg-zinc-900 py-2.5 font-medium text-white transition hover:bg-zinc-700 sm:w-auto sm:px-8"
        >
          Salvar
        </button>
      </form>
    </div>
  );
}

function SectionFields({
  sectionKey,
  section,
  site,
}: {
  sectionKey: SectionKey;
  section: Section;
  site: { id: string };
}) {
  switch (sectionKey) {
    case "hero": {
      const c = section.content as SectionContentMap["hero"];
      return (
        <>
          <Field label="Título" name="title" defaultValue={c.title} />
          <Field label="Subtítulo" name="subtitle" defaultValue={c.subtitle} />
          <ImageUploadField
            name="image_url"
            label="Imagem de fundo"
            siteId={site.id}
            defaultValue={c.image_url}
          />
          <Field
            label="Texto do botão"
            name="cta_label"
            defaultValue={c.cta_label}
          />
          <Field
            label="Link do botão"
            name="cta_url"
            defaultValue={c.cta_url}
            placeholder="#contact ou https://..."
          />
        </>
      );
    }
    case "about": {
      const c = section.content as SectionContentMap["about"];
      return (
        <>
          <Field label="Título" name="title" defaultValue={c.title} />
          <label className="mt-4 block text-sm font-medium">
            Texto
            <textarea
              name="text"
              defaultValue={c.text}
              rows={6}
              className={inputClass}
            />
          </label>
          <ImageUploadField
            name="image_url"
            label="Imagem"
            siteId={site.id}
            defaultValue={c.image_url}
          />
        </>
      );
    }
    case "services": {
      const c = section.content as SectionContentMap["services"];
      return (
        <>
          <Field label="Título" name="title" defaultValue={c.title} />
          <ServicesEditor defaultItems={c.items} />
        </>
      );
    }
    case "gallery": {
      const c = section.content as SectionContentMap["gallery"];
      return (
        <>
          <Field label="Título" name="title" defaultValue={c.title} />
          <GalleryEditor siteId={site.id} defaultImages={c.images} />
        </>
      );
    }
    case "location": {
      const c = section.content as SectionContentMap["location"];
      return (
        <>
          <Field label="Título" name="title" defaultValue={c.title} />
          <Field label="Endereço" name="address" defaultValue={c.address} />
          <Field
            label="Link de embed do Google Maps"
            name="maps_embed_url"
            defaultValue={c.maps_embed_url}
            placeholder="https://www.google.com/maps/embed?..."
          />
          <p className="mt-1 text-xs text-zinc-500">
            No Google Maps: Compartilhar → Incorporar um mapa → copie apenas a
            URL do src.
          </p>
        </>
      );
    }
    case "contact": {
      const c = section.content as SectionContentMap["contact"];
      return (
        <>
          <Field label="Título" name="title" defaultValue={c.title} />
          <Field
            label="WhatsApp (com DDD)"
            name="whatsapp"
            defaultValue={c.whatsapp}
            placeholder="5511999999999"
          />
          <Field label="Telefone" name="phone" defaultValue={c.phone} />
          <Field label="E-mail" name="email" defaultValue={c.email} />
          <Field
            label="Instagram (usuário)"
            name="instagram"
            defaultValue={c.instagram}
            placeholder="minhaempresa"
          />
          <Field label="Facebook" name="facebook" defaultValue={c.facebook} />
        </>
      );
    }
  }
}

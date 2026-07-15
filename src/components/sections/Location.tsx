import type { LocationContent } from "@/lib/types";

export function Location({ content }: { content: LocationContent }) {
  return (
    <section id="location" className="bg-zinc-50 px-6 py-16 sm:py-24">
      <div className="mx-auto max-w-5xl">
        <h2 className="text-center text-3xl font-bold">{content.title}</h2>
        {content.address && (
          <p className="mt-4 text-center text-zinc-600">{content.address}</p>
        )}
        {content.maps_embed_url && (
          <div className="mt-8 overflow-hidden rounded-2xl shadow-md">
            <iframe
              src={content.maps_embed_url}
              className="h-80 w-full border-0"
              loading="lazy"
              referrerPolicy="no-referrer-when-downgrade"
              title="Mapa"
            />
          </div>
        )}
      </div>
    </section>
  );
}

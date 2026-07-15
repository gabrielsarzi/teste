import type { GalleryContent } from "@/lib/types";

export function Gallery({ content }: { content: GalleryContent }) {
  return (
    <section id="gallery" className="mx-auto max-w-5xl px-6 py-16 sm:py-24">
      <h2 className="text-center text-3xl font-bold">{content.title}</h2>
      <div className="mt-10 grid grid-cols-2 gap-3 sm:grid-cols-3">
        {content.images.map((image, i) => (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            key={i}
            src={image.url}
            alt={image.alt}
            loading="lazy"
            className="aspect-square w-full rounded-xl object-cover"
          />
        ))}
      </div>
    </section>
  );
}

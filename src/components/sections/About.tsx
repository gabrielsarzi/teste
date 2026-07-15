import type { AboutContent } from "@/lib/types";

export function About({ content }: { content: AboutContent }) {
  return (
    <section id="about" className="mx-auto max-w-5xl px-6 py-16 sm:py-24">
      <div className="grid items-center gap-10 sm:grid-cols-2">
        <div>
          <h2 className="text-3xl font-bold">{content.title}</h2>
          <p className="mt-4 whitespace-pre-line leading-relaxed text-zinc-600">
            {content.text}
          </p>
        </div>
        {content.image_url && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={content.image_url}
            alt={content.title}
            className="w-full rounded-2xl object-cover shadow-md"
          />
        )}
      </div>
    </section>
  );
}

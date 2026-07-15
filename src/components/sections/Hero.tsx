import type { HeroContent } from "@/lib/types";

export function Hero({ content }: { content: HeroContent }) {
  return (
    <section
      id="hero"
      className="relative flex min-h-[70vh] items-center justify-center overflow-hidden bg-zinc-900 px-6 py-24 text-center text-white"
    >
      {content.image_url && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={content.image_url}
          alt=""
          className="absolute inset-0 h-full w-full object-cover opacity-40"
        />
      )}
      <div className="relative z-10 mx-auto max-w-2xl">
        <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
          {content.title}
        </h1>
        {content.subtitle && (
          <p className="mt-4 text-lg text-zinc-200">{content.subtitle}</p>
        )}
        {content.cta_label && (
          <a
            href={content.cta_url || "#contact"}
            className="mt-8 inline-block rounded-full bg-primary px-8 py-3 font-semibold text-white shadow-lg transition hover:opacity-90"
          >
            {content.cta_label}
          </a>
        )}
      </div>
    </section>
  );
}

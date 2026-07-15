import type { ServicesContent } from "@/lib/types";

export function Services({ content }: { content: ServicesContent }) {
  return (
    <section id="services" className="bg-zinc-50 px-6 py-16 sm:py-24">
      <div className="mx-auto max-w-5xl">
        <h2 className="text-center text-3xl font-bold">{content.title}</h2>
        <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {content.items.map((item, i) => (
            <div
              key={i}
              className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm"
            >
              <h3 className="text-lg font-semibold">{item.name}</h3>
              {item.description && (
                <p className="mt-2 text-sm text-zinc-600">{item.description}</p>
              )}
              {item.price && (
                <p className="mt-4 font-semibold text-primary">{item.price}</p>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

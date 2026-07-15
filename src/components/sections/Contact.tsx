import type { ContactContent } from "@/lib/types";

function onlyDigits(value: string) {
  return value.replace(/\D/g, "");
}

export function Contact({ content }: { content: ContactContent }) {
  const items = [
    content.whatsapp && {
      label: "WhatsApp",
      value: content.whatsapp,
      href: `https://wa.me/${onlyDigits(content.whatsapp)}`,
    },
    content.phone && {
      label: "Telefone",
      value: content.phone,
      href: `tel:${onlyDigits(content.phone)}`,
    },
    content.email && {
      label: "E-mail",
      value: content.email,
      href: `mailto:${content.email}`,
    },
    content.instagram && {
      label: "Instagram",
      value: `@${content.instagram.replace(/^@/, "")}`,
      href: `https://instagram.com/${content.instagram.replace(/^@/, "")}`,
    },
    content.facebook && {
      label: "Facebook",
      value: content.facebook,
      href: content.facebook.startsWith("http")
        ? content.facebook
        : `https://facebook.com/${content.facebook}`,
    },
  ].filter(Boolean) as { label: string; value: string; href: string }[];

  return (
    <section id="contact" className="mx-auto max-w-5xl px-6 py-16 sm:py-24">
      <h2 className="text-center text-3xl font-bold">{content.title}</h2>
      <div className="mx-auto mt-10 grid max-w-lg gap-4">
        {items.map((item) => (
          <a
            key={item.label}
            href={item.href}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-between rounded-xl border border-zinc-200 px-5 py-4 shadow-sm transition hover:border-primary hover:shadow"
          >
            <span className="font-medium">{item.label}</span>
            <span className="text-sm text-zinc-600">{item.value}</span>
          </a>
        ))}
      </div>
    </section>
  );
}

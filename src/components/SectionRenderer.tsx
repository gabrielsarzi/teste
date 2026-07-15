import type { Section, SectionContentMap } from "@/lib/types";
import { Hero } from "@/components/sections/Hero";
import { About } from "@/components/sections/About";
import { Services } from "@/components/sections/Services";
import { Gallery } from "@/components/sections/Gallery";
import { Location } from "@/components/sections/Location";
import { Contact } from "@/components/sections/Contact";

/**
 * Renderiza as seções habilitadas do site, na ordem configurada.
 * Ativar/desativar uma seção no painel só muda dados — nada de código.
 */
export function SectionRenderer({ sections }: { sections: Section[] }) {
  return (
    <>
      {sections.map((section) => {
        switch (section.key) {
          case "hero":
            return (
              <Hero
                key={section.id}
                content={section.content as SectionContentMap["hero"]}
              />
            );
          case "about":
            return (
              <About
                key={section.id}
                content={section.content as SectionContentMap["about"]}
              />
            );
          case "services":
            return (
              <Services
                key={section.id}
                content={section.content as SectionContentMap["services"]}
              />
            );
          case "gallery":
            return (
              <Gallery
                key={section.id}
                content={section.content as SectionContentMap["gallery"]}
              />
            );
          case "location":
            return (
              <Location
                key={section.id}
                content={section.content as SectionContentMap["location"]}
              />
            );
          case "contact":
            return (
              <Contact
                key={section.id}
                content={section.content as SectionContentMap["contact"]}
              />
            );
          default:
            return null;
        }
      })}
    </>
  );
}

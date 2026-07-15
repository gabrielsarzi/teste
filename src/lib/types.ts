// Modelo central da plataforma: um Site por cliente, com seções
// configuráveis e uma página bio opcional.

export const SECTION_KEYS = [
  "hero",
  "about",
  "services",
  "gallery",
  "location",
  "contact",
] as const;

export type SectionKey = (typeof SECTION_KEYS)[number];

export const SECTION_LABELS: Record<SectionKey, string> = {
  hero: "Início",
  about: "Sobre",
  services: "Serviços",
  gallery: "Galeria",
  location: "Localização",
  contact: "Contato",
};

export interface Theme {
  /** Cor primária em hex, ex: #0ea5e9 */
  primary: string;
}

export interface Site {
  id: string;
  slug: string;
  name: string;
  custom_domain: string | null;
  published: boolean;
  theme: Theme;
  created_at: string;
}

export interface HeroContent {
  title: string;
  subtitle: string;
  image_url: string;
  cta_label: string;
  cta_url: string;
}

export interface AboutContent {
  title: string;
  text: string;
  image_url: string;
}

export interface ServiceItem {
  name: string;
  description: string;
  price: string;
}

export interface ServicesContent {
  title: string;
  items: ServiceItem[];
}

export interface GalleryImage {
  url: string;
  alt: string;
}

export interface GalleryContent {
  title: string;
  images: GalleryImage[];
}

export interface LocationContent {
  title: string;
  address: string;
  maps_embed_url: string;
}

export interface ContactContent {
  title: string;
  phone: string;
  whatsapp: string;
  email: string;
  instagram: string;
  facebook: string;
}

export interface SectionContentMap {
  hero: HeroContent;
  about: AboutContent;
  services: ServicesContent;
  gallery: GalleryContent;
  location: LocationContent;
  contact: ContactContent;
}

export interface Section<K extends SectionKey = SectionKey> {
  id: string;
  site_id: string;
  key: K;
  enabled: boolean;
  position: number;
  content: SectionContentMap[K];
}

export interface BioPage {
  site_id: string;
  enabled: boolean;
  display_name: string;
  tagline: string;
  avatar_url: string;
}

export interface BioLink {
  id: string;
  site_id: string;
  label: string;
  url: string;
  position: number;
  enabled: boolean;
}

export const DEFAULT_SECTION_CONTENT: SectionContentMap = {
  hero: {
    title: "Bem-vindo",
    subtitle: "Apresente seu negócio em uma frase.",
    image_url: "",
    cta_label: "Fale conosco",
    cta_url: "#contact",
  },
  about: {
    title: "Sobre nós",
    text: "Conte a história do seu negócio aqui.",
    image_url: "",
  },
  services: {
    title: "Serviços",
    items: [],
  },
  gallery: {
    title: "Galeria",
    images: [],
  },
  location: {
    title: "Onde estamos",
    address: "",
    maps_embed_url: "",
  },
  contact: {
    title: "Contato",
    phone: "",
    whatsapp: "",
    email: "",
    instagram: "",
    facebook: "",
  },
};

"use client";

import { useState } from "react";
import type { GalleryImage } from "@/lib/types";
import { uploadImage } from "@/lib/upload";

/** Editor da galeria: upload múltiplo + remoção; serializa em JSON. */
export function GalleryEditor({
  siteId,
  defaultImages,
}: {
  siteId: string;
  defaultImages: GalleryImage[];
}) {
  const [images, setImages] = useState<GalleryImage[]>(defaultImages);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFiles(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    if (files.length === 0) return;

    setUploading(true);
    setError(null);
    try {
      const uploaded: GalleryImage[] = [];
      for (const file of files) {
        uploaded.push({ url: await uploadImage(siteId, file), alt: "" });
      }
      setImages((prev) => [...prev, ...uploaded]);
    } catch {
      setError("Falha no upload. Tente novamente.");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  return (
    <div className="mt-4">
      <span className="block text-sm font-medium">Fotos</span>
      <input type="hidden" name="images_json" value={JSON.stringify(images)} />

      <div className="mt-2 grid grid-cols-3 gap-3 sm:grid-cols-4">
        {images.map((image, i) => (
          <div key={i} className="group relative">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={image.url}
              alt={image.alt}
              className="aspect-square w-full rounded-lg object-cover"
            />
            <button
              type="button"
              onClick={() => setImages(images.filter((_, j) => j !== i))}
              className="absolute right-1 top-1 rounded-full bg-black/60 px-2 py-0.5 text-xs text-white opacity-0 transition group-hover:opacity-100"
            >
              ✕
            </button>
          </div>
        ))}
      </div>

      <input
        type="file"
        accept="image/*"
        multiple
        onChange={handleFiles}
        disabled={uploading}
        className="mt-3 text-sm"
      />
      {uploading && <p className="mt-1 text-sm text-zinc-500">Enviando...</p>}
      {error && <p className="mt-1 text-sm text-red-600">{error}</p>}
    </div>
  );
}

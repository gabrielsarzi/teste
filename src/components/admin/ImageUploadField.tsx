"use client";

import { useState } from "react";
import { uploadImage } from "@/lib/upload";

/**
 * Campo de imagem para formulários do painel: faz o upload na hora e
 * guarda a URL num input hidden que segue junto com o form.
 */
export function ImageUploadField({
  name,
  label,
  siteId,
  defaultValue,
}: {
  name: string;
  label: string;
  siteId: string;
  defaultValue: string;
}) {
  const [url, setUrl] = useState(defaultValue);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setError(null);
    try {
      setUrl(await uploadImage(siteId, file));
    } catch {
      setError("Falha no upload. Tente novamente.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="mt-4">
      <span className="block text-sm font-medium">{label}</span>
      <input type="hidden" name={name} value={url} />

      {url && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={url}
          alt=""
          className="mt-2 h-32 w-full max-w-xs rounded-lg object-cover"
        />
      )}

      <div className="mt-2 flex items-center gap-3">
        <input
          type="file"
          accept="image/*"
          onChange={handleFile}
          disabled={uploading}
          className="text-sm"
        />
        {url && (
          <button
            type="button"
            onClick={() => setUrl("")}
            className="text-sm text-red-600 hover:underline"
          >
            Remover
          </button>
        )}
      </div>

      {uploading && <p className="mt-1 text-sm text-zinc-500">Enviando...</p>}
      {error && <p className="mt-1 text-sm text-red-600">{error}</p>}
    </div>
  );
}

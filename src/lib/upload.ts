import { createClient } from "@/lib/supabase/client";

/**
 * Sobe uma imagem para o bucket público e devolve a URL final.
 * Os arquivos ficam em uma pasta por site (<site_id>/...), que é o que a
 * política de storage usa para autorizar o upload.
 */
export async function uploadImage(siteId: string, file: File): Promise<string> {
  const supabase = createClient();
  const ext = file.name.split(".").pop() ?? "jpg";
  const path = `${siteId}/${crypto.randomUUID()}.${ext}`;

  const { error } = await supabase.storage.from("images").upload(path, file);
  if (error) throw error;

  const { data } = supabase.storage.from("images").getPublicUrl(path);
  return data.publicUrl;
}

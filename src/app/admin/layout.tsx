import Link from "next/link";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { signOut } from "@/app/admin/actions";

export const dynamic = "force-dynamic";

export default async function AdminLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login");

  return (
    <div className="min-h-screen bg-zinc-50">
      <header className="border-b border-zinc-200 bg-white">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
          <Link href="/admin" className="font-bold">
            Painel
          </Link>
          <nav className="flex items-center gap-4 text-sm">
            <Link href="/admin" className="text-zinc-600 hover:text-zinc-900">
              Seções
            </Link>
            <Link
              href="/admin/bio"
              className="text-zinc-600 hover:text-zinc-900"
            >
              Bio
            </Link>
            <Link
              href="/admin/configuracoes"
              className="text-zinc-600 hover:text-zinc-900"
            >
              Configurações
            </Link>
            <form action={signOut}>
              <button className="text-zinc-400 hover:text-zinc-900">
                Sair
              </button>
            </form>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-4xl px-6 py-8">{children}</main>
    </div>
  );
}

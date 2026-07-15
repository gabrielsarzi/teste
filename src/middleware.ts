import { NextResponse, type NextRequest } from "next/server";
import { updateSession } from "@/lib/supabase/middleware";

const ROOT_DOMAIN = process.env.NEXT_PUBLIC_ROOT_DOMAIN ?? "localhost:3000";

/**
 * Multi-tenant por domínio: quando o cliente aponta o domínio próprio
 * (ex: www.padariadojoao.com.br) para a plataforma, o middleware descobre
 * o slug correspondente e reescreve a URL para /[slug]/... — o visitante
 * nunca vê o slug na barra de endereço.
 */
export async function middleware(request: NextRequest) {
  const host = request.headers.get("host") ?? "";
  const { pathname } = request.nextUrl;

  // Painel e login: só renova a sessão de auth.
  if (pathname.startsWith("/admin") || pathname.startsWith("/login")) {
    return updateSession(request);
  }

  // Acesso pelo domínio da plataforma segue o roteamento normal
  // (/, /admin, /[slug], ...).
  if (host === ROOT_DOMAIN || host.endsWith(`.${ROOT_DOMAIN}`)) {
    return NextResponse.next();
  }

  const slug = await lookupSlugByDomain(host.replace(/^www\./, ""));
  if (!slug) {
    return NextResponse.next();
  }

  const url = request.nextUrl.clone();
  url.pathname = `/${slug}${pathname === "/" ? "" : pathname}`;
  return NextResponse.rewrite(url);
}

async function lookupSlugByDomain(domain: string): Promise<string | null> {
  const base = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!base || !anonKey) return null;

  try {
    const res = await fetch(
      `${base}/rest/v1/sites?custom_domain=eq.${encodeURIComponent(domain)}&published=eq.true&select=slug`,
      {
        headers: { apikey: anonKey, Authorization: `Bearer ${anonKey}` },
        next: { revalidate: 60 },
      }
    );
    if (!res.ok) return null;
    const rows: { slug: string }[] = await res.json();
    return rows[0]?.slug ?? null;
  } catch {
    return null;
  }
}

export const config = {
  // Ignora assets estáticos e rotas internas do Next.
  matcher: ["/((?!_next/|api/|favicon.ico|.*\\..*).*)"],
};

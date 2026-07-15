import Link from "next/link";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-6 text-center">
      <h1 className="text-4xl font-bold tracking-tight">
        Landing Page Builder
      </h1>
      <p className="max-w-md text-zinc-600">
        Sites profissionais para pequenas empresas, com painel próprio para o
        cliente editar tudo sem tocar em código.
      </p>
      <Link
        href="/admin"
        className="rounded-lg bg-zinc-900 px-6 py-3 font-medium text-white transition hover:bg-zinc-700"
      >
        Acessar painel
      </Link>
    </main>
  );
}

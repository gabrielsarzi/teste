"use client";

import { useState } from "react";
import type { ServiceItem } from "@/lib/types";

/** Editor da lista de serviços; serializa tudo num hidden input JSON. */
export function ServicesEditor({
  defaultItems,
}: {
  defaultItems: ServiceItem[];
}) {
  const [items, setItems] = useState<ServiceItem[]>(defaultItems);

  function update(index: number, patch: Partial<ServiceItem>) {
    setItems(items.map((it, i) => (i === index ? { ...it, ...patch } : it)));
  }

  function move(index: number, delta: number) {
    const target = index + delta;
    if (target < 0 || target >= items.length) return;
    const next = [...items];
    [next[index], next[target]] = [next[target], next[index]];
    setItems(next);
  }

  return (
    <div className="mt-4">
      <span className="block text-sm font-medium">Serviços</span>
      <input type="hidden" name="items_json" value={JSON.stringify(items)} />

      <div className="mt-2 flex flex-col gap-3">
        {items.map((item, i) => (
          <div key={i} className="rounded-xl border border-zinc-200 p-4">
            <div className="flex gap-2">
              <input
                placeholder="Nome do serviço"
                value={item.name}
                onChange={(e) => update(i, { name: e.target.value })}
                className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm"
              />
              <input
                placeholder="Preço (opcional)"
                value={item.price}
                onChange={(e) => update(i, { price: e.target.value })}
                className="w-40 rounded-lg border border-zinc-300 px-3 py-2 text-sm"
              />
            </div>
            <textarea
              placeholder="Descrição (opcional)"
              value={item.description}
              onChange={(e) => update(i, { description: e.target.value })}
              rows={2}
              className="mt-2 w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm"
            />
            <div className="mt-2 flex gap-3 text-sm">
              <button type="button" onClick={() => move(i, -1)}>
                ↑
              </button>
              <button type="button" onClick={() => move(i, 1)}>
                ↓
              </button>
              <button
                type="button"
                onClick={() => setItems(items.filter((_, j) => j !== i))}
                className="text-red-600 hover:underline"
              >
                Remover
              </button>
            </div>
          </div>
        ))}
      </div>

      <button
        type="button"
        onClick={() =>
          setItems([...items, { name: "", description: "", price: "" }])
        }
        className="mt-3 rounded-lg border border-zinc-300 px-4 py-2 text-sm hover:bg-zinc-50"
      >
        + Adicionar serviço
      </button>
    </div>
  );
}

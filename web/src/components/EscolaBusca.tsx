import { useMemo, useState } from "react";
import type { EscolaInfo, Selecao } from "../lib/api";
import { campo } from "./ui";

const norm = (s: string) => s.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();

export function EscolaBusca({
  escolas,
  pontos,
  onEscolher,
}: {
  escolas: EscolaInfo[];
  pontos: Extract<Selecao, { tipo: "ponto" }>[];
  onEscolher: (s: Selecao) => void;
}) {
  const [q, setQ] = useState("");
  const resultados = useMemo(() => {
    const t = norm(q.trim());
    if (t.length < 2) return [];
    const e = escolas
      .filter((x) => norm(`${x.nome} ${x.bairro ?? ""} ${x.id}`).includes(t))
      .slice(0, 8)
      .map((x) => ({ sel: { tipo: "escola", id: x.id, nome: x.nome } as Selecao, sub: `${x.bairro} · INEP ${x.id}` }));
    const p = pontos
      .filter((x) => norm(x.nome).includes(t))
      .map((x) => ({ sel: x as Selecao, sub: "ponto de previsão" }));
    return [...p, ...e];
  }, [q, escolas, pontos]);

  return (
    <div className="relative w-full sm:w-80">
      <label htmlFor="busca-escola" className="sr-only">
        Buscar escola por nome, bairro ou código INEP
      </label>
      <input
        id="busca-escola"
        className={`${campo} w-full`}
        placeholder="Buscar escola, bairro ou INEP…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        autoComplete="off"
      />
      {resultados.length > 0 && (
        <ul className="absolute left-0 right-0 top-full z-[1100] mt-1 max-h-80 overflow-auto border border-line bg-surface shadow-lg">
          {resultados.map((r) => (
            <li key={r.sel.tipo === "escola" ? r.sel.id : r.sel.nome}>
              <button
                type="button"
                className="block w-full px-3 py-2 text-left hover:bg-raised focus-visible:bg-raised focus-visible:outline-none"
                onClick={() => {
                  onEscolher(r.sel);
                  setQ("");
                }}
              >
                <span className="block text-sm">{r.sel.nome}</span>
                <span className="block text-xs text-muted">{r.sub}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

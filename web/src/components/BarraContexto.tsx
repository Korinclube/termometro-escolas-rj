import type { Cenario, EscolaInfo, Meta, SalaParams, Selecao } from "../lib/api";
import type { Telhado } from "../lib/fisica";
import { ROTULO_TELHADO } from "../lib/formato";
import { EscolaBusca } from "./EscolaBusca";
import { Subtitulo, campo } from "./ui";

export function BarraContexto({
  meta,
  escolas,
  pontos,
  sel,
  onSel,
  cenario,
  onCenario,
  sala,
  onSala,
}: {
  meta: Meta | null;
  escolas: EscolaInfo[];
  pontos: Extract<Selecao, { tipo: "ponto" }>[];
  sel: Selecao;
  onSel: (s: Selecao) => void;
  cenario: Cenario;
  onCenario: (c: Cenario) => void;
  sala: SalaParams;
  onSala: (s: SalaParams) => void;
}) {
  const info = sel.tipo === "escola" ? escolas.find((e) => e.id === sel.id) : undefined;
  return (
    <div className="no-print border-b border-line bg-canvas">
      <div className="mx-auto flex max-w-7xl flex-wrap items-end gap-x-6 gap-y-3 px-4 py-3">
        <div className="min-w-0 flex-1 basis-64">
          <Subtitulo>Escola em análise</Subtitulo>
          <div className="truncate font-display font-bold">{sel.nome}</div>
          <div className="truncate text-xs text-muted">
            {info
              ? <>{info.rede} · {info.bairro} · INEP <span className="num">{info.id}</span> · <span className="num">{info.alunos}</span> alunos</>
              : sel.tipo === "ponto"
                ? <>Ponto de previsão · <span className="num">{sel.lat.toFixed(3).replace(".", ",")}; {sel.lon.toFixed(3).replace(".", ",")}</span></>
                : ""}
          </div>
        </div>
        <EscolaBusca escolas={escolas} pontos={pontos} onEscolher={onSel} />
        <label className="flex w-full min-w-0 flex-col gap-1 text-xs text-muted sm:w-auto">
          Cenário
          <select className={`${campo} w-full min-w-0 sm:w-auto`} value={cenario} onChange={(e) => onCenario(e.target.value as Cenario)}>
            {meta &&
              (Object.entries(meta.cenarios) as [Cenario, string][]).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
          </select>
        </label>
        <label className="flex w-full min-w-0 flex-col gap-1 text-xs text-muted sm:w-auto">
          Telhado da sala
          <select
            className={`${campo} w-full min-w-0 sm:w-auto`}
            value={sala.telhado}
            onChange={(e) => onSala({ ...sala, telhado: e.target.value as Telhado })}
          >
            {Object.entries(ROTULO_TELHADO).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 pb-1.5 text-sm">
          <input
            type="checkbox"
            checked={sala.climatizada}
            onChange={(e) => onSala({ ...sala, climatizada: e.target.checked })}
          />
          Ar-condicionado funcionando
        </label>
      </div>
      {cenario !== "ao_vivo" && (
        <div className="border-t border-atencao/40 bg-atencao/10 px-4 py-1.5 text-center text-xs">
          Simulação ativa: {meta?.cenarios[cenario]}. Não é a previsão de hoje.
        </div>
      )}
    </div>
  );
}

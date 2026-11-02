import { useEffect, useMemo, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Previsao, SalaParams } from "../lib/api";
import { FAIXAS, LIMIAR, calcularHora, type Faixa, type Telhado } from "../lib/fisica";
import { ROTULO_TELHADO, grau, grauSinal, rotuloDia } from "../lib/formato";
import { BarraFaixas, Botao, Carregando, Erro, Secao, Subtitulo } from "../components/ui";

function resumir(horas: { faixa: Faixa; icSala: number; tSala: number; aula: boolean }[]) {
  const aula = horas.filter((h) => h.aula);
  const porFaixa = Object.fromEntries(FAIXAS.map((f) => [f, aula.filter((h) => h.faixa === f).length])) as Record<Faixa, number>;
  return {
    porFaixa,
    total: aula.length,
    icMax: Math.max(...aula.map((h) => h.icSala), 0),
    tMax: Math.max(...aula.map((h) => h.tSala), 0),
  };
}

function BarraHoras({ titulo, r }: { titulo: string; r: ReturnType<typeof resumir> }) {
  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <Subtitulo>{titulo}</Subtitulo>
        <span className="num text-xs text-muted">ar máx. {grau(r.tMax)} · IC máx. {grau(r.icMax)}</span>
      </div>
      <BarraFaixas contagem={r.porFaixa} unidade="h" />
    </div>
  );
}

export function Simulador({
  previsao,
  sala,
  onAplicar,
}: {
  previsao: { dados: Previsao | null; erro: string | null; carregando: boolean };
  sala: SalaParams;
  onAplicar: (s: SalaParams) => void;
}) {
  const [sim, setSim] = useState<SalaParams>(sala);
  useEffect(() => setSim(sala), [sala]);

  const linhas = useMemo(() => {
    const d = previsao.dados;
    if (!d) return [];
    const datas = new Set(d.dias.filter((x) => x.previsao).map((x) => x.data));
    return d.horas
      .filter((h) => datas.has(h.hora.slice(0, 10)))
      .map((h) => {
        const base = calcularHora(h.t_ext, h.rh_ext, sala);
        const novo = calcularHora(h.t_ext, h.rh_ext, sim);
        return { hora: h.hora, aula: h.aula, base, novo };
      });
  }, [previsao.dados, sala, sim]);

  const rBase = resumir(linhas.map((l) => ({ ...l.base, aula: l.aula })));
  const rNovo = resumir(linhas.map((l) => ({ ...l.novo, aula: l.aula })));
  const mudou = JSON.stringify(sim) !== JSON.stringify(sala);

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[320px_minmax(0,1fr)]">
      <Secao titulo="Parâmetros da sala" meta="Recalcula na hora, sobre a mesma previsão da rua.">
        <div className="grid gap-4">
          <fieldset>
            <legend className="mb-2 text-xs text-muted">Telhado da sala</legend>
            <div className="grid gap-1.5">
              {(Object.keys(ROTULO_TELHADO) as Telhado[]).map((t) => (
                <label key={t} className="flex items-center gap-2 text-sm">
                  <input type="radio" name="telhado-sim" checked={sim.telhado === t} onChange={() => setSim({ ...sim, telhado: t })} />
                  {ROTULO_TELHADO[t]}
                </label>
              ))}
            </div>
          </fieldset>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={sim.climatizada} onChange={(e) => setSim({ ...sim, climatizada: e.target.checked })} />
            Ar-condicionado funcionando (teto de 24 °C)
          </label>
          <label className="text-xs text-muted">
            Ajuste manual na sala: <span className="num text-ink">{grauSinal(sim.ajuste)}</span>
            <input
              type="range" min={-3} max={3} step={0.5} value={sim.ajuste}
              onChange={(e) => setSim({ ...sim, ajuste: Number(e.target.value) })}
              className="mt-2 w-full"
            />
            <span className="mt-1 block">
              Hipótese para lotação ou ventilação. Referência: numa escola do Paraná com fibrocimento, a sala com ~25 alunos
              ficou em média 3 °C acima de uma pouco ocupada. Não é medida desta escola.
            </span>
          </label>
          <div className="flex flex-wrap gap-2">
            <Botao primario disabled={!mudou} onClick={() => onAplicar(sim)}>Aplicar ao painel</Botao>
            <Botao disabled={!mudou} onClick={() => setSim(sala)}>Desfazer</Botao>
          </div>
        </div>
      </Secao>

      <Secao
        titulo="Antes e depois"
        meta={`Atual: ${ROTULO_TELHADO[sala.telhado]}${sala.climatizada ? ", ar-condicionado funcionando" : ""} · Simulada: ${ROTULO_TELHADO[sim.telhado]}${sim.climatizada ? ", ar-condicionado funcionando" : ""}`}
      >
        {previsao.carregando && <Carregando />}
        {previsao.erro && <Erro mensagem={previsao.erro} />}
        {linhas.length > 0 && (
          <>
            <div className="grid gap-4 md:grid-cols-2">
              <BarraHoras titulo="Atual (estimado)" r={rBase} />
              <BarraHoras titulo="Simulada (estimado)" r={rNovo} />
            </div>
            <div className="mt-5 h-[300px]" role="img" aria-label="Índice de calor na sala, atual e simulado">
              <ResponsiveContainer>
                <LineChart data={linhas.map((l) => ({ hora: l.hora, atual: l.base.icSala, simulada: l.novo.icSala }))} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
                  <CartesianGrid stroke="rgb(var(--line))" vertical={false} />
                  <XAxis dataKey="hora" interval={11} tick={{ fontSize: 11, fill: "rgb(var(--muted))" }} tickFormatter={(v: string) => `${rotuloDia(v.slice(0, 10))} ${v.slice(11, 13)}h`} />
                  <YAxis unit="°" allowDecimals={false} tick={{ fontSize: 11, fill: "rgb(var(--muted))" }} domain={[(m: number) => Math.floor(m - 2), (m: number) => Math.ceil(m + 2)]} />
                  <ReferenceLine y={LIMIAR.alertaIC} stroke="rgb(var(--faixa-alerta))" strokeDasharray="1 3" />
                  <ReferenceLine y={LIMIAR.perigoIC} stroke="rgb(var(--faixa-perigo))" strokeDasharray="1 3" />
                  <Tooltip
                    contentStyle={{ background: "rgb(var(--surface))", border: "1px solid rgb(var(--line))", fontSize: 12 }}
                    formatter={(v: number, n: string) => [grau(v), n]}
                  />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Line dataKey="atual" name="IC na sala · atual (estimado)" stroke="rgb(var(--muted))" dot={false} isAnimationActive={false} />
                  <Line dataKey="simulada" name="IC na sala · simulada (estimado)" stroke="rgb(var(--accent))" strokeWidth={2} dot={false} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <p className="mt-2 text-xs text-muted">
              Contagem em horas de aula (7h–17h, seg–sex) nas próximas 72 h. Os deslocamentos por telhado vêm de um estudo
              em Acra (Gana) e valem até haver sensores nas escolas do Rio.
            </p>
          </>
        )}
      </Secao>
    </div>
  );
}

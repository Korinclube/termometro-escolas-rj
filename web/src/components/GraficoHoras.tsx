import {
  CartesianGrid, ComposedChart, Legend, Line, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { LIMIAR } from "../lib/fisica";
import { grau, rotuloDia } from "../lib/formato";

export interface PontoGrafico {
  hora: string;
  t_ext: number;
  t_sala: number;
  ic_sala: number;
  aula: boolean;
}

const eixo = { fontSize: 11, fill: "rgb(var(--muted))" };

/** Linhas da rua e da sala hora a hora, com o horário de aula sombreado. */
export function GraficoHoras({ horas, altura = 300 }: { horas: PontoGrafico[]; altura?: number }) {
  const blocos: { x1: string; x2: string }[] = [];
  let ini: string | null = null;
  horas.forEach((h, i) => {
    if (h.aula && ini === null) ini = h.hora;
    const fim = !horas[i + 1]?.aula;
    if (h.aula && fim && ini) {
      blocos.push({ x1: ini, x2: h.hora });
      ini = null;
    }
  });
  const max = Math.max(48, ...horas.map((h) => Math.ceil(h.ic_sala + 2)));
  const min = Math.min(...horas.map((h) => Math.floor(h.t_ext - 2)));

  return (
    <div style={{ height: altura }} role="img" aria-label="Gráfico horário de temperatura da rua, temperatura e índice de calor da sala">
      <ResponsiveContainer>
        <ComposedChart data={horas} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
          <CartesianGrid stroke="rgb(var(--line))" vertical={false} />
          {blocos.map((b) => (
            <ReferenceArea key={b.x1} x1={b.x1} x2={b.x2} fill="rgb(var(--accent))" fillOpacity={0.06} />
          ))}
          <XAxis
            dataKey="hora"
            tick={eixo}
            interval={11}
            tickFormatter={(v: string) => `${rotuloDia(v.slice(0, 10))} ${v.slice(11, 13)}h`}
          />
          <YAxis tick={eixo} domain={[min, max]} unit="°" />
          <ReferenceLine y={LIMIAR.atencaoT} stroke="rgb(var(--faixa-atencao))" strokeDasharray="4 4" />
          <ReferenceLine y={LIMIAR.alertaT} stroke="rgb(var(--faixa-alerta))" strokeDasharray="4 4" />
          <ReferenceLine y={LIMIAR.alertaIC} stroke="rgb(var(--faixa-alerta))" strokeDasharray="1 3" />
          <ReferenceLine y={LIMIAR.perigoIC} stroke="rgb(var(--faixa-perigo))" strokeDasharray="1 3" />
          <Tooltip
            contentStyle={{ background: "rgb(var(--surface))", border: "1px solid rgb(var(--line))", fontSize: 12 }}
            labelFormatter={(v: string) => `${rotuloDia(v.slice(0, 10))} ${v.slice(11)}`}
            formatter={(v: number, n: string) => [grau(v), n]}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Line dataKey="t_ext" name="Ar na rua" stroke="rgb(var(--muted))" dot={false} strokeWidth={1.5} isAnimationActive={false} />
          <Line dataKey="t_sala" name="Ar na sala (estimado)" stroke="rgb(var(--accent))" dot={false} strokeWidth={2} isAnimationActive={false} />
          <Line dataKey="ic_sala" name="IC na sala (estimado)" stroke="rgb(var(--faixa-alerta))" dot={false} strokeWidth={2} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export function LegendaLimiares() {
  return (
    <p className="mt-2 text-xs text-muted">
      Faixa sombreada = horário de aula (7h–17h, seg–sex). Tracejado: 27,8 °C (Atenção) e 31,1 °C (Alerta) no ar da
      sala; pontilhado: índice de calor 40 °C (Alerta) e 46 °C (Perigo).
    </p>
  );
}

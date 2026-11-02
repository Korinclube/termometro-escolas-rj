import type { Dia } from "../lib/api";
import { grau, rotuloDia } from "../lib/formato";
import { FaixaMarca } from "./ui";

export function TabelaDias({ dias }: { dias: Dia[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-line text-left text-xs text-muted">
            <th className="py-2 pr-3 font-medium">Dia</th>
            <th className="py-2 pr-3 font-medium">Pior faixa na sala (estimado)</th>
            <th className="py-2 pr-3 text-right font-medium">Ar na sala</th>
            <th className="py-2 pr-3 text-right font-medium">IC na sala</th>
            <th className="py-2 pr-3 text-right font-medium">IC na rua</th>
            <th className="py-2 pr-3 text-right font-medium">
              <abbr title="Nível de Calor estimado pelas regras do Decreto 54.740/2024; não é o nível oficial do COR">
                NC rua*
              </abbr>
            </th>
            <th className="py-2 font-medium">Horas de aula por faixa</th>
          </tr>
        </thead>
        <tbody>
          {dias.map((d) => (
            <tr key={d.data} className="border-b border-line last:border-0">
              <td className="num py-2 pr-3">{rotuloDia(d.data)}</td>
              <td className="py-2 pr-3">
                <FaixaMarca faixa={d.faixa_sala} />
                {d.ponto_cego && <span className="ml-2 text-xs text-muted">· ponto cego</span>}
              </td>
              <td className="num py-2 pr-3 text-right">{grau(d.t_sala_max_aula)}</td>
              <td className="num py-2 pr-3 text-right">{grau(d.ic_sala_max_aula)}</td>
              <td className="num py-2 pr-3 text-right">{grau(d.ic_ext_max)}</td>
              <td className="num py-2 pr-3 text-right">{d.nc_estimado_rua ?? "–"}</td>
              <td className="num py-2 text-xs text-muted">
                {d.dia_letivo
                  ? Object.entries(d.horas_aula_por_faixa)
                      .filter(([, n]) => n)
                      .map(([f, n]) => `${f} ${n}h`)
                      .join(" / ")
                  : "–"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-xs text-muted">
        Valores máximos no horário de aula. Ponto cego = sala em Alerta ou Perigo com a rua estimada em NC1 ou NC2,
        quando o protocolo da cidade não aciona medidas nas escolas.
      </p>
    </div>
  );
}

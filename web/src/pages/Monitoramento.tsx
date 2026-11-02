import type { Painel, Previsao } from "../lib/api";
import { dataHora, grau, rotuloDia } from "../lib/formato";
import { GraficoHoras, LegendaLimiares } from "../components/GraficoHoras";
import { TabelaDias } from "../components/TabelaDias";
import { BarraFaixas, Carregando, Erro, Metrica, Nota, Secao } from "../components/ui";

export function Monitoramento({
  painel,
  previsao,
}: {
  painel: { dados: Painel | null; erro: string | null; carregando: boolean };
  previsao: { dados: Previsao | null; erro: string | null; carregando: boolean };
}) {
  const p = painel.dados;
  const futuros = previsao.dados?.dias.filter((d) => d.previsao) ?? [];
  const horasFuturas = previsao.dados?.horas.filter((h) => futuros.some((d) => h.hora.startsWith(d.data))) ?? [];

  return (
    <div className="grid gap-4">
      <Secao
        titulo="Quadro da rede · próximas 72 horas"
        meta={
          p
            ? `${p.resumo.total} escolas públicas da capital · ${p.dias.map(rotuloDia).join(", ")} · ${p.premissa}`
            : "Escolas públicas da capital com dado georreferenciado"
        }
      >
        {painel.carregando && <Carregando texto="Calculando a previsão para a rede…" />}
        {painel.erro && <Erro mensagem={painel.erro} />}
        {p && (
          <>
            <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
              <Metrica
                rotulo="Escolas em Alerta ou Perigo (estimado)"
                valor={p.resumo.por_faixa.Alerta + p.resumo.por_faixa.Perigo}
                nota={`de ${p.resumo.total}`}
              />
              <Metrica
                rotulo="Em ponto cego"
                valor={p.resumo.ponto_cego}
                nota="sala em Alerta, rua em NC1/NC2"
              />
              <Metrica rotulo="NC estimado máximo*" valor={`NC ${p.resumo.nc_estimado_max}`} nota="não é o nível do COR" />
              <Metrica rotulo="IC máx. na sala (estimado)" valor={grau(p.resumo.ic_sala_max)} nota="horário de aula" />
              <Metrica rotulo="Máxima do ar na rua" valor={grau(p.resumo.t_ext_max)} nota="Open-Meteo" />
            </div>
            <div className="mt-5">
              <BarraFaixas rotulo="Escolas por pior faixa:" contagem={p.resumo.por_faixa} />
            </div>
            <p className="mt-3 text-xs text-muted">
              * Nível de Calor estimado com as regras do Decreto 54.740/2024 para cada célula; não é o nível oficial
              do COR, que vale para a cidade inteira.
            </p>
            <p className="mt-2 text-xs text-muted">
              A previsão tem resolução de ~11 km ({p.resumo.celulas} células para a cidade): escolas vizinhas recebem o
              mesmo valor. O que as distingue é o prédio. Use o seletor de telhado e o mapa de exposição.
            </p>
          </>
        )}
      </Secao>

      <Secao
        titulo={previsao.dados ? `Hora a hora · ${previsao.dados.escola.nome}` : "Hora a hora"}
        meta={previsao.dados ? `Gerado em ${dataHora(previsao.dados.gerado_em)}` : undefined}
      >
        {previsao.carregando && <Carregando />}
        {previsao.erro && <Erro mensagem={previsao.erro} />}
        {previsao.dados && (
          <>
            {previsao.dados.aviso_emitido && (
              <div className="mb-3">
                <Nota tom="alerta">
                  <strong>Aviso às escolas:</strong> {previsao.dados.motivo_aviso}
                </Nota>
              </div>
            )}
            <GraficoHoras horas={horasFuturas} />
            <LegendaLimiares />
            <div className="mt-5">
              <TabelaDias dias={futuros} />
            </div>
            <details className="mt-4 text-xs text-muted">
              <summary className="cursor-pointer font-semibold">Premissas desta estimativa</summary>
              <ul className="mt-2 list-disc space-y-1 pl-5">
                {previsao.dados.premissas.map((x) => (
                  <li key={x}>{x}</li>
                ))}
              </ul>
            </details>
          </>
        )}
      </Secao>
    </div>
  );
}

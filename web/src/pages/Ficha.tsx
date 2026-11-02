import type { Cenario, SalaParams, Selecao } from "../lib/api";
import { consulta, useApi } from "../lib/api";
import type { Faixa } from "../lib/fisica";
import { ROTULO_TELHADO, dataHora, grau, rotuloDia } from "../lib/formato";
import { TabelaDias } from "../components/TabelaDias";
import type { Dia, EscolaInfo } from "../lib/api";
import { BarraFaixas, Botao, Carregando, Erro, Metrica, Nota, Secao } from "../components/ui";

interface FichaDados {
  escola: { nome: string; lat: number; lon: number; tipo_telhado: string; climatizacao_funcionando: boolean; ajuste_sala_c: number };
  info: EscolaInfo | null;
  cenario: Cenario;
  cenario_rotulo: string;
  gerado_em: string;
  periodo: string[];
  dias_letivos: number;
  horas_aula_total: number;
  horas_aula_por_faixa: Record<Faixa, number>;
  dias_ponto_cego: string[];
  dias: Dia[];
  ibutg: {
    estimado_max_sala: number | null;
    limites_nr15: { taxa_metabolica_w: number; atividade: string; ibutg_max: number; horas_acima: number }[];
    metodo: string;
    limite_legal: string;
    cozinha: string;
  };
  premissas: string[];
  fontes: string[];
  aviso_nao_oficial: string;
  natureza: string;
}

export function Ficha({ sel, sala, cenario }: { sel: Selecao; sala: SalaParams; cenario: Cenario }) {
  const { dados: f, erro, carregando } = useApi<FichaDados>(`/api/ficha?${consulta(sel, sala, cenario)}`);
  if (!f && !carregando && !erro) return null;
  if (carregando || erro || !f)
    return (
      <Secao titulo="Ficha de evidência">
        {carregando && <Carregando />}
        {erro && <Erro mensagem={erro} />}
      </Secao>
    );
  const graves = f.horas_aula_por_faixa.Alerta + f.horas_aula_por_faixa.Perigo;

  return (
    <article className="grid gap-4">
      <div className="no-print flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted">{f.natureza}</p>
        <Botao onClick={() => window.print()}>Imprimir ou salvar PDF</Botao>
      </div>

      <Secao
        titulo={`Ficha de evidência · ${f.escola.nome}`}
        meta={`${f.info ? `${f.info.rede} · ${f.info.bairro} · INEP ${f.info.id} · ` : ""}${f.periodo.map(rotuloDia).join(" a ")} · gerada em ${dataHora(f.gerado_em)} · ${f.cenario_rotulo}`}
      >
        {f.cenario !== "ao_vivo" && (
          <div className="mb-3">
            <Nota tom="atencao">Simulação, não previsão: {f.cenario_rotulo}.</Nota>
          </div>
        )}
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <Metrica rotulo="Horas de aula em Alerta ou Perigo (estimado)" valor={`${graves}h`} nota={`de ${f.horas_aula_total}h em ${f.dias_letivos} dias letivos`} />
          <Metrica rotulo="Dias em ponto cego" valor={f.dias_ponto_cego.length} nota="sala em Alerta, rua em NC1/NC2" />
          <Metrica rotulo="IBUTG estimado máx. na sala" valor={grau(f.ibutg.estimado_max_sala)} nota="estimativa sem globo" />
          <Metrica rotulo="Telhado da sala" valor={<span className="font-sans text-base">{ROTULO_TELHADO[f.escola.tipo_telhado]}</span>} nota={f.escola.climatizacao_funcionando ? "ar-condicionado funcionando" : "sem ar-condicionado"} />
        </div>
        <div className="mt-4">
          <BarraFaixas rotulo="Horas de aula por faixa:" contagem={f.horas_aula_por_faixa} unidade="h" />
        </div>
      </Secao>

      <Secao titulo="Dia a dia">
        <TabelaDias dias={f.dias} />
      </Secao>

      <Secao titulo="Limites ocupacionais (NR-15) · estimativa, não laudo" meta="Vale para trabalhadores da escola, não para alunos.">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line text-left text-xs text-muted">
              <th className="py-2 pr-3 font-medium">Atividade (ilustrativa)</th>
              <th className="py-2 pr-3 text-right font-medium">IBUTG máx. (Quadro 1)</th>
              <th className="py-2 text-right font-medium">Horas de aula acima</th>
            </tr>
          </thead>
          <tbody>
            {f.ibutg.limites_nr15.map((l) => (
              <tr key={l.taxa_metabolica_w} className="border-b border-line last:border-0">
                <td className="py-2 pr-3">{l.atividade}</td>
                <td className="num py-2 pr-3 text-right">{grau(l.ibutg_max)}</td>
                <td className="num py-2 text-right">{l.horas_acima}h</td>
              </tr>
            ))}
          </tbody>
        </table>
        <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-muted">
          <li>{f.ibutg.metodo}</li>
          <li>{f.ibutg.limite_legal}</li>
          <li>{f.ibutg.cozinha}</li>
        </ul>
      </Secao>

      <Secao titulo="Premissas e fontes">
        <div className="grid gap-4 md:grid-cols-2">
          <ul className="list-disc space-y-1 pl-5 text-sm">{f.premissas.map((p) => <li key={p}>{p}</li>)}</ul>
          <ul className="list-disc space-y-1 pl-5 text-sm">{f.fontes.map((p) => <li key={p}>{p}</li>)}</ul>
        </div>
        <p className="mt-4 border-t border-line pt-3 text-sm font-semibold">{f.aviso_nao_oficial}</p>
      </Secao>
    </article>
  );
}

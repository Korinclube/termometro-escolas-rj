import { useState } from "react";
import type { Cenario, SalaParams, Selecao } from "../lib/api";
import { consulta, pedir, useApi } from "../lib/api";
import { Botao, Carregando, Erro, FaixaMarca, Secao, Subtitulo } from "../components/ui";
import { FAIXAS, type Faixa } from "../lib/fisica";

interface Contexto {
  modelo: string;
  instrucao_sistema: string;
  schema: unknown;
  prompt: string | null;
  script_python: string;
}

interface Parecer {
  escola: string;
  pior_faixa_prevista: string;
  aviso_emitido: boolean;
  modelo: string;
  aviso_nao_oficial: string;
  parecer: {
    resumo: string;
    riscos_principais: string[];
    acoes_recomendadas: { publico: string; acao: string; quando: string; faixa_gatilho: string }[];
    mensagem_familias: string;
    limitacoes: string[];
  };
}

function Bloco({ titulo, texto }: { titulo: string; texto: string }) {
  const [copiado, setCopiado] = useState(false);
  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <Subtitulo>{titulo}</Subtitulo>
        <button
          type="button"
          className="text-xs text-muted hover:text-ink"
          onClick={() => navigator.clipboard.writeText(texto).then(() => setCopiado(true))}
        >
          {copiado ? "Copiado" : "Copiar"}
        </button>
      </div>
      <pre className="max-h-72 overflow-auto border border-line bg-raised p-3 font-mono text-xs leading-relaxed whitespace-pre-wrap">{texto}</pre>
    </div>
  );
}

export function Gemini({ sel, sala, cenario }: { sel: Selecao; sala: SalaParams; cenario: Cenario }) {
  const id = sel.tipo === "escola" ? sel.id : "";
  const ctx = useApi<Contexto>(`/api/gemini/contexto?escola_id=${id}&cenario=${cenario}`);
  const [parecer, setParecer] = useState<Parecer | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [gerando, setGerando] = useState(false);

  async function gerar() {
    setGerando(true);
    setErro(null);
    try {
      setParecer(await pedir<Parecer>(`/api/parecer?${consulta(sel, sala, cenario)}`, { method: "POST" }));
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setGerando(false);
    }
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <Secao
        titulo="Parecer técnico"
        meta="O Gemini só redige. Faixas, níveis e números vêm do cálculo do painel, e o aviso de não oficial é anexado pelo código."
        acoes={<Botao primario onClick={gerar} disabled={gerando}>{gerando ? "Gerando…" : "Gerar parecer"}</Botao>}
      >
        {erro && <Erro mensagem={erro.includes("GEMINI_API_KEY") ? "O servidor não tem GEMINI_API_KEY configurada. Defina a variável e reinicie a API." : erro} />}
        {gerando && <Carregando texto="Gerando parecer com o Gemini…" />}
        {!gerando && !parecer && !erro && <p className="text-sm text-muted">Gera um parecer para {sel.nome} com as premissas de prédio e o cenário atuais.</p>}
        {!gerando && parecer && (
          <div className="grid gap-4 text-sm">
            <p>{parecer.parecer.resumo}</p>
            <div>
              <div className="mb-1"><Subtitulo>Riscos principais</Subtitulo></div>
              <ul className="list-disc space-y-1 pl-5">{parecer.parecer.riscos_principais.map((r) => <li key={r}>{r}</li>)}</ul>
            </div>
            <div>
              <div className="mb-1"><Subtitulo>Ações recomendadas</Subtitulo></div>
              <ul className="divide-y divide-line border-y border-line">
                {parecer.parecer.acoes_recomendadas.map((a, i) => (
                  <li key={i} className="py-2">
                    <div>{a.acao}</div>
                    <div className="flex flex-wrap gap-x-2 text-xs text-muted">
                      <span>{a.publico.replace(/_/g, " ")} · {a.quando} ·</span>
                      {FAIXAS.includes(a.faixa_gatilho as Faixa) ? (
                        <FaixaMarca faixa={a.faixa_gatilho as Faixa} />
                      ) : (
                        <span>faixa {a.faixa_gatilho}</span>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
            <Bloco titulo="Mensagem para famílias" texto={parecer.parecer.mensagem_familias} />
            <div>
              <div className="mb-1"><Subtitulo>Limitações</Subtitulo></div>
              <ul className="list-disc space-y-1 pl-5 text-muted">{parecer.parecer.limitacoes.map((r) => <li key={r}>{r}</li>)}</ul>
            </div>
            <p className="text-xs text-muted">{parecer.modelo} · {parecer.aviso_nao_oficial}</p>
          </div>
        )}
      </Secao>

      <Secao titulo="Por dentro da chamada" meta={ctx.dados ? `Modelo: ${ctx.dados.modelo} (variável GEMINI_MODEL)` : undefined}>
        {ctx.carregando && <Carregando />}
        {ctx.erro && <Erro mensagem={ctx.erro} />}
        {ctx.dados && (
          <div className="grid gap-4">
            <Bloco titulo="Instrução de sistema" texto={ctx.dados.instrucao_sistema} />
            <Bloco titulo="Schema JSON da resposta (schema.json)" texto={JSON.stringify(ctx.dados.schema, null, 2)} />
            {ctx.dados.prompt ? (
              <Bloco titulo="Prompt enviado (dados desta escola)" texto={ctx.dados.prompt} />
            ) : (
              <p className="text-xs text-muted">Selecione uma escola da base para ver o prompt com os dados dela.</p>
            )}
            <Bloco titulo="Script Python (SDK google-genai) para rodar fora do painel" texto={ctx.dados.script_python} />
          </div>
        )}
      </Secao>
    </div>
  );
}

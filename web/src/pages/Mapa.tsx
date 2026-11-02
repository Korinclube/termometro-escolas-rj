import { useEffect, useMemo, useState } from "react";
import { CircleMarker, MapContainer, TileLayer, Tooltip } from "react-leaflet";
import type { EscolaInfo, Painel, PainelEscola, Selecao } from "../lib/api";
import { grau, grauSinal } from "../lib/formato";
import { FAIXAS } from "../lib/fisica";
import { REGIOES_FOCO } from "../lib/pontos";
import { Botao, Carregando, Erro, FaixaMarca, Secao, Subtitulo, TOKEN_FAIXA, VAR_FAIXA, campo } from "../components/ui";

type Modo = "faixa" | "exposicao";
type Ponto = Extract<Selecao, { tipo: "ponto" }>;

const EXPOSICAO = [
  { ate: 0, var: "exp-1", rotulo: "abaixo da média" },
  { ate: 2, var: "exp-2", rotulo: "0 a 2 °C" },
  { ate: 3.57, var: "exp-3", rotulo: "2 a 3,6 °C" },
  { ate: Infinity, var: "exp-4", rotulo: "3,6 °C ou mais (grupo quente)" },
];

/** O canvas do Leaflet não resolve var(): lê os valores do tema já calculados. */
function corTema(nome: string): string {
  const v = getComputedStyle(document.documentElement).getPropertyValue(`--${nome}`).trim();
  return v ? `rgb(${v.split(/\s+/).join(",")})` : "#888";
}

function useEscuro() {
  const q = typeof window !== "undefined" ? window.matchMedia("(prefers-color-scheme: dark)") : null;
  const [escuro, setEscuro] = useState(q?.matches ?? false);
  useEffect(() => {
    if (!q) return;
    const f = (e: MediaQueryListEvent) => setEscuro(e.matches);
    q.addEventListener("change", f);
    return () => q.removeEventListener("change", f);
  }, [q]);
  return escuro;
}

export function Mapa({
  escolas,
  painel,
  pontos,
  pontosUsuario,
  sel,
  onSel,
  onAbrir,
  onAdicionarPonto,
  onRemoverPonto,
}: {
  escolas: EscolaInfo[];
  painel: { dados: Painel | null; erro: string | null; carregando: boolean };
  pontos: Ponto[];
  pontosUsuario: Ponto[];
  sel: Selecao;
  onSel: (s: Selecao) => void;
  onAbrir: () => void;
  onAdicionarPonto: (p: Ponto) => void;
  onRemoverPonto: (p: Ponto) => void;
}) {
  const [modo, setModo] = useState<Modo>("faixa");
  const [foco, setFoco] = useState(true);
  const escuro = useEscuro();
  const cores = useMemo(() => {
    const m: Record<string, string> = {};
    [...Object.values(TOKEN_FAIXA), ...EXPOSICAO.map((x) => x.var), "muted", "ink"].forEach((n) => (m[n] = corTema(n)));
    return m;
  }, [escuro]);
  const corExposicao = (d: number | null) =>
    d === null ? cores.muted : cores[EXPOSICAO.find((x) => d < x.ate)!.var];
  const porId = useMemo(() => {
    const m = new Map<string, PainelEscola>();
    painel.dados?.escolas.forEach((e) => m.set(e.id, e));
    return m;
  }, [painel.dados]);
  const visiveis = useMemo(
    () => (foco ? escolas.filter((e) => e.regiao && REGIOES_FOCO.includes(e.regiao)) : escolas),
    [escolas, foco],
  );
  const info = sel.tipo === "escola" ? escolas.find((e) => e.id === sel.id) : undefined;
  const prev = sel.tipo === "escola" ? porId.get(sel.id) : undefined;
  const [novo, setNovo] = useState({ nome: "", lat: "", lon: "" });
  const latN = Number(novo.lat.replace(",", "."));
  const lonN = Number(novo.lon.replace(",", "."));
  const novoValido =
    novo.nome.trim().length > 2 && latN >= -23.2 && latN <= -22.4 && lonN >= -44.1 && lonN <= -42.9;

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
      <Secao
        titulo="Mapa de risco"
        meta={
          modo === "faixa"
            ? `Pior faixa prevista na sala (estimado) nas próximas 72 h · ${painel.dados?.premissa ?? ""}`
            : "Desvio da temperatura de superfície (satélite, 2023) em relação à média da cidade. Não é temperatura do ar nem da sala."
        }
        acoes={
          <>
            <label className="sr-only" htmlFor="modo-mapa">Camada</label>
            <select id="modo-mapa" className={campo} value={modo} onChange={(e) => setModo(e.target.value as Modo)}>
              <option value="faixa">Pior faixa prevista na sala</option>
              <option value="exposicao">Exposição: ilha de calor (satélite)</option>
            </select>
            <label className="sr-only" htmlFor="foco-mapa">Recorte</label>
            <select id="foco-mapa" className={campo} value={foco ? "foco" : "tudo"} onChange={(e) => setFoco(e.target.value === "foco")}>
              <option value="foco">Zona Norte</option>
              <option value="tudo">Cidade inteira</option>
            </select>
          </>
        }
      >
        {painel.erro && modo === "faixa" && <Erro mensagem={painel.erro} />}
        {painel.carregando && modo === "faixa" && <Carregando texto="Calculando faixas…" />}
        <div className="h-[520px] overflow-hidden border border-line">
          <MapContainer center={[-22.83, -43.36]} zoom={11} preferCanvas className="h-full w-full">
            <TileLayer
              className="mosaico-base"
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            {visiveis.map((e) => {
              const pe = porId.get(e.id);
              const cor = modo === "faixa" ? (pe ? cores[TOKEN_FAIXA[pe.faixa]] : cores.muted) : corExposicao(e.desvio_superficie_c);
              const ativo = sel.tipo === "escola" && sel.id === e.id;
              return (
                <CircleMarker
                  key={e.id}
                  center={[e.lat, e.lon]}
                  radius={ativo ? 9 : 5}
                  pathOptions={{ color: ativo ? cores.ink : cor, weight: ativo ? 3 : 1, fillColor: cor, fillOpacity: 0.85 }}
                  eventHandlers={{ click: () => onSel({ tipo: "escola", id: e.id, nome: e.nome }) }}
                >
                  <Tooltip>{e.nome}</Tooltip>
                </CircleMarker>
              );
            })}
            {[...pontos, ...pontosUsuario].map((p) => (
              <CircleMarker
                key={p.nome}
                center={[p.lat, p.lon]}
                radius={7}
                pathOptions={{ color: cores.ink, weight: 2, dashArray: "3 3", fillOpacity: 0 }}
                eventHandlers={{ click: () => onSel(p) }}
              >
                <Tooltip>{p.nome}</Tooltip>
              </CircleMarker>
            ))}
          </MapContainer>
        </div>
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
          {modo === "faixa"
            ? FAIXAS.map((f) => (
                <span key={f} className="inline-flex items-center gap-1.5">
                  <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: VAR_FAIXA[f] }} /> {f}
                </span>
              ))
            : EXPOSICAO.map((x) => (
                <span key={x.rotulo} className="inline-flex items-center gap-1.5">
                  <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: `rgb(var(--${x.var}))` }} /> {x.rotulo}
                </span>
              ))}
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-full border-2 border-dashed border-ink" /> ponto de previsão (sem escola na base)
          </span>
        </div>
      </Secao>

      <div className="grid content-start gap-4">
        <Secao titulo="Selecionada">
          <Subtitulo>Escola em análise</Subtitulo>
          <div className="mt-1 font-semibold">{sel.nome}</div>
          {info ? (
            <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-2 text-sm">
              <dt className="text-muted">Rede</dt><dd>{info.rede}</dd>
              <dt className="text-muted">Bairro</dt><dd>{info.bairro}</dd>
              <dt className="text-muted">Alunos</dt><dd className="num">{info.alunos}</dd>
              <dt className="text-muted">Desvio de superfície</dt>
              <dd className="num">{grauSinal(info.desvio_superficie_c, 2)}</dd>
              <dt className="text-muted">Verde em 500 m</dt><dd className="num">{info.verde_500m_pct === null ? "–" : `${String(info.verde_500m_pct).replace(".", ",")}%`}</dd>
              <dt className="text-muted">INSE</dt><dd>{info.inse ?? "–"}</dd>
              <dt className="text-muted">Favela a 500 m</dt><dd>{info.favela_500m ? "sim" : "não"}</dd>
              {prev && (
                <>
                  <dt className="text-muted">Pior faixa prevista na sala (estimado)</dt><dd><FaixaMarca faixa={prev.faixa} /></dd>
                  <dt className="text-muted">IC máx. na sala (estimado)</dt><dd className="num">{grau(prev.ic_sala_max)}</dd>
                </>
              )}
            </dl>
          ) : (
            sel.tipo === "ponto" && <p className="mt-2 text-sm text-muted">Ponto de previsão. Sem dados do prédio.</p>
          )}
          <div className="mt-4">
            <Botao primario onClick={onAbrir}>Ver previsão hora a hora</Botao>
          </div>
        </Secao>

        <Secao titulo="Baixada e outros pontos" meta="A base pública por escola cobre só a capital. Adicione escolas da Baixada pela coordenada.">
          <ul className="mb-3 space-y-1 text-sm">
            {[...pontos, ...pontosUsuario].map((p) => (
              <li key={p.nome} className="flex items-center justify-between gap-2">
                <button type="button" className="text-left underline-offset-2 hover:underline" onClick={() => onSel(p)}>
                  {p.nome}
                </button>
                {pontosUsuario.includes(p) && (
                  <button type="button" className="text-xs text-muted hover:text-ink" onClick={() => onRemoverPonto(p)}>
                    remover
                  </button>
                )}
              </li>
            ))}
          </ul>
          <form
            className="grid gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (!novoValido) return;
              onAdicionarPonto({ tipo: "ponto", nome: novo.nome.trim(), lat: latN, lon: lonN });
              setNovo({ nome: "", lat: "", lon: "" });
            }}
          >
            <label className="text-xs text-muted">
              Nome da escola
              <input className={`${campo} mt-1 w-full`} value={novo.nome} onChange={(e) => setNovo({ ...novo, nome: e.target.value })} />
            </label>
            <div className="grid grid-cols-2 gap-2">
              <label className="text-xs text-muted">
                Latitude
                <input className={`${campo} num mt-1 w-full`} placeholder="-22,7160" value={novo.lat} onChange={(e) => setNovo({ ...novo, lat: e.target.value })} />
              </label>
              <label className="text-xs text-muted">
                Longitude
                <input className={`${campo} num mt-1 w-full`} placeholder="-43,5550" value={novo.lon} onChange={(e) => setNovo({ ...novo, lon: e.target.value })} />
              </label>
            </div>
            <p className="text-xs text-muted">Precisa estar na Região Metropolitana do Rio. Fica salvo só neste navegador.</p>
            <div>
              <Botao type="submit" disabled={!novoValido}>Adicionar ponto</Botao>
            </div>
          </form>
        </Secao>
      </div>
    </div>
  );
}

import { useEffect, useMemo, useState } from "react";
import { BarraContexto } from "./components/BarraContexto";
import { BoletimDialog } from "./components/BoletimDialog";
import { TopBar, type Aba } from "./components/TopBar";
import type { Cenario, EscolaInfo, Meta, Painel, Previsao, SalaParams, Selecao } from "./lib/api";
import { consulta, useApi } from "./lib/api";
import { PONTOS_BAIXADA } from "./lib/pontos";
import { Ficha } from "./pages/Ficha";
import { Gemini } from "./pages/Gemini";
import { Mapa } from "./pages/Mapa";
import { Monitoramento } from "./pages/Monitoramento";
import { Simulador } from "./pages/Simulador";

type Ponto = Extract<Selecao, { tipo: "ponto" }>;
const CHAVE_PONTOS = "termometro.pontos";
// Escola de partida: EM Mato Grosso, Irajá (Zona Norte), da base pública.
const INICIAL: Selecao = { tipo: "escola", id: "33074577", nome: "0514009 EM MATO GROSSO" };

function lerPontos(): Ponto[] {
  try {
    return JSON.parse(localStorage.getItem(CHAVE_PONTOS) ?? "[]");
  } catch {
    return [];
  }
}

export default function App() {
  const [aba, setAba] = useState<Aba>("monitoramento");
  const [sel, setSel] = useState<Selecao>(INICIAL);
  const [cenario, setCenario] = useState<Cenario>("ao_vivo");
  const [sala, setSala] = useState<SalaParams>({ telhado: "desconhecido", climatizada: false, ajuste: 0 });
  const [boletim, setBoletim] = useState(false);
  const [pontosUsuario, setPontosUsuario] = useState<Ponto[]>(lerPontos);

  useEffect(() => {
    try {
      localStorage.setItem(CHAVE_PONTOS, JSON.stringify(pontosUsuario));
    } catch {
      /* armazenamento indisponível: os pontos valem só nesta sessão */
    }
  }, [pontosUsuario]);

  const meta = useApi<Meta>("/api/meta");
  const escolas = useApi<EscolaInfo[]>("/api/escolas");
  const painel = useApi<Painel>(`/api/painel?cenario=${cenario}&telhado=${sala.telhado}`);
  const previsao = useApi<Previsao>(`/api/previsao?${consulta(sel, sala, cenario)}`);
  const pontos = useMemo(() => [...PONTOS_BAIXADA, ...pontosUsuario], [pontosUsuario]);
  const listaEscolas = escolas.dados ?? [];

  return (
    <div className="flex min-h-screen flex-col">
      <TopBar aba={aba} onAba={setAba} onBoletim={() => setBoletim(true)} />
      <BarraContexto
        meta={meta.dados}
        escolas={listaEscolas}
        pontos={pontos}
        sel={sel}
        onSel={setSel}
        cenario={cenario}
        onCenario={setCenario}
        sala={sala}
        onSala={setSala}
      />
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-4">
        {aba === "monitoramento" && <Monitoramento painel={painel} previsao={previsao} />}
        {aba === "mapa" && (
          <Mapa
            escolas={listaEscolas}
            painel={painel}
            pontos={PONTOS_BAIXADA}
            pontosUsuario={pontosUsuario}
            sel={sel}
            onSel={setSel}
            onAbrir={() => setAba("monitoramento")}
            onAdicionarPonto={(p) => {
              setPontosUsuario((ps) => [...ps.filter((x) => x.nome !== p.nome), p]);
              setSel(p);
            }}
            onRemoverPonto={(p) => setPontosUsuario((ps) => ps.filter((x) => x.nome !== p.nome))}
          />
        )}
        {aba === "simulador" && <Simulador previsao={previsao} sala={sala} onAplicar={setSala} />}
        {aba === "ficha" && <Ficha sel={sel} sala={sala} cenario={cenario} />}
        {aba === "gemini" && <Gemini sel={sel} sala={sala} cenario={cenario} />}
      </main>
      <footer className="border-t border-line px-4 py-3 text-center text-xs text-muted">
        {meta.dados?.aviso_nao_oficial} Previsão: Open-Meteo (CC BY 4.0). Escolas: {meta.dados?.fonte_escolas}
      </footer>
      <BoletimDialog aberto={boletim} onFechar={() => setBoletim(false)} sel={sel} sala={sala} cenario={cenario} />
    </div>
  );
}

import { useEffect, useState } from "react";
import type { Faixa, Telhado } from "./fisica";

export type Cenario = "ao_vivo" | "fev2025" | "mais1" | "mais2" | "mais3";

export interface EscolaInfo {
  id: string;
  nome: string;
  rede: string;
  municipio: string;
  bairro: string | null;
  regiao: string | null;
  lat: number;
  lon: number;
  alunos: number;
  desvio_superficie_c: number | null;
  verde_500m_pct: number | null;
  inse: string | null;
  favela_500m: boolean;
}

export type Selecao =
  | { tipo: "escola"; id: string; nome: string }
  | { tipo: "ponto"; nome: string; lat: number; lon: number };

export interface SalaParams {
  telhado: Telhado;
  climatizada: boolean;
  ajuste: number;
}

export interface Meta {
  aviso_nao_oficial: string;
  cenarios: Record<Cenario, string>;
  telhados: Record<Telhado, number>;
  fonte_escolas: string;
  nota_escolas: string;
}

export interface Dia {
  data: string;
  dia_letivo: boolean;
  previsao: boolean;
  nc_estimado_rua: number | null;
  t_ext_max: number;
  ic_ext_max: number;
  t_sala_max_aula: number | null;
  ic_sala_max_aula: number | null;
  ibutg_sala_max_aula: number | null;
  faixa_sala: Faixa | "Sem aula";
  horas_aula_por_faixa: Partial<Record<Faixa, number>>;
  ponto_cego: boolean;
}

export interface Hora {
  hora: string;
  t_ext: number;
  rh_ext: number;
  ic_ext: number;
  t_sala: number;
  rh_sala: number;
  ic_sala: number;
  ibutg_sala: number;
  faixa: Faixa;
  aula: boolean;
}

export interface Previsao {
  escola: { nome: string; lat: number; lon: number; tipo_telhado: Telhado };
  info: EscolaInfo | null;
  gerado_em: string;
  dias: Dia[];
  horas: Hora[];
  aviso_emitido: boolean;
  motivo_aviso: string;
  premissas: string[];
  aviso_nao_oficial: string;
}

export interface PainelEscola {
  id: string;
  faixa: Faixa;
  nc_max: number;
  ic_sala_max: number;
  ponto_cego: boolean;
  dias: { data: string; faixa: Faixa | "Sem aula"; nc: number | null }[];
}

export interface Painel {
  cenario: Cenario;
  cenario_rotulo: string;
  dias: string[];
  telhado: Telhado;
  premissa: string;
  resumo: {
    total: number;
    por_faixa: Record<Faixa, number>;
    ponto_cego: number;
    nc_estimado_max: number;
    ic_sala_max: number;
    t_ext_max: number;
    celulas: number;
  };
  escolas: PainelEscola[];
}

export function consulta(sel: Selecao, sala: SalaParams, cenario: Cenario): string {
  const p = new URLSearchParams({
    telhado: sala.telhado,
    climatizada: String(sala.climatizada),
    ajuste: String(sala.ajuste),
    cenario,
  });
  if (sel.tipo === "escola") p.set("escola_id", sel.id);
  else {
    p.set("lat", String(sel.lat));
    p.set("lon", String(sel.lon));
    p.set("nome", sel.nome);
  }
  return p.toString();
}

async function lerErro(r: Response): Promise<string> {
  try {
    const j = await r.json();
    return typeof j.detail === "string" ? j.detail : `Erro ${r.status}`;
  } catch {
    return `Erro ${r.status}`;
  }
}

export async function pedir<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init);
  if (!r.ok) throw new Error(await lerErro(r));
  return r.json() as Promise<T>;
}

export function useApi<T>(url: string | null) {
  const [estado, setEstado] = useState<{ dados: T | null; erro: string | null; carregando: boolean }>({
    dados: null,
    erro: null,
    carregando: !!url,
  });
  useEffect(() => {
    if (!url) return;
    let vivo = true;
    setEstado((e) => ({ ...e, carregando: true, erro: null }));
    pedir<T>(url)
      .then((dados) => vivo && setEstado({ dados, erro: null, carregando: false }))
      .catch((e: Error) => vivo && setEstado({ dados: null, erro: e.message, carregando: false }));
    return () => {
      vivo = false;
    };
  }, [url]);
  return estado;
}

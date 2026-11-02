import type { Selecao } from "./api";

// A base pública de escolas por ponto (Alana/MapBiomas) cobre só capitais.
// Para a Baixada, o painel oferece o centro aproximado de cada município como
// ponto de previsão. Escolas reais entram como pontos personalizados.
export const PONTOS_BAIXADA: Extract<Selecao, { tipo: "ponto" }>[] = [
  { tipo: "ponto", nome: "Queimados (centro aproximado)", lat: -22.716, lon: -43.555 },
  { tipo: "ponto", nome: "Nova Iguaçu (centro aproximado)", lat: -22.759, lon: -43.451 },
  { tipo: "ponto", nome: "Belford Roxo (centro aproximado)", lat: -22.764, lon: -43.399 },
  { tipo: "ponto", nome: "Duque de Caxias (centro aproximado)", lat: -22.786, lon: -43.311 },
  { tipo: "ponto", nome: "São João de Meriti (centro aproximado)", lat: -22.804, lon: -43.372 },
  { tipo: "ponto", nome: "Mesquita (centro aproximado)", lat: -22.783, lon: -43.432 },
  { tipo: "ponto", nome: "Nilópolis (centro aproximado)", lat: -22.807, lon: -43.414 },
];

export const REGIOES_FOCO = ["Madureira", "Pavuna", "Penha", "Inhaúma", "Méier", "Ramos", "Ilha do Governador"];

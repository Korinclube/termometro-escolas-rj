const SEMANA = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];

export function rotuloDia(iso: string): string {
  const [a, m, d] = iso.split("-").map(Number);
  const dt = new Date(a, m - 1, d);
  return `${SEMANA[dt.getDay()]} ${String(d).padStart(2, "0")}/${String(m).padStart(2, "0")}`;
}

export const grau = (v: number | null | undefined, casas = 1) =>
  v === null || v === undefined ? "–" : `${v.toFixed(casas).replace(".", ",")} °C`;

export const grauSinal = (v: number | null | undefined, casas = 1) =>
  v === null || v === undefined ? "–" : `${v > 0 ? "+" : ""}${v.toFixed(casas).replace(".", ",")} °C`;

/** "2026-11-02T15:20-03:00" -> "02/11/2026 15:20" */
export function dataHora(iso: string): string {
  const [d, h] = iso.split("T");
  const [a, m, dia] = d.split("-");
  return `${dia}/${m}/${a} ${h?.slice(0, 5) ?? ""}`.trim();
}

export const ROTULO_TELHADO: Record<string, string> = {
  laje: "Laje de concreto",
  fibrocimento_sem_forro: "Fibrocimento sem forro",
  telha_metalica_sem_forro: "Telha metálica sem forro",
  desconhecido: "Desconhecido (pior caso)",
};

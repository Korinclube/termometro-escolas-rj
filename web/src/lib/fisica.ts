// Porte de src/pipeline.py (andar da sala) para o simulador responder sem rede.
// Mantido em sincronia por fisica.test.ts contra fisica.fixtures.json (gerado pelo Python).

export type Telhado = "laje" | "fibrocimento_sem_forro" | "telha_metalica_sem_forro" | "desconhecido";
export type Faixa = "Normal" | "Atenção" | "Alerta" | "Perigo";

export const DELTA_TELHADO_C: Record<Telhado, number> = {
  laje: -1.0,
  fibrocimento_sem_forro: 0.0,
  telha_metalica_sem_forro: 2.5,
  desconhecido: 2.5,
};
export const TEMP_SALA_CLIMATIZADA_C = 24.0;
export const LIMIAR = { atencaoT: 27.8, alertaT: 31.1, alertaIC: 40.0, perigoIC: 46.0 };
export const FAIXAS: Faixa[] = ["Normal", "Atenção", "Alerta", "Perigo"];

export function indiceCalorC(tC: number, rh: number): number {
  const tF = (tC * 9) / 5 + 32;
  const simples = 0.5 * (tF + 61.0 + (tF - 68.0) * 1.2 + rh * 0.094);
  let hiF = (simples + tF) / 2;
  if (hiF >= 80) {
    hiF =
      -42.379 + 2.04901523 * tF + 10.14333127 * rh - 0.22475541 * tF * rh - 0.00683783 * tF ** 2 -
      0.05481717 * rh ** 2 + 0.00122874 * tF ** 2 * rh + 0.00085282 * tF * rh ** 2 -
      0.00000199 * tF ** 2 * rh ** 2;
    if (rh < 13 && tF >= 80 && tF <= 112) {
      hiF -= ((13 - rh) / 4) * Math.sqrt((17 - Math.abs(tF - 95.0)) / 17);
    } else if (rh > 85 && tF >= 80 && tF <= 87) {
      hiF += ((rh - 85) / 10) * ((87 - tF) / 5);
    }
  }
  return ((hiF - 32) * 5) / 9;
}

const es = (t: number) => 6.112 * Math.exp((17.62 * t) / (243.12 + t));

export function umidadeRelativaInterna(tExt: number, rhExt: number, tIn: number): number {
  return Math.min(100, (100 * ((rhExt / 100) * es(tExt))) / es(tIn));
}

export function bulboUmidoC(t: number, rhIn: number): number {
  const rh = Math.min(Math.max(rhIn, 5), 99);
  return (
    t * Math.atan(0.151977 * Math.sqrt(rh + 8.313659)) + Math.atan(t + rh) - Math.atan(rh - 1.676331) +
    0.00391838 * rh ** 1.5 * Math.atan(0.023101 * rh) - 4.686035
  );
}

export const ibutgInternoEstimadoC = (t: number, rh: number) => 0.7 * bulboUmidoC(t, rh) + 0.3 * t;

export interface Sala {
  telhado: Telhado;
  climatizada: boolean;
  ajuste: number;
}

export function temperaturaSala(tExt: number, s: Sala): number {
  const t = tExt + DELTA_TELHADO_C[s.telhado] + s.ajuste;
  return s.climatizada ? Math.min(t, TEMP_SALA_CLIMATIZADA_C) : t;
}

export function classificarFaixa(tIn: number, icIn: number): Faixa {
  if (icIn >= LIMIAR.perigoIC) return "Perigo";
  if (tIn >= LIMIAR.alertaT || icIn >= LIMIAR.alertaIC) return "Alerta";
  if (tIn >= LIMIAR.atencaoT) return "Atenção";
  return "Normal";
}

export function calcularHora(tExt: number, rhExt: number, s: Sala) {
  const tSala = temperaturaSala(tExt, s);
  const rhSala = umidadeRelativaInterna(tExt, rhExt, tSala);
  const icSala = indiceCalorC(tSala, rhSala);
  return {
    icExt: indiceCalorC(tExt, rhExt),
    tSala,
    rhSala,
    icSala,
    ibutgSala: ibutgInternoEstimadoC(tSala, rhSala),
    faixa: classificarFaixa(tSala, icSala),
  };
}

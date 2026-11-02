import casos from "./fisica.fixtures.json";
import { calcularHora, type Telhado } from "./fisica";

describe("física do simulador = pipeline Python", () => {
  it.each(casos.map((c) => [c] as const))("%o", (c) => {
    const r = calcularHora(c.t_ext, c.rh_ext, {
      telhado: c.telhado as Telhado,
      climatizada: c.climatizada,
      ajuste: c.ajuste,
    });
    expect(r.icExt).toBeCloseTo(c.ic_ext, 4);
    expect(r.tSala).toBeCloseTo(c.t_sala, 4);
    expect(r.rhSala).toBeCloseTo(c.rh_sala, 4);
    expect(r.icSala).toBeCloseTo(c.ic_sala, 4);
    expect(r.ibutgSala).toBeCloseTo(c.ibutg_sala, 4);
    expect(r.faixa).toBe(c.faixa);
  });
});

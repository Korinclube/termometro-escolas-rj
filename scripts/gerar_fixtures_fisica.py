"""Gera web/src/lib/fisica.fixtures.json a partir do pipeline Python.

O simulador do painel recalcula a física no navegador (src/lib/fisica.ts). Os
testes dos dois lados comparam contra este arquivo, então uma regra alterada só
de um lado quebra o teste. Rode após mudar regras: python scripts/gerar_fixtures_fisica.py
"""

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from pipeline import (  # noqa: E402
    Escola, classificar_faixa, estimar_temperatura_sala, ibutg_interno_estimado_c,
    indice_calor_c, umidade_relativa_interna,
)

SAIDA = RAIZ / "web" / "src" / "lib" / "fisica.fixtures.json"


def casos() -> list[dict]:
    out = []
    for t in (18.0, 24.5, 27.0, 29.0, 31.0, 33.0, 35.0, 38.0, 41.0):
        for rh in (8, 30, 55, 70, 88):
            for telhado in ("laje", "fibrocimento_sem_forro", "telha_metalica_sem_forro", "desconhecido"):
                for clim, ajuste in ((False, 0.0), (True, 0.0), (False, 1.5)):
                    e = Escola("f", 0, 0, telhado, clim, ajuste_sala_c=ajuste)
                    t_in = estimar_temperatura_sala(t, e)
                    rh_in = umidade_relativa_interna(t, rh, t_in)
                    ic_in = indice_calor_c(t_in, rh_in)
                    out.append({
                        "t_ext": t, "rh_ext": rh, "telhado": telhado, "climatizada": clim, "ajuste": ajuste,
                        "ic_ext": round(indice_calor_c(t, rh), 6), "t_sala": round(t_in, 6),
                        "rh_sala": round(rh_in, 6), "ic_sala": round(ic_in, 6),
                        "ibutg_sala": round(ibutg_interno_estimado_c(t_in, rh_in), 6),
                        "faixa": classificar_faixa(t_in, ic_in).rotulo,
                    })
    return out


if __name__ == "__main__":
    SAIDA.write_text(json.dumps(casos(), ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{SAIDA} gravado")

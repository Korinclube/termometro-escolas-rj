"""Monta data/escolas.json a partir de fontes públicas (rodar só quando atualizar).

Entradas (baixe antes; não vão para o repositório):
  alana.csv     planilha "Verde nas escolas" (Instituto Alana + MapBiomas), export CSV:
                https://docs.google.com/spreadsheets/d/1lkahECBj2v08iXE5gBgBORL8yAqmvluLxULjK0Mdxc0/export?format=csv
  bairros.geojson  Limite de Bairros (IPP/Data.Rio):
                https://pgeo3.rio.rj.gov.br/arcgis/rest/services/Cartografia/Limites_administrativos/MapServer/4/query?where=1%3D1&outFields=*&outSR=4326&f=geojson

Uso: python scripts/preparar_escolas.py alana.csv bairros.geojson
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import date
from pathlib import Path

RIO = "3304557"
REDES_PUBLICAS = {"Municipal", "Estadual", "Federal"}
SAIDA = Path(__file__).resolve().parent.parent / "data" / "escolas.json"


def _num(v: str) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _dentro(x: float, y: float, anel: list[list[float]]) -> bool:
    dentro = False
    j = len(anel) - 1
    for i in range(len(anel)):
        xi, yi = anel[i][0], anel[i][1]
        xj, yj = anel[j][0], anel[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            dentro = not dentro
        j = i
    return dentro


def _poligonos(geom: dict) -> list[list[list[list[float]]]]:
    return [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]


def bairro_de(lon: float, lat: float, bairros: list[dict]) -> dict | None:
    for f in bairros:
        for poli in _poligonos(f["geometry"]):
            if _dentro(lon, lat, poli[0]) and not any(_dentro(lon, lat, b) for b in poli[1:]):
                return f["properties"]
    return None


def main(csv_path: str, bairros_path: str) -> None:
    bairros = json.loads(Path(bairros_path).read_text(encoding="utf-8"))["features"]
    escolas = []
    with open(csv_path, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["cod_munic"] != RIO or r["Depend"] not in REDES_PUBLICAS:
                continue
            lat, lon = _num(r["lat"]), _num(r["long"])
            if lat is None or lon is None:
                continue
            b = bairro_de(lon, lat, bairros) or {}
            veg, nveg = _num(r["m2_Veg_500m"]), _num(r["m2_NVeg_500m"])
            escolas.append(
                {
                    "id": r["cod_esc"],
                    "nome": r["Escola"].strip(),
                    "rede": r["Depend"],
                    "municipio": "Rio de Janeiro",
                    "bairro": (b.get("nome") or "").strip() or None,
                    "regiao": (b.get("rp") or "").strip() or None,
                    "lat": round(lat, 6),
                    "lon": round(lon, 6),
                    "alunos": int(_num(r["total alun"]) or 0),
                    "desvio_superficie_c": _num(r["desvio_media"]),
                    "verde_500m_pct": round(100 * veg / (veg + nveg), 1) if veg is not None and nveg else None,
                    "inse": r["INSE_2023"] or None,
                    "favela_500m": r["favela_500"] == "verdadeiro",
                }
            )
    escolas.sort(key=lambda e: (e["bairro"] or "", e["nome"]))
    SAIDA.write_text(
        json.dumps(
            {
                "fonte": "Instituto Alana e MapBiomas, 'Verde nas escolas' (Censo Escolar + Landsat 2023); "
                "bairros: IPP/Data.Rio.",
                "gerado_em": date.today().isoformat(),
                "nota": "Desvio de superfície = temperatura de superfície (satélite) no ponto da escola menos a "
                "média da cidade. Não é a temperatura do ar nem da sala.",
                "escolas": escolas,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    sem_bairro = sum(1 for e in escolas if not e["bairro"])
    print(f"{len(escolas)} escolas gravadas em {SAIDA} ({sem_bairro} sem bairro)")


if __name__ == "__main__":
    main(*sys.argv[1:3])

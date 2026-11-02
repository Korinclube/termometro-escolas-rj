"""API do painel Termômetro das Escolas (FastAPI).

Rodar:  uvicorn api:app --app-dir src --reload
O frontend compilado (web/dist) é servido na raiz quando existe.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any, Callable, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import pipeline as pl
from pipeline import (
    AVISO_NAO_OFICIAL,
    DELTA_TELHADO_C,
    NR15_IBUTG_MAX_C,
    Escola,
    Faixa,
    ResultadoEscola,
    avaliar_escola,
)

RAIZ = Path(__file__).resolve().parent.parent
DADOS_ESCOLAS = RAIZ / "data" / "escolas.json"
DIST = RAIZ / "web" / "dist"

Cenario = Literal["ao_vivo", "fev2025", "mais1", "mais2", "mais3"]
CENARIOS: dict[str, dict[str, Any]] = {
    "ao_vivo": {"rotulo": "Previsão ao vivo (Open-Meteo)", "delta": 0.0},
    "fev2025": {
        "rotulo": "Reprise: onda de calor de 17 a 19/02/2025 (reanálise)",
        "delta": 0.0,
        "inicio": date(2025, 2, 15),
        "hoje": date(2025, 2, 17),
        "fim": date(2025, 2, 19),
    },
    "mais1": {"rotulo": "Sensibilidade: previsão +1 °C", "delta": 1.0},
    "mais2": {"rotulo": "Sensibilidade: previsão +2 °C", "delta": 2.0},
    "mais3": {"rotulo": "Sensibilidade: previsão +3 °C", "delta": 3.0},
}
TTL_S = 30 * 60
GRADE = 0.1  # graus (~11 km); agrupa escolas na mesma célula de previsão, perto da resolução do modelo

ROTULO_TELHADO = {
    "laje": "laje de concreto",
    "fibrocimento_sem_forro": "fibrocimento sem forro",
    "telha_metalica_sem_forro": "telha metálica sem forro",
    "desconhecido": "desconhecido, pior caso",
}

ATIVIDADES_NR15 = {
    251: "≈ 250 W: em pé, andando devagar (ex.: professor em sala) - ilustrativo",
    300: "300 W: atividade moderada contínua (ex.: merendeira no preparo) - ilustrativo",
}

app = FastAPI(title="Termômetro das Escolas RJ", version="0.2.0")


# ---------------------------------------------------------------------------
# Dados de escolas e cache de previsão
# ---------------------------------------------------------------------------
def _carregar_escolas() -> dict[str, Any]:
    return json.loads(DADOS_ESCOLAS.read_text(encoding="utf-8"))


_BASE = _carregar_escolas()
ESCOLAS: dict[str, dict[str, Any]] = {e["id"]: e for e in _BASE["escolas"]}

_cache: dict[tuple, tuple[float, Any]] = {}
_trava = threading.Lock()


def _em_cache(chave: tuple, fn: Callable[[], Any]) -> Any:
    agora = time.time()
    with _trava:
        if chave in _cache and agora - _cache[chave][0] < TTL_S:
            return _cache[chave][1]
    valor = fn()
    with _trava:
        _cache[chave] = (agora, valor)
    return valor


def _celula(lat: float, lon: float) -> tuple[float, float]:
    return (round(round(lat / GRADE) * GRADE, 2), round(round(lon / GRADE) * GRADE, 2))


def _baixar(cenario: str, lats: list[float], lons: list[float]) -> list[dict[str, Any]]:
    c = CENARIOS[cenario]
    if "inicio" in c:
        resp = pl.buscar_reanalise(lats, lons, c["inicio"], c["fim"])
    else:
        resp = pl.buscar_previsao(lats, lons)
    return resp if isinstance(resp, list) else [resp]


CACHE_DISCO = RAIZ / ".cache" / "meteo"


def _arquivo_cache(cenario: str, cel: tuple[float, float]) -> Path:
    return CACHE_DISCO / f"{cenario}_{cel[0]:.2f}_{cel[1]:.2f}.json"


def _validade(cenario: str) -> float:
    # Reanálise não muda; previsão vale TTL_S. Cenários de sensibilidade reusam "ao_vivo".
    return float("inf") if "inicio" in CENARIOS[cenario] else TTL_S


def _fonte(cenario: str) -> str:
    return "fev2025" if "inicio" in CENARIOS[cenario] else "ao_vivo"


def _dados_celulas(cenario: str, celulas: list[tuple[float, float]]) -> dict[tuple[float, float], dict]:
    """Uma chamada Open-Meteo por lote de células, com cache em memória e em disco.

    O cache em disco evita estourar a cota gratuita (Open-Meteo conta cada ponto)
    quando o servidor reinicia.
    """
    fonte, validade, agora = _fonte(cenario), _validade(cenario), time.time()
    faltando = []
    for c in celulas:
        if (fonte, c) in _cache and agora - _cache[(fonte, c)][0] < validade:
            continue
        arq = _arquivo_cache(fonte, c)
        if arq.exists() and agora - arq.stat().st_mtime < validade:
            with _trava:
                _cache[(fonte, c)] = (arq.stat().st_mtime, json.loads(arq.read_text(encoding="utf-8")))
            continue
        faltando.append(c)
    CACHE_DISCO.mkdir(parents=True, exist_ok=True)
    for i in range(0, len(faltando), 100):
        lote = faltando[i : i + 100]
        respostas = _baixar(fonte, [c[0] for c in lote], [c[1] for c in lote])
        with _trava:
            for cel, resp in zip(lote, respostas):
                _cache[(fonte, cel)] = (time.time(), resp)
                _arquivo_cache(fonte, cel).write_text(json.dumps(resp), encoding="utf-8")
    return {c: _cache[(fonte, c)][1] for c in celulas}


def _hoje(cenario: str) -> date | None:
    return CENARIOS[cenario].get("hoje")


def _avaliar(escola: Escola, cenario: str, incluir_horas: bool = False) -> ResultadoEscola:
    cel = _celula(escola.lat, escola.lon)
    try:
        dados = _dados_celulas(cenario, [cel])[cel]
    except Exception as exc:  # rede, cota, resposta inválida
        raise HTTPException(502, f"Falha ao buscar dados meteorológicos: {exc}") from exc
    return avaliar_escola(
        escola,
        dados,
        hoje=_hoje(cenario),
        delta_cenario_c=CENARIOS[cenario]["delta"],
        incluir_horas=incluir_horas,
    )


def _escola(
    escola_id: str | None,
    lat: float | None,
    lon: float | None,
    nome: str | None,
    telhado: str,
    climatizada: bool,
    ajuste: float,
) -> tuple[Escola, dict[str, Any] | None]:
    if telhado not in DELTA_TELHADO_C:
        raise HTTPException(422, f"telhado deve ser um de {list(DELTA_TELHADO_C)}")
    if not -5 <= ajuste <= 5:
        raise HTTPException(422, "ajuste deve ficar entre -5 e +5 °C")
    if escola_id:
        info = ESCOLAS.get(escola_id)
        if not info:
            raise HTTPException(404, "Escola não encontrada")
        return Escola(info["nome"], info["lat"], info["lon"], telhado, climatizada, ajuste_sala_c=ajuste), info
    if lat is None or lon is None:
        raise HTTPException(422, "Informe escola_id ou lat e lon")
    if not (-23.2 <= lat <= -22.4 and -44.1 <= lon <= -42.9):
        raise HTTPException(422, "Coordenadas fora da Região Metropolitana do Rio")
    return Escola(nome or "Ponto personalizado", lat, lon, telhado, climatizada, ajuste_sala_c=ajuste), None


def _pior(dias: list[pl.ResumoDia]) -> Faixa:
    faixas = [Faixa[_CHAVE[d.faixa_sala]] for d in dias if d.previsao and d.faixa_sala in _CHAVE]
    return max(faixas, default=Faixa.NORMAL)


_CHAVE = {"Normal": "NORMAL", "Atenção": "ATENCAO", "Alerta": "ALERTA", "Perigo": "PERIGO"}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/meta")
def meta() -> dict[str, Any]:
    return {
        "aviso_nao_oficial": AVISO_NAO_OFICIAL,
        "cenarios": {k: v["rotulo"] for k, v in CENARIOS.items()},
        "telhados": DELTA_TELHADO_C,
        "limiares": {
            "atencao_t": pl.LIMIAR_ATENCAO_T_C,
            "alerta_t": pl.LIMIAR_ALERTA_T_C,
            "alerta_ic": pl.LIMIAR_ALERTA_IC_C,
            "perigo_ic": pl.LIMIAR_PERIGO_IC_C,
            "sala_climatizada": pl.TEMP_SALA_CLIMATIZADA_C,
        },
        "nr15": {str(k): {"ibutg_max": v, "atividade": ATIVIDADES_NR15[k]} for k, v in NR15_IBUTG_MAX_C.items()},
        "fonte_escolas": _BASE["fonte"],
        "nota_escolas": _BASE["nota"],
        "escolas_geradas_em": _BASE["gerado_em"],
    }


@app.get("/api/escolas")
def listar_escolas() -> list[dict[str, Any]]:
    return _BASE["escolas"]


@app.get("/api/painel")
def painel(cenario: Cenario = "ao_vivo", telhado: str = "desconhecido") -> dict[str, Any]:
    """Resumo de todas as escolas com uma premissa única de telhado (padrão: desconhecido = pior caso)."""
    if telhado not in DELTA_TELHADO_C:
        raise HTTPException(422, f"telhado deve ser um de {list(DELTA_TELHADO_C)}")

    def calcular() -> dict[str, Any]:
        por_celula: dict[tuple[float, float], list[dict[str, Any]]] = {}
        for e in _BASE["escolas"]:
            por_celula.setdefault(_celula(e["lat"], e["lon"]), []).append(e)
        try:
            dados = _dados_celulas(cenario, list(por_celula))
        except Exception as exc:
            raise HTTPException(502, f"Falha ao buscar dados meteorológicos: {exc}") from exc

        escolas_out, dias_ref = [], None
        contagem = {f.rotulo: 0 for f in Faixa}
        ponto_cego = 0
        nc_max, ic_sala_max, t_ext_max = 1, 0.0, 0.0
        for cel, membros in por_celula.items():
            r = avaliar_escola(
                Escola("célula", cel[0], cel[1], telhado),
                dados[cel],
                hoje=_hoje(cenario),
                delta_cenario_c=CENARIOS[cenario]["delta"],
            )
            futuros = [d for d in r.dias if d.previsao]
            dias_ref = dias_ref or [d.data for d in futuros]
            pior = _pior(r.dias)
            cego = any(d.ponto_cego for d in futuros)
            nc = max((d.nc_estimado_rua or 1) for d in futuros)
            ic = max((d.ic_sala_max_aula or 0) for d in futuros)
            nc_max, ic_sala_max = max(nc_max, nc), max(ic_sala_max, ic)
            t_ext_max = max(t_ext_max, max(d.t_ext_max for d in futuros))
            for e in membros:
                contagem[pior.rotulo] += 1
                ponto_cego += cego
                escolas_out.append(
                    {
                        "id": e["id"],
                        "faixa": pior.rotulo,
                        "nc_max": nc,
                        "ic_sala_max": ic,
                        "ponto_cego": cego,
                        "dias": [{"data": d.data, "faixa": d.faixa_sala, "nc": d.nc_estimado_rua} for d in futuros],
                    }
                )
        return {
            "cenario": cenario,
            "cenario_rotulo": CENARIOS[cenario]["rotulo"],
            "gerado_em": time.strftime("%Y-%m-%dT%H:%M"),
            "dias": dias_ref or [],
            "resumo": {
                "total": len(escolas_out),
                "por_faixa": contagem,
                "ponto_cego": ponto_cego,
                "nc_estimado_max": nc_max,
                "ic_sala_max": round(ic_sala_max, 1),
                "t_ext_max": round(t_ext_max, 1),
                "celulas": len(por_celula),
            },
            "telhado": telhado,
            "premissa": f"Todas as escolas com telhado '{telhado}' ({pl._br(DELTA_TELHADO_C[telhado])} °C) e sem climatização.",
            "aviso_nao_oficial": AVISO_NAO_OFICIAL,
            "escolas": escolas_out,
        }

    return _em_cache(("painel", cenario, telhado), calcular)


@app.get("/api/previsao")
def previsao(
    escola_id: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    nome: str | None = None,
    telhado: str = "desconhecido",
    climatizada: bool = False,
    ajuste: float = 0.0,
    cenario: Cenario = "ao_vivo",
) -> dict[str, Any]:
    escola, info = _escola(escola_id, lat, lon, nome, telhado, climatizada, ajuste)
    r = _avaliar(escola, cenario, incluir_horas=True)
    out = r.to_dict()
    out["info"] = info
    out["cenario"] = cenario
    return out


@app.get("/api/boletim")
def boletim(
    escola_id: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    nome: str | None = None,
    telhado: str = "desconhecido",
    climatizada: bool = False,
    ajuste: float = 0.0,
    cenario: Cenario = "ao_vivo",
) -> dict[str, str]:
    escola, _ = _escola(escola_id, lat, lon, nome, telhado, climatizada, ajuste)
    return {"texto": texto_boletim(_avaliar(escola, cenario), cenario)}


ACOES = {
    "Atenção": "apagar luzes, fechar persianas do lado do sol, ventilação cruzada e água a cada 30 min",
    "Alerta": "suspender educação física, levar turmas para salas mais frescas, avisar famílias, "
    "considerar turno reduzido",
    "Perigo": "tirar os alunos da sala, acionar atendimento de saúde, registrar e comunicar à rede",
}
_DIA_SEMANA = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


def texto_boletim(r: ResultadoEscola, cenario: str = "ao_vivo") -> str:
    """Texto pronto para WhatsApp (negrito com *asteriscos*)."""
    linhas = [f"*Termômetro das Escolas · {r.escola.nome}*"]
    if cenario != "ao_vivo":
        linhas.append(f"_SIMULAÇÃO: {CENARIOS[cenario]['rotulo']}. Não é previsão real._")
    linhas.append("Calor previsto *dentro da sala* nos próximos dias letivos:")
    for d in r.dias:
        if not d.previsao or not d.dia_letivo:
            continue
        dt = date.fromisoformat(d.data)
        valor = f"até {d.t_sala_max_aula:.0f} °C, sensação {d.ic_sala_max_aula:.0f} °C" if d.t_sala_max_aula else ""
        linhas.append(f"• {_DIA_SEMANA[dt.weekday()]} {dt:%d/%m}: *{d.faixa_sala}* ({valor})")
    graves = sorted(
        {d.faixa_sala for d in r.dias if d.previsao and d.faixa_sala in ACOES},
        key=["Atenção", "Alerta", "Perigo"].index,
    )
    if graves:
        linhas.append("")
        linhas.append("O que fazer:")
        linhas += [f"• {f}: {ACOES[f]}." for f in graves]
        linhas.append("• Sinais de mal-estar (tontura, enjoo, dor de cabeça forte): tirar do calor e chamar atendimento.")
    else:
        linhas.append("Sem faixa de risco prevista. Seguimos monitorando.")
    if r.aviso_emitido:
        linhas.append(f"\n⚠️ Aviso: {r.motivo_aviso}")
    linhas.append(
        f"\n_Estimativa a partir da previsão do tempo e do tipo de telhado ({ROTULO_TELHADO[r.escola.tipo_telhado]})._"
    )
    linhas.append(f"_{AVISO_NAO_OFICIAL}_")
    return "\n".join(linhas)


@app.get("/api/ficha")
def ficha(
    escola_id: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    nome: str | None = None,
    telhado: str = "desconhecido",
    climatizada: bool = False,
    ajuste: float = 0.0,
    cenario: Cenario = "ao_vivo",
) -> dict[str, Any]:
    """Ficha de evidência: o que a previsão indica, com premissas e limites. Não é laudo."""
    escola, info = _escola(escola_id, lat, lon, nome, telhado, climatizada, ajuste)
    r = _avaliar(escola, cenario, incluir_horas=True)
    futuros = [d for d in r.dias if d.previsao]
    letivos = [d for d in futuros if d.dia_letivo]
    horas_aula = [h for h in (r.horas or []) if h["aula"] and h["hora"][:10] in {d.data for d in letivos}]
    horas_faixa = {f.rotulo: sum(1 for h in horas_aula if h["faixa"] == f.rotulo) for f in Faixa}
    ibutg_max = max((h["ibutg_sala"] for h in horas_aula), default=None)
    return {
        "escola": asdict(escola),
        "info": info,
        "cenario": cenario,
        "cenario_rotulo": CENARIOS[cenario]["rotulo"],
        "gerado_em": r.gerado_em,
        "periodo": [futuros[0].data, futuros[-1].data] if futuros else [],
        "dias_letivos": len(letivos),
        "horas_aula_total": len(horas_aula),
        "horas_aula_por_faixa": horas_faixa,
        "dias_ponto_cego": [d.data for d in futuros if d.ponto_cego],
        "dias": [asdict(d) for d in futuros],
        "ibutg": {
            "estimado_max_sala": ibutg_max,
            "limites_nr15": [
                {
                    "taxa_metabolica_w": m,
                    "atividade": ATIVIDADES_NR15[m],
                    "ibutg_max": lim,
                    "horas_acima": sum(1 for h in horas_aula if h["ibutg_sala"] > lim),
                }
                for m, lim in NR15_IBUTG_MAX_C.items()
            ],
            "metodo": "IBUTG = 0,7 × bulbo úmido (Stull, psicrométrico) + 0,3 × globo, com globo = ar da sala. "
            "Tende a ficar abaixo do IBUTG medido (telhado quente irradia; ar parado).",
            "limite_legal": "A NR-15 (Anexo 3, item 3.1) exige laudo com medidor de IBUTG calibrado conforme a "
            "NHO 06. Esta estimativa indica onde medir; não caracteriza insalubridade.",
            "cozinha": "Cozinhas não são estimadas: fogões e caldeirões são fonte de calor que o modelo não tem.",
        },
        "aviso_emitido": r.aviso_emitido,
        "motivo_aviso": r.motivo_aviso,
        "premissas": r.premissas,
        "fontes": [
            "Previsão: Open-Meteo (CC BY 4.0), modelos globais e regionais, ~9 km.",
            "Índice de Calor: NOAA/NWS (Rothfusz), algoritmo completo.",
            "Níveis de Calor: Decreto Rio nº 54.740/2024 (regras de persistência), aplicados como estimativa.",
            "Sala: Amankwaa et al., Buildings & Cities (Acra, 16 salas).",
            "Faixas da sala: lei de Nova York (27,8 °C / 31,1 °C) e faixas de IC do NWS.",
            "Limites ocupacionais: NR-15, Anexo 3, Quadro 1 (Portaria SEPRT 1.359/2019).",
            _BASE["fonte"],
        ],
        "aviso_nao_oficial": AVISO_NAO_OFICIAL,
        "natureza": "Ficha de evidência preditiva. Não é laudo técnico nem medição.",
    }


@app.post("/api/parecer")
def parecer(
    escola_id: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    nome: str | None = None,
    telhado: str = "desconhecido",
    climatizada: bool = False,
    ajuste: float = 0.0,
    cenario: Cenario = "ao_vivo",
) -> dict[str, Any]:
    import gemini_evaluator as ge

    escola, _ = _escola(escola_id, lat, lon, nome, telhado, climatizada, ajuste)
    r = _avaliar(escola, cenario)
    try:
        return ge.avaliar(r).model_dump()
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, f"Falha na chamada ao Gemini: {exc}") from exc


@app.get("/api/gemini/contexto")
def gemini_contexto(escola_id: str | None = None, cenario: Cenario = "ao_vivo") -> dict[str, Any]:
    """O que o Laboratório Gemini mostra: instrução, schema, payload e script."""
    import gemini_evaluator as ge

    payload = None
    if escola_id:
        escola, _ = _escola(escola_id, None, None, None, "desconhecido", False, 0.0)
        payload = ge.montar_prompt(_avaliar(escola, cenario))
    return {
        "modelo": ge.MODELO_PADRAO,
        "instrucao_sistema": ge.INSTRUCAO_SISTEMA,
        "schema": ge.ParecerTecnico.model_json_schema(),
        "prompt": payload,
        "script_python": SCRIPT_PYTHON.replace("__MODELO__", ge.MODELO_PADRAO),
    }


SCRIPT_PYTHON = '''# pip install google-genai pydantic
# export GEMINI_API_KEY=...
import json
from google import genai
from google.genai import types

INSTRUCAO = open("instrucao_sistema.txt", encoding="utf-8").read()
SCHEMA = json.load(open("schema.json", encoding="utf-8"))
PROMPT = open("prompt.txt", encoding="utf-8").read()

client = genai.Client()
resp = client.models.generate_content(
    model="__MODELO__",
    contents=PROMPT,
    config=types.GenerateContentConfig(
        system_instruction=INSTRUCAO,
        response_mime_type="application/json",
        response_json_schema=SCHEMA,
        temperature=0.2,
    ),
)
print(json.dumps(json.loads(resp.text), ensure_ascii=False, indent=2))
'''


# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{caminho:path}", include_in_schema=False)
    def spa(caminho: str) -> FileResponse:
        alvo = DIST / caminho
        if caminho and alvo.is_file() and DIST in alvo.resolve().parents:
            return FileResponse(alvo)
        return FileResponse(DIST / "index.html")

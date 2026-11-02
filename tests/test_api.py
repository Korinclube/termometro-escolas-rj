from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

import api
import pipeline as pl

IRAJA = "33074577"


def _resposta(inicio: date, dias: int = 5, pico: float = 33.0, rh: float = 60) -> dict:
    dia = [25.0] * 12 + [pico] * 5 + [25.0] * 7
    tempos = [
        (datetime.combine(inicio, datetime.min.time()) + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M")
        for i in range(24 * dias)
    ]
    return {"hourly": {"time": tempos, "temperature_2m": dia * dias, "relative_humidity_2m": [rh] * len(tempos)}}


@pytest.fixture
def cliente(monkeypatch, tmp_path):
    chamadas = []
    hoje = pl.pd.Timestamp.now(tz=pl.FUSO).date()

    def falsa_previsao(lat, lon, **_):
        chamadas.append(("previsao", len(lat) if isinstance(lat, list) else 1))
        r = _resposta(hoje - timedelta(days=2))
        return [r] * len(lat) if isinstance(lat, list) else r

    def falsa_reanalise(lat, lon, inicio, fim, **_):
        chamadas.append(("reanalise", len(lat) if isinstance(lat, list) else 1))
        r = _resposta(inicio, pico=36.0)
        return [r] * len(lat) if isinstance(lat, list) else r

    monkeypatch.setattr(pl, "buscar_previsao", falsa_previsao)
    monkeypatch.setattr(pl, "buscar_reanalise", falsa_reanalise)
    monkeypatch.setattr(api, "CACHE_DISCO", tmp_path)
    api._cache.clear()
    c = TestClient(api.app)
    c.chamadas = chamadas
    return c


def test_escolas_da_base_publica(cliente):
    escolas = cliente.get("/api/escolas").json()
    assert len(escolas) > 1000
    e = next(x for x in escolas if x["id"] == IRAJA)
    assert e["bairro"] == "Irajá" and e["rede"] == "Municipal"


def test_painel_resume_rede_e_usa_cache(cliente):
    r = cliente.get("/api/painel").json()
    assert r["resumo"]["total"] == len(r["escolas"]) > 1000
    assert sum(r["resumo"]["por_faixa"].values()) == r["resumo"]["total"]
    assert len(r["dias"]) == 3
    chamadas = len(cliente.chamadas)
    cliente.get("/api/painel")
    assert len(cliente.chamadas) == chamadas  # cache


def test_painel_premissa_de_telhado_muda_resultado(cliente):
    pior = cliente.get("/api/painel?telhado=desconhecido").json()["resumo"]["por_faixa"]
    laje = cliente.get("/api/painel?telhado=laje").json()["resumo"]["por_faixa"]
    assert pior["Alerta"] + pior["Perigo"] >= laje["Alerta"] + laje["Perigo"]
    assert cliente.get("/api/painel?telhado=palha").status_code == 422


def test_previsao_por_escola_traz_horas(cliente):
    r = cliente.get("/api/previsao", params={"escola_id": IRAJA, "telhado": "laje"}).json()
    assert r["info"]["id"] == IRAJA
    assert r["escola"]["tipo_telhado"] == "laje"
    assert len(r["horas"]) >= 72 and {"t_sala", "ic_sala", "faixa", "aula"} <= set(r["horas"][0])


def test_previsao_ponto_personalizado_e_validacoes(cliente):
    ok = cliente.get("/api/previsao", params={"lat": -22.716, "lon": -43.555, "nome": "Queimados"})
    assert ok.status_code == 200 and ok.json()["escola"]["nome"] == "Queimados"
    assert cliente.get("/api/previsao", params={"lat": -10, "lon": -43}).status_code == 422
    assert cliente.get("/api/previsao", params={"escola_id": "000"}).status_code == 404
    assert cliente.get("/api/previsao", params={"escola_id": IRAJA, "ajuste": 9}).status_code == 422


def test_cenario_reprise_usa_reanalise_e_datas_de_2025(cliente):
    r = cliente.get("/api/previsao", params={"escola_id": IRAJA, "cenario": "fev2025"}).json()
    futuros = [d["data"] for d in r["dias"] if d["previsao"]]
    assert futuros == ["2025-02-17", "2025-02-18", "2025-02-19"]
    assert ("reanalise", 1) in cliente.chamadas


def test_boletim_tem_aviso_e_marca_simulacao(cliente):
    t = cliente.get("/api/boletim", params={"escola_id": IRAJA, "cenario": "mais2"}).json()["texto"]
    assert pl.AVISO_NAO_OFICIAL in t
    assert "SIMULAÇÃO" in t
    assert "O que fazer" in t


def test_ficha_nao_e_laudo(cliente):
    f = cliente.get("/api/ficha", params={"escola_id": IRAJA, "telhado": "telha_metalica_sem_forro"}).json()
    assert "Não é laudo" in f["natureza"]
    assert "NHO 06" in f["ibutg"]["limite_legal"]
    assert [x["ibutg_max"] for x in f["ibutg"]["limites_nr15"]] == [29.1, 28.2]
    assert sum(f["horas_aula_por_faixa"].values()) == f["horas_aula_total"]


def test_parecer_sem_chave_retorna_503(cliente, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    r = cliente.post("/api/parecer", params={"escola_id": IRAJA})
    assert r.status_code == 503 and "GEMINI_API_KEY" in r.json()["detail"]


def test_contexto_gemini_mostra_schema_e_prompt(cliente):
    c = cliente.get("/api/gemini/contexto", params={"escola_id": IRAJA}).json()
    assert c["schema"]["title"] == "ParecerTecnico"
    assert '"horas"' not in c["prompt"]
    assert "google-genai" in c["script_python"]


def test_falha_de_rede_vira_502(cliente, monkeypatch):
    def quebra(*a, **k):
        raise ConnectionError("sem rede")

    monkeypatch.setattr(pl, "buscar_previsao", quebra)
    api._cache.clear()
    assert cliente.get("/api/previsao", params={"escola_id": IRAJA}).status_code == 502

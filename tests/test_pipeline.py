from datetime import date, datetime, timedelta

import pandas as pd
import pytest

from pipeline import (
    AVISO_NAO_OFICIAL,
    Escola,
    Faixa,
    avaliar_escola,
    classificar_faixa,
    classificar_niveis_calor,
    estimar_temperatura_sala,
    indice_calor_c,
    umidade_relativa_interna,
)


def f2c(f: float) -> float:
    return (f - 32) * 5 / 9


# Valores da tabela de índice de calor do NWS (°F).
@pytest.mark.parametrize(
    "t_f, rh, hi_f",
    [(90, 70, 106), (96, 65, 121), (86, 50, 88), (100, 40, 109), (80, 40, 80)],
)
def test_indice_calor_bate_com_tabela_nws(t_f, rh, hi_f):
    assert indice_calor_c(f2c(t_f), rh) == pytest.approx(f2c(hi_f), abs=1.0)


def test_indice_calor_ameno_fica_perto_da_temperatura():
    assert indice_calor_c(20.0, 60) == pytest.approx(20.0, abs=1.0)


def test_exemplos_da_metodologia():
    # "sala a 32 °C com 70% chega a 40 °C"; "34 °C com 70% passa de 46 °C"
    assert indice_calor_c(32, 70) >= 40
    assert indice_calor_c(34, 70) > 46


def test_umidade_cai_quando_sala_aquece():
    assert umidade_relativa_interna(30, 70, 32.5) < 70
    assert umidade_relativa_interna(30, 70, 30) == pytest.approx(70)
    assert umidade_relativa_interna(30, 95, 25) == 100.0


def test_temperatura_sala_por_telhado():
    base = dict(nome="x", lat=0, lon=0)
    assert estimar_temperatura_sala(30, Escola(**base, tipo_telhado="laje")) == 29
    assert estimar_temperatura_sala(30, Escola(**base, tipo_telhado="fibrocimento_sem_forro")) == 30
    assert estimar_temperatura_sala(30, Escola(**base, tipo_telhado="telha_metalica_sem_forro")) == 32.5
    clim = Escola(**base, tipo_telhado="telha_metalica_sem_forro", climatizacao_funcionando=True)
    assert estimar_temperatura_sala(30, clim) == 24
    assert estimar_temperatura_sala(18, clim) == 20.5


@pytest.mark.parametrize(
    "t_in, ic_in, esperado",
    [
        (27.7, 28, Faixa.NORMAL),
        (27.8, 28, Faixa.ATENCAO),
        (31.1, 33, Faixa.ALERTA),
        (30.0, 40.0, Faixa.ALERTA),
        (34.0, 46.0, Faixa.PERIGO),
    ],
)
def test_faixas(t_in, ic_in, esperado):
    assert classificar_faixa(t_in, ic_in) == esperado


def _serie_ic(perfis: list[list[float]], inicio: date = date(2027, 2, 15)) -> pd.Series:
    idx, vals = [], []
    for i, perfil in enumerate(perfis):
        for h in range(24):
            idx.append(datetime.combine(inicio + timedelta(days=i), datetime.min.time()) + timedelta(hours=h))
            vals.append(perfil[h])
    return pd.Series(vals, index=pd.DatetimeIndex(idx))


def _dia(pico: float, horas: int) -> list[float]:
    return [pico if 10 <= h < 10 + horas else 30.0 for h in range(24)]


def test_nc_regras_de_persistencia():
    s = _serie_ic([_dia(30, 0), _dia(38, 4), _dia(38, 3), _dia(38, 4), _dia(41, 4), _dia(45, 2), _dia(37, 5)])
    d = sorted(classificar_niveis_calor(s).items())
    niveis = [n for _, n in d]
    # dia 2: 3h só -> quebra o evento; dia 1 isolado = NC2; dias 3-6 evento de 4 dias
    assert niveis == [1, 2, 1, 3, 4, 5, 3]


def test_nc_dia_incompleto_e_ignorado():
    s = _serie_ic([_dia(38, 6)])[:20]
    assert classificar_niveis_calor(s) == {}


def _dados_open_meteo(t_por_hora: list[float], rh: float, inicio: date) -> dict:
    tempos = [
        (datetime.combine(inicio, datetime.min.time()) + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M")
        for i in range(len(t_por_hora))
    ]
    return {"hourly": {"time": tempos, "temperature_2m": t_por_hora, "relative_humidity_2m": [rh] * len(tempos)}}


def test_avaliar_escola_emite_aviso_em_dois_dias_letivos_de_alerta():
    # seg 2027-02-15 a qua: tarde a 33 °C, telhado metálico -> sala 35.5 °C = Alerta
    dia = [26.0] * 12 + [33.0] * 5 + [26.0] * 7
    dados = _dados_open_meteo(dia * 3, 60, date(2027, 2, 15))
    escola = Escola("Teste", -22.8, -43.3, "telha_metalica_sem_forro")
    r = avaliar_escola(escola, dados, hoje=date(2027, 2, 15))

    assert [d.faixa_sala for d in r.dias] == ["Alerta"] * 3
    assert r.aviso_emitido
    assert r.aviso_nao_oficial == AVISO_NAO_OFICIAL
    assert all(d.horas_aula_por_faixa for d in r.dias)


def test_fim_de_semana_nao_conta_e_sem_aviso_em_dia_ameno():
    dados = _dados_open_meteo([24.0] * 72, 60, date(2027, 2, 19))  # sex, sáb, dom
    r = avaliar_escola(Escola("T", 0, 0, "laje"), dados, hoje=date(2027, 2, 19))
    assert [d.faixa_sala for d in r.dias] == ["Normal", "Sem aula", "Sem aula"]
    assert not r.aviso_emitido


# --- funções adicionadas para o painel ---------------------------------------
from pipeline import NR15_IBUTG_MAX_C, bulbo_umido_c, ibutg_interno_estimado_c  # noqa: E402


def test_bulbo_umido_stull_valor_de_referencia():
    # Stull (2011): T = 20 °C, UR = 50 % -> Tw ≈ 13,7 °C
    assert bulbo_umido_c(20, 50) == pytest.approx(13.7, abs=0.1)


def test_ibutg_estimado_fica_entre_bulbo_umido_e_ar():
    t, rh = 32.0, 60.0
    assert bulbo_umido_c(t, rh) < ibutg_interno_estimado_c(t, rh) < t


def test_limites_nr15_conferidos():
    assert NR15_IBUTG_MAX_C == {251: 29.1, 300: 28.2}


def test_ajuste_e_cenario_entram_na_conta_e_nas_premissas():
    dia = [26.0] * 12 + [30.0] * 5 + [26.0] * 7
    dados = _dados_open_meteo(dia * 3, 60, date(2027, 2, 15))
    base = avaliar_escola(Escola("T", 0, 0, "fibrocimento_sem_forro"), dados, hoje=date(2027, 2, 15))
    mais = avaliar_escola(
        Escola("T", 0, 0, "fibrocimento_sem_forro", ajuste_sala_c=1.0), dados, hoje=date(2027, 2, 15), delta_cenario_c=2.0
    )
    assert mais.dias[0].t_sala_max_aula == pytest.approx(base.dias[0].t_sala_max_aula + 3.0)
    assert any("Ajuste manual" in p for p in mais.premissas)
    assert any("sensibilidade" in p for p in mais.premissas)


def test_ponto_cego_quando_sala_em_alerta_e_rua_em_nc1():
    # rua a 31 °C e UR 40 %: IC da rua < 36 (NC1); metal -> sala 33,5 °C = Alerta
    dia = [24.0] * 12 + [31.0] * 5 + [24.0] * 7
    dados = _dados_open_meteo(dia * 3, 40, date(2027, 2, 15))
    r = avaliar_escola(Escola("T", 0, 0, "telha_metalica_sem_forro"), dados, hoje=date(2027, 2, 15), incluir_horas=True)
    assert all(d.nc_estimado_rua == 1 and d.faixa_sala == "Alerta" and d.ponto_cego for d in r.dias)
    assert len(r.horas) == 72 and sum(h["aula"] for h in r.horas) == 30


def test_horizonte_corta_dias_alem_de_72h():
    dados = _dados_open_meteo([25.0] * 24 * 5, 60, date(2027, 2, 15))
    r = avaliar_escola(Escola("T", 0, 0), dados, hoje=date(2027, 2, 15))
    assert [d.data for d in r.dias] == ["2027-02-15", "2027-02-16", "2027-02-17"]


def test_fixtures_do_simulador_estao_em_dia():
    import json
    import sys
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(raiz / "scripts"))
    from gerar_fixtures_fisica import SAIDA, casos

    assert json.loads(SAIDA.read_text(encoding="utf-8")) == casos(), "rode scripts/gerar_fixtures_fisica.py"

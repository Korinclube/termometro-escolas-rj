import json
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from gemini_evaluator import (
    SCHEMA_PATH,
    ParecerTecnico,
    avaliar,
    montar_prompt,
)
from pipeline import AVISO_NAO_OFICIAL, Escola, avaliar_escola

PARECER_OK = {
    "resumo": "Previsão de Alerta na terça e na quarta à tarde.",
    "riscos_principais": ["Sala a 35,5 °C entre 12h e 17h."],
    "acoes_recomendadas": [
        {"publico": "professores", "acao": "Suspenda a educação física.", "quando": "2027-02-16", "faixa_gatilho": "Alerta"}
    ],
    "mensagem_familias": "Mande seu filho com garrafa de água.",
    "limitacoes": ["Estimativa sem sensor na sala."],
}


def _resultado():
    inicio = date(2027, 2, 15)
    dia = [26.0] * 12 + [33.0] * 5 + [26.0] * 7
    tempos = [(datetime.combine(inicio, datetime.min.time()) + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(72)]
    dados = {"hourly": {"time": tempos, "temperature_2m": dia * 3, "relative_humidity_2m": [60] * 72}}
    return avaliar_escola(Escola("Teste", -22.8, -43.3, "telha_metalica_sem_forro"), dados, hoje=inicio)


class FakeModels:
    def __init__(self, parsed=None, text=""):
        self.parsed, self.text, self.chamadas = parsed, text, []

    def generate_content(self, **kwargs):
        self.chamadas.append(kwargs)
        return SimpleNamespace(parsed=self.parsed, text=self.text)


def test_avaliar_usa_schema_e_anexa_dados_deterministicos():
    models = FakeModels(parsed=ParecerTecnico(**PARECER_OK))
    out = avaliar(_resultado(), client=SimpleNamespace(models=models), modelo="m-teste")

    cfg = models.chamadas[0]["config"]
    assert cfg.response_mime_type == "application/json"
    assert cfg.response_schema is ParecerTecnico
    assert out.aviso_emitido is True
    assert out.pior_faixa_prevista in {"Alerta", "Perigo"}
    assert out.aviso_nao_oficial == AVISO_NAO_OFICIAL
    assert out.modelo == "m-teste"


def test_avaliar_valida_texto_quando_parsed_vem_vazio():
    models = FakeModels(parsed=None, text=json.dumps(PARECER_OK))
    out = avaliar(_resultado(), client=SimpleNamespace(models=models))
    assert out.parecer.acoes_recomendadas[0].faixa_gatilho == "Alerta"


def test_avaliar_rejeita_resposta_fora_do_schema():
    ruim = dict(PARECER_OK, acoes_recomendadas=[dict(PARECER_OK["acoes_recomendadas"][0], faixa_gatilho="NC5")])
    models = FakeModels(parsed=None, text=json.dumps(ruim))
    with pytest.raises(ValidationError):
        avaliar(_resultado(), client=SimpleNamespace(models=models))


def test_sem_chave_da_erro_claro(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        avaliar(_resultado())


def test_prompt_so_leva_dias_de_previsao_e_aviso():
    p = montar_prompt(_resultado())
    assert AVISO_NAO_OFICIAL in p
    assert '"previsao": false' not in p


def test_schema_json_sincronizado_com_modelo():
    assert json.loads(SCHEMA_PATH.read_text(encoding="utf-8")) == ParecerTecnico.model_json_schema()

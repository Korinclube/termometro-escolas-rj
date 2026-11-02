"""Parecer técnico do Gemini sobre o resultado do pipeline.

Divisão de responsabilidades:
- Números, faixas e NC vêm SEMPRE do pipeline (determinístico, auditável).
- O Gemini só redige: resumo, riscos, ações por público e mensagem às famílias,
  em JSON validado pelo schema (`ParecerTecnico` == schema.json).
- O aviso de "não oficial" é anexado pelo código, não depende do modelo.

Uso:
    export GEMINI_API_KEY=...
    python src/gemini_evaluator.py --telhado telha_metalica_sem_forro
    python src/gemini_evaluator.py --export-schema   # regrava schema.json
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from pipeline import (
    AVISO_NAO_OFICIAL,
    DELTA_TELHADO_C,
    Escola,
    ResultadoEscola,
    avaliar_escola,
    buscar_previsao,
)

MODELO_PADRAO = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema.json"

Publico = Literal["direcao", "professores", "merendeiras", "alunos", "familias", "rede_de_ensino"]
FaixaGatilho = Literal["Atenção", "Alerta", "Perigo"]


class AcaoRecomendada(BaseModel):
    publico: Publico
    acao: str = Field(description="Ação concreta, em uma frase, no imperativo.")
    quando: str = Field(description="Data ou condição de disparo (ex.: '2026-11-04, turno da tarde').")
    faixa_gatilho: FaixaGatilho


class ParecerTecnico(BaseModel):
    resumo: str = Field(description="2 a 4 frases sobre o risco nos próximos dias letivos.")
    riscos_principais: list[str] = Field(description="Até 4 riscos, citando datas e números do input.")
    acoes_recomendadas: list[AcaoRecomendada]
    mensagem_familias: str = Field(description="Mensagem curta de WhatsApp, linguagem simples, sem alarmismo.")
    limitacoes: list[str] = Field(description="Incertezas do dado que o leitor precisa saber.")


class ParecerCompleto(BaseModel):
    """Saída final: dado determinístico + texto do modelo + aviso fixo."""

    escola: str
    aviso_emitido: bool
    motivo_aviso: str
    pior_faixa_prevista: str
    parecer: ParecerTecnico
    modelo: str
    aviso_nao_oficial: str = AVISO_NAO_OFICIAL


INSTRUCAO_SISTEMA = f"""\
Você apoia o projeto Termômetro das Escolas (Rio de Janeiro), que prevê calor
dentro de salas de aula públicas. Escreva em português do Brasil, para diretores
e professores.

Regras obrigatórias:
1. Use apenas os números e datas do JSON de entrada. Não calcule, não estime,
   não invente valores nem fontes.
2. Nunca diga que as faixas ou o NC são oficiais. O NC do input é uma estimativa
   regionalizada, não o nível do COR. Texto de referência: "{AVISO_NAO_OFICIAL}"
3. Não faça diagnóstico médico. Sintomas de mal-estar por calor -> acionar
   atendimento de saúde.
4. Recomende ações só para dias letivos com faixa Atenção ou pior, usando esta base:
   - Atenção (sala >= 27,8 °C): apagar luzes, fechar persianas do lado do sol,
     ventilação cruzada, água a cada 30 minutos.
   - Alerta (sala >= 31,1 °C ou IC >= 40 °C): suspender educação física, levar
     turmas a salas mais frescas, avisar famílias, considerar turno reduzido.
   - Perigo (IC da sala >= 46 °C ou qualquer caso de mal-estar): tirar os alunos
     da sala, acionar atendimento de saúde, registrar e comunicar à rede.
     Nenhum aluno fica na sala para medir.
5. Inclua merendeiras quando houver Alerta ou Perigo (cozinha é o ponto mais quente).
6. Se nenhum dia letivo passar de Normal, diga isso e recomende só monitoramento.
7. Em limitacoes, reflita as premissas do input (telhado, resolução da previsão).
"""


class _ClienteGemini(Protocol):
    models: Any


def _pior_faixa(resultado: ResultadoEscola) -> str:
    ordem = ["Normal", "Atenção", "Alerta", "Perigo"]
    faixas = [d.faixa_sala for d in resultado.dias if d.previsao and d.faixa_sala in ordem]
    return max(faixas, key=ordem.index) if faixas else "Normal"


def montar_prompt(resultado: ResultadoEscola) -> str:
    dados = resultado.to_dict()
    dados["dias"] = [d for d in dados["dias"] if d["previsao"]]
    dados.pop("horas", None)
    return (
        "Gere o parecer técnico para esta escola a partir da previsão abaixo.\n\n"
        + json.dumps(dados, ensure_ascii=False, indent=2)
    )


def avaliar(
    resultado: ResultadoEscola,
    client: _ClienteGemini | None = None,
    modelo: str = MODELO_PADRAO,
) -> ParecerCompleto:
    from google.genai import types

    if client is None:
        if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
            raise RuntimeError("Defina GEMINI_API_KEY para chamar o Gemini.")
        from google import genai

        client = genai.Client()

    resposta = client.models.generate_content(
        model=modelo,
        contents=montar_prompt(resultado),
        config=types.GenerateContentConfig(
            system_instruction=INSTRUCAO_SISTEMA,
            response_mime_type="application/json",
            response_schema=ParecerTecnico,
            temperature=0.2,
        ),
    )
    parecer = resposta.parsed
    if not isinstance(parecer, ParecerTecnico):
        # Valida o texto bruto; levanta ValidationError se fugir do schema.
        parecer = ParecerTecnico.model_validate_json(resposta.text)

    return ParecerCompleto(
        escola=resultado.escola.nome,
        aviso_emitido=resultado.aviso_emitido,
        motivo_aviso=resultado.motivo_aviso,
        pior_faixa_prevista=_pior_faixa(resultado),
        parecer=parecer,
        modelo=modelo,
    )


def exportar_schema(caminho: Path = SCHEMA_PATH) -> None:
    caminho.write_text(
        json.dumps(ParecerTecnico.model_json_schema(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Parecer Gemini do Termômetro das Escolas")
    p.add_argument("--nome", default="Escola exemplo - Madureira")
    p.add_argument("--lat", type=float, default=-22.8431)
    p.add_argument("--lon", type=float, default=-43.3358)
    p.add_argument("--telhado", choices=list(DELTA_TELHADO_C), default="fibrocimento_sem_forro")
    p.add_argument("--climatizada", action="store_true")
    p.add_argument("--modelo", default=MODELO_PADRAO)
    p.add_argument("--export-schema", action="store_true")
    a = p.parse_args()

    if a.export_schema:
        exportar_schema()
        print(f"Schema gravado em {SCHEMA_PATH}")
        return

    escola = Escola(a.nome, a.lat, a.lon, a.telhado, a.climatizada)
    resultado = avaliar_escola(escola, buscar_previsao(a.lat, a.lon))
    print(avaliar(resultado, modelo=a.modelo).model_dump_json(indent=2))


if __name__ == "__main__":
    main()

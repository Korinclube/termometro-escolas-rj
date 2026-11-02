# Termômetro das Escolas RJ

Previsão de 72 horas do calor **dentro das salas de aula** públicas do Rio de Janeiro. O sistema cruza
a previsão horária do Open-Meteo, o Índice de Calor da NOAA (Rothfusz), as regras de persistência do
Decreto Rio nº 54.740/2024 e uma estimativa provisória da temperatura da sala por tipo de telhado.

> Faixas definidas pelo Termômetro das Escolas a partir de referências internacionais; não são norma
> brasileira nem nível oficial do COR.

## O que tem

- **Painel web** (React + Vite + Tailwind): monitoramento 72 h da rede, mapa de risco (faixa prevista ou
  exposição por satélite), simulador da sala, ficha de evidência imprimível, laboratório Gemini e
  boletim pronto para WhatsApp.
- **API** (FastAPI): previsão por escola ou coordenada, resumo da rede, cenários (reprise da onda de calor
  de fevereiro de 2025 por reanálise e testes de sensibilidade), boletim, ficha e parecer.
- **Pipeline** (`src/pipeline.py`): física e regras de domínio, com testes.
- **Parecer com Gemini** (`src/gemini_evaluator.py`): o modelo só redige; números e faixas vêm do cálculo,
  e a resposta segue `schema.json`.
- **Base de escolas** (`data/escolas.json`): 1.540 escolas públicas da capital com coordenadas, desvio de
  temperatura de superfície, verde no entorno e INSE (Instituto Alana e MapBiomas, "Verde nas escolas";
  bairros do IPP/Data.Rio). A Baixada entra como ponto de previsão ou ponto adicionado pelo usuário.

## Rodar

```bash
pip install -r requirements.txt
cd web && npm install && npm run build && cd ..
uvicorn api:app --app-dir src --port 8000
```

Abra http://localhost:8000. Para o parecer do Gemini, defina `GEMINI_API_KEY` (e, se quiser,
`GEMINI_MODEL`) antes de subir a API.

Desenvolvimento do frontend: com a API rodando, `cd web && npm run dev`.

Previsão no terminal, sem painel:

```bash
python src/pipeline.py --telhado telha_metalica_sem_forro
```

## Testes

```bash
pytest              # Python: física, níveis, faixas, API, Gemini (sem rede nem chave)
cd web && npm test  # a física do simulador (TypeScript) bate com a do Python
```

## Limites que o painel declara

- A previsão tem ~11 km de resolução e não distingue escolas vizinhas; o que distingue é o prédio.
- A temperatura da sala vem de uma regra provisória (estudo em Acra, Gana) até haver sensores calibrados.
- O nível de calor por célula é uma estimativa, não o nível oficial do COR.
- O IBUTG é estimado sem termômetro de globo e não substitui a avaliação da NR-15 (medidor conforme NHO 06).
- Temperatura de superfície por satélite é só ranking de exposição, nunca temperatura da sala.

Regras de domínio, comandos e decisões de projeto estão em [`CLAUDE.md`](CLAUDE.md).

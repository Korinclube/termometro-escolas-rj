# Termômetro das Escolas RJ - Pipeline Preditivo de Calor

## Visão geral
Previsão de 72 h do calor dentro de salas de aula públicas da Região Metropolitana do Rio.
Dois andares:
1. **Rua**: Open-Meteo horário -> Índice de Calor (Rothfusz/NWS) -> "nível estimado na rua"
   com as regras do Decreto Rio nº 54.740/2024. Sempre rotulado como estimativa.
2. **Sala**: função de transferência provisória por telhado -> T e IC internos -> faixa
   Atenção / Alerta / Perigo no horário de aula.
O Gemini (`src/gemini_evaluator.py`) só redige o parecer; números e faixas vêm do pipeline.

## Comandos
- Instalar: `pip install -r requirements.txt` e `cd web && npm install`
- Painel (produção local): `cd web && npm run build`, depois `uvicorn api:app --app-dir src --port 8000` e abrir http://localhost:8000
- Painel (desenvolvimento): API como acima + `cd web && npm run dev` (Vite faz proxy de /api para :8000)
- Previsão no terminal (sem IA): `python src/pipeline.py [--telhado telha_metalica_sem_forro] [--json]`
- Parecer Gemini: `GEMINI_API_KEY=... python src/gemini_evaluator.py` (ou botão no Laboratório Gemini)
- Regravar schema.json após mudar `ParecerTecnico`: `python src/gemini_evaluator.py --export-schema`
- Regravar fixtures do simulador após mudar regras de física: `python scripts/gerar_fixtures_fisica.py`
- Atualizar a base de escolas: `python scripts/preparar_escolas.py alana.csv bairros.geojson` (fontes no docstring)
- Testes: `pytest` (Python, sem rede nem chave) e `cd web && npm test` (física TS = Python)

## Estrutura
- `src/pipeline.py`: física e regras (fonte da verdade). `src/api.py`: FastAPI, cache de previsão
  (memória + `.cache/meteo`, 30 min), cenários, boletim, ficha de evidência. `src/gemini_evaluator.py`: parecer.
- `data/escolas.json`: 1.540 escolas públicas da capital (Alana/MapBiomas + bairros IPP). A Baixada não está
  na base: entra como ponto de previsão (centro do município) ou ponto adicionado pelo usuário.
- `web/`: React + Vite + Tailwind. `src/theme.css` é a fonte única de cores/raio; `components/ui.tsx` tem as
  peças compartilhadas (Secao, Metrica, Botao, FaixaMarca, Carregando, Erro, campo). `lib/fisica.ts` é um porte
  do andar da sala para o simulador; `fisica.fixtures.json` (gerado pelo Python) amarra os dois lados.
- Open-Meteo gratuito conta cada ponto como uma chamada: a API agrupa escolas em células de 0,1° e usa cache.

## Regras de domínio (não alterar limiares sem fonte citada)
1. **Índice de Calor**: algoritmo completo do NWS (média simples+T, regressão se >= 80 °F,
   ajustes de umidade baixa/alta). Testado contra a tabela do NWS.
2. **Nível estimado na rua (Decreto 54.740/2024)**, por dia com 24 h de dados:
   - q36: IC > 36 °C por >= 4 h; q40: IC >= 40 °C por >= 4 h; q44: IC > 44 °C por >= 2 h.
   - Evento = dias q36/q44 consecutivos. 1-2 dias -> NC2. >= 3 dias -> NC3 (q36), NC4 (q40), NC5 (q44).
   - Fora de evento -> NC1. `past_days=2` dá contexto de persistência.
   - NUNCA chamar de nível oficial do COR (o oficial é um só para a cidade).
3. **Temperatura da sala (provisória, Amankwaa et al., Acra)**: laje -1,0 °C; fibrocimento sem
   forro +0,0 °C; telha metálica sem forro +2,5 °C; desconhecido = pior caso (+2,5 °C).
   Climatizada e funcionando: teto de 24 °C. UR interna conserva a pressão de vapor da rua.
   Substituir pela regressão por classe de prédio quando houver sensores calibrados.
4. **Faixas da sala (proposta do projeto, não norma)**, avaliadas sobre T e IC *internos*:
   - Atenção: T_sala >= 27,8 °C.
   - Alerta: T_sala >= 31,1 °C ou IC_sala >= 40 °C.
   - Perigo: IC_sala >= 46 °C (ou qualquer mal-estar, não previsível).
5. **Aviso às escolas**: Alerta ou pior em 2 dias letivos seguidos da previsão.
6. **Texto obrigatório** em toda saída pública: constante `AVISO_NAO_OFICIAL` em `pipeline.py`.
7. Temperatura de superfície de satélite nunca vira "temperatura da escola" - só ranking de exposição,
   com escala de cor própria (nunca as cores das faixas).
8. **Cenários**: "fev2025" reprisa 17-19/02/2025 com reanálise (arquivo Open-Meteo); "+1/+2/+3 °C" é teste
   de sensibilidade com a mesma UR. Nenhum deles é projeção do El Niño (anomalia do oceano ≠ ar no Rio).
9. **IBUTG/NR-15**: só estimativa interna sem globo (0,7·Tw Stull + 0,3·T), comparada ao Quadro 1 do Anexo 3
   (251 W → 29,1 °C; 300 W → 28,2 °C). Nunca chamar de laudo: a NR-15 exige medidor calibrado (NHO 06).
   Cozinha não é estimada. Vale para trabalhadores, não para alunos.
10. Ponto cego = dia letivo com sala em Alerta/Perigo e rua estimada em NC1/NC2.

## Padrões de código
- Python 3.11+, tipagem estática; constantes de domínio no topo de `pipeline.py`.
- SDK `google-genai` (`genai.Client`, `response_schema=ParecerTecnico`). Modelo via `GEMINI_MODEL`.
- `schema.json` é gerado de `ParecerTecnico`; um teste garante que estão sincronizados.
- Toda mudança de regra de domínio vem com teste.

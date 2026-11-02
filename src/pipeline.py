"""Pipeline preditivo do Termômetro das Escolas RJ.

Dois andares, como na metodologia do projeto:
1. Rua: previsão horária Open-Meteo -> Índice de Calor (Rothfusz/NWS) -> "nível
   estimado na rua" com as regras de persistência do Decreto Rio nº 54.740/2024.
   É uma ESTIMATIVA regionalizada, nunca o nível oficial do COR.
2. Sala: função de transferência provisória por tipo de telhado -> temperatura e
   IC internos -> faixa Atenção / Alerta / Perigo durante o horário de aula.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import date
from enum import IntEnum
from typing import Any, Literal

import pandas as pd
import requests

AVISO_NAO_OFICIAL = (
    "Faixas definidas pelo Termômetro das Escolas a partir de referências "
    "internacionais; não são norma brasileira nem nível oficial do COR."
)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_ARQUIVO_URL = "https://archive-api.open-meteo.com/v1/archive"
FUSO = "America/Sao_Paulo"

# --- Andar 2: premissas provisórias da sala (substituir pela "assinatura" de
# cada classe de prédio quando houver sensores calibrados) -------------------
TipoTelhado = Literal[
    "laje", "fibrocimento_sem_forro", "telha_metalica_sem_forro", "desconhecido"
]

# Diferença média sala - rua (°C), Amankwaa et al. (Acra, 16 salas, 1 ano).
# "desconhecido" assume o pior caso medido (metal) para não subestimar risco.
DELTA_TELHADO_C: dict[str, float] = {
    "laje": -1.0,
    "fibrocimento_sem_forro": 0.0,
    "telha_metalica_sem_forro": 2.5,
    "desconhecido": 2.5,
}
TEMP_SALA_CLIMATIZADA_C = 24.0

# Faixas do projeto (metodologia, seção "Faixas de alerta propostas").
LIMIAR_ATENCAO_T_C = 27.8   # nível de ação da lei de Nova York (82 °F)
LIMIAR_ALERTA_T_C = 31.1    # limite de ocupação de Nova York (88 °F)
LIMIAR_ALERTA_IC_C = 40.0
LIMIAR_PERIGO_IC_C = 46.0

# NR-15, Anexo 3, Quadro 1 (Portaria SEPRT 1.359/2019): IBUTG máximo por taxa
# metabólica média. Só linhas conferidas na tabela oficial. Vale para
# trabalhadores (professores, merendeiras), não para alunos.
NR15_IBUTG_MAX_C: dict[int, float] = {251: 29.1, 300: 28.2}


class Faixa(IntEnum):
    NORMAL = 0
    ATENCAO = 1
    ALERTA = 2
    PERIGO = 3

    @property
    def rotulo(self) -> str:
        return ("Normal", "Atenção", "Alerta", "Perigo")[self.value]


@dataclass(frozen=True)
class Escola:
    nome: str
    lat: float
    lon: float
    tipo_telhado: TipoTelhado = "desconhecido"
    climatizacao_funcionando: bool = False
    inicio_aula_h: int = 7   # inclusivo
    fim_aula_h: int = 17     # exclusivo
    ajuste_sala_c: float = 0.0  # hipótese do usuário (lotação, ventilação); 0 = sem ajuste


# ---------------------------------------------------------------------------
# Física
# ---------------------------------------------------------------------------
def indice_calor_c(t_c: float, rh: float) -> float:
    """Índice de Calor em °C pelo algoritmo completo do NWS/NOAA (Rothfusz).

    https://www.wpc.ncep.noaa.gov/html/heatindex_equationbody.html
    """
    t_f = t_c * 9 / 5 + 32
    simples = 0.5 * (t_f + 61.0 + (t_f - 68.0) * 1.2 + rh * 0.094)
    hi_f = (simples + t_f) / 2  # o NWS tira a média com T antes do teste

    if hi_f >= 80:
        hi_f = (
            -42.379 + 2.04901523 * t_f + 10.14333127 * rh
            - 0.22475541 * t_f * rh - 0.00683783 * t_f**2
            - 0.05481717 * rh**2 + 0.00122874 * t_f**2 * rh
            + 0.00085282 * t_f * rh**2 - 0.00000199 * t_f**2 * rh**2
        )
        if rh < 13 and 80 <= t_f <= 112:
            hi_f -= ((13 - rh) / 4) * math.sqrt((17 - abs(t_f - 95.0)) / 17)
        elif rh > 85 and 80 <= t_f <= 87:
            hi_f += ((rh - 85) / 10) * ((87 - t_f) / 5)

    return (hi_f - 32) * 5 / 9


def pressao_vapor_saturacao_hpa(t_c: float) -> float:
    """Fórmula de Magnus (WMO)."""
    return 6.112 * math.exp(17.62 * t_c / (243.12 + t_c))


def umidade_relativa_interna(t_ext_c: float, rh_ext: float, t_in_c: float) -> float:
    """UR na sala conservando a pressão de vapor da rua.

    Sala mais quente que a rua -> UR menor. Ignora a umidade liberada pelos
    alunos (subestima um pouco o IC interno em salas lotadas e fechadas).
    """
    e = rh_ext / 100 * pressao_vapor_saturacao_hpa(t_ext_c)
    return min(100.0, 100 * e / pressao_vapor_saturacao_hpa(t_in_c))


def bulbo_umido_c(t_c: float, rh: float) -> float:
    """Temperatura de bulbo úmido psicrométrico (Stull, 2011). UR 5-99 %."""
    rh = min(max(rh, 5.0), 99.0)
    return (
        t_c * math.atan(0.151977 * math.sqrt(rh + 8.313659))
        + math.atan(t_c + rh) - math.atan(rh - 1.676331)
        + 0.00391838 * rh**1.5 * math.atan(0.023101 * rh) - 4.686035
    )


def ibutg_interno_estimado_c(t_c: float, rh: float) -> float:
    """IBUTG interno ESTIMADO, sem globo: 0,7 x bulbo úmido + 0,3 x globo, com
    globo = ar e bulbo úmido natural ~ psicrométrico. Telhado quente e ar parado
    elevam o IBUTG real, então este valor tende a ficar ABAIXO da medição.
    Não substitui a avaliação da NR-15 (medidor calibrado conforme NHO 06)."""
    return 0.7 * bulbo_umido_c(t_c, rh) + 0.3 * t_c


def estimar_temperatura_sala(t_ext_c: float, escola: Escola) -> float:
    t_in = t_ext_c + DELTA_TELHADO_C[escola.tipo_telhado] + escola.ajuste_sala_c
    if escola.climatizacao_funcionando:
        return min(t_in, TEMP_SALA_CLIMATIZADA_C)
    return t_in


def classificar_faixa(t_in_c: float, ic_in_c: float) -> Faixa:
    if ic_in_c >= LIMIAR_PERIGO_IC_C:
        return Faixa.PERIGO
    if t_in_c >= LIMIAR_ALERTA_T_C or ic_in_c >= LIMIAR_ALERTA_IC_C:
        return Faixa.ALERTA
    if t_in_c >= LIMIAR_ATENCAO_T_C:
        return Faixa.ATENCAO
    return Faixa.NORMAL


# ---------------------------------------------------------------------------
# Andar 1: nível estimado na rua (Decreto Rio nº 54.740/2024)
# ---------------------------------------------------------------------------
def classificar_niveis_calor(ic_horario: pd.Series) -> dict[date, int]:
    """Nível de Calor estimado (1 a 5) por dia, a partir do IC horário da rua.

    Por dia: q36 = IC > 36 por >= 4h; q40 = IC >= 40 por >= 4h; q44 = IC > 44
    por >= 2h. Dias q36/q44 seguidos formam um evento. Evento de 1-2 dias = NC2;
    evento de >= 3 dias = NC3, NC4 (dia q40) ou NC5 (dia q44). Senão NC1.
    Só dias com 24 horas de dados entram (evita contar horas que faltam).
    """
    por_dia = ic_horario.groupby(ic_horario.index.date)
    dias = [d for d, s in por_dia if len(s) == 24]
    q36 = {d: (por_dia.get_group(d) > 36).sum() >= 4 for d in dias}
    q40 = {d: (por_dia.get_group(d) >= 40).sum() >= 4 for d in dias}
    q44 = {d: (por_dia.get_group(d) > 44).sum() >= 2 for d in dias}

    niveis: dict[date, int] = {}
    i = 0
    while i < len(dias):
        if not (q36[dias[i]] or q44[dias[i]]):
            niveis[dias[i]] = 1
            i += 1
            continue
        j = i
        while j + 1 < len(dias) and (q36[dias[j + 1]] or q44[dias[j + 1]]) and (
            (dias[j + 1] - dias[j]).days == 1
        ):
            j += 1
        evento = dias[i : j + 1]
        for d in evento:
            if len(evento) < 3:
                niveis[d] = 2
            elif q44[d]:
                niveis[d] = 5
            elif q40[d]:
                niveis[d] = 4
            else:
                niveis[d] = 3
        i = j + 1
    return niveis


# ---------------------------------------------------------------------------
# Dados
# ---------------------------------------------------------------------------
def _sessao_com_retentativa() -> requests.Session:
    """Repete em 429/5xx e falhas de conexão, com espera exponencial."""
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    sessao = requests.Session()
    retry = Retry(
        total=4, backoff_factor=2, status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",), respect_retry_after_header=True,
    )
    sessao.mount("https://", HTTPAdapter(max_retries=retry))
    return sessao


_SESSAO = _sessao_com_retentativa()


def _coords(v: float | list[float]) -> str:
    return ",".join(f"{x:.4f}" for x in v) if isinstance(v, list) else f"{v:.4f}"


def buscar_previsao(
    lat: float | list[float],
    lon: float | list[float],
    forecast_days: int = 3,
    past_days: int = 2,
    session: requests.Session | None = None,
) -> Any:
    """Previsão horária Open-Meteo. past_days dá contexto para a persistência.

    Com listas de coordenadas, devolve uma lista de respostas (uma por ponto).
    """
    params: dict[str, Any] = {
        "latitude": _coords(lat),
        "longitude": _coords(lon),
        "hourly": "temperature_2m,relative_humidity_2m",
        "forecast_days": forecast_days,
        "past_days": past_days,
        "timezone": FUSO,
    }
    resp = (session or _SESSAO).get(OPEN_METEO_URL, params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()


def buscar_reanalise(
    lat: float | list[float],
    lon: float | list[float],
    inicio: date,
    fim: date,
    session: requests.Session | None = None,
) -> Any:
    """Dados horários observados/reanálise (ERA5 e outros) do arquivo Open-Meteo."""
    params: dict[str, Any] = {
        "latitude": _coords(lat),
        "longitude": _coords(lon),
        "hourly": "temperature_2m,relative_humidity_2m",
        "start_date": inicio.isoformat(),
        "end_date": fim.isoformat(),
        "timezone": FUSO,
    }
    resp = (session or _SESSAO).get(OPEN_METEO_ARQUIVO_URL, params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()


def previsao_para_dataframe(dados: dict[str, Any]) -> pd.DataFrame:
    h = dados["hourly"]
    df = pd.DataFrame(
        {"t_ext": h["temperature_2m"], "rh_ext": h["relative_humidity_2m"]},
        index=pd.to_datetime(h["time"]),
    )
    return df.dropna()


# ---------------------------------------------------------------------------
# Avaliação por escola
# ---------------------------------------------------------------------------
@dataclass
class ResumoDia:
    data: str
    dia_letivo: bool
    previsao: bool  # False = dia passado (contexto de persistência)
    nc_estimado_rua: int | None
    t_ext_max: float
    ic_ext_max: float
    t_sala_max_aula: float | None
    ic_sala_max_aula: float | None
    ibutg_sala_max_aula: float | None
    faixa_sala: str
    horas_aula_por_faixa: dict[str, int]
    ponto_cego: bool  # sala em Alerta/Perigo com a rua estimada em NC1 ou NC2


@dataclass
class ResultadoEscola:
    escola: Escola
    gerado_em: str
    dias: list[ResumoDia]
    aviso_emitido: bool
    motivo_aviso: str
    aviso_nao_oficial: str = AVISO_NAO_OFICIAL
    premissas: list[str] = field(default_factory=list)
    horas: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def avaliar_escola(
    escola: Escola,
    dados: dict[str, Any],
    hoje: date | None = None,
    delta_cenario_c: float = 0.0,
    incluir_horas: bool = False,
    horizonte_dias: int = 3,
) -> ResultadoEscola:
    """Avalia uma escola. delta_cenario_c soma graus à rua mantendo a UR
    (teste de sensibilidade, não projeção climática)."""
    df = previsao_para_dataframe(dados)
    hoje = hoje or pd.Timestamp.now(tz=FUSO).date()
    if delta_cenario_c:
        df["t_ext"] = df["t_ext"] + delta_cenario_c

    df["ic_ext"] = [indice_calor_c(t, rh) for t, rh in zip(df.t_ext, df.rh_ext)]
    df["t_in"] = [estimar_temperatura_sala(t, escola) for t in df.t_ext]
    df["rh_in"] = [
        umidade_relativa_interna(t, rh, ti)
        for t, rh, ti in zip(df.t_ext, df.rh_ext, df.t_in)
    ]
    df["ic_in"] = [indice_calor_c(t, rh) for t, rh in zip(df.t_in, df.rh_in)]
    df["faixa"] = [classificar_faixa(t, ic) for t, ic in zip(df.t_in, df.ic_in)]
    df["ibutg_in"] = [ibutg_interno_estimado_c(t, rh) for t, rh in zip(df.t_in, df.rh_in)]

    niveis = classificar_niveis_calor(df["ic_ext"])

    ultimo_dia = hoje + pd.Timedelta(days=horizonte_dias - 1)
    df = df[df.index.date <= ultimo_dia]

    dias: list[ResumoDia] = []
    for d, grupo in df.groupby(df.index.date):
        h = grupo.index.hour
        g_aula = grupo[(h >= escola.inicio_aula_h) & (h < escola.fim_aula_h)]
        letivo = d.weekday() < 5
        if letivo and not g_aula.empty:
            pior = Faixa(int(g_aula.faixa.max()))
            contagem = {f.rotulo: int((g_aula.faixa == f).sum()) for f in Faixa}
            t_max, ic_max = round(g_aula.t_in.max(), 1), round(g_aula.ic_in.max(), 1)
            ibutg_max = round(g_aula.ibutg_in.max(), 1)
        else:
            pior, contagem, t_max, ic_max, ibutg_max = Faixa.NORMAL, {}, None, None, None
        nc = niveis.get(d)
        dias.append(
            ResumoDia(
                data=d.isoformat(),
                dia_letivo=letivo,
                previsao=d >= hoje,
                nc_estimado_rua=nc,
                t_ext_max=round(grupo.t_ext.max(), 1),
                ic_ext_max=round(grupo.ic_ext.max(), 1),
                t_sala_max_aula=t_max,
                ic_sala_max_aula=ic_max,
                ibutg_sala_max_aula=ibutg_max,
                faixa_sala=pior.rotulo if letivo else "Sem aula",
                horas_aula_por_faixa=contagem,
                ponto_cego=letivo and pior >= Faixa.ALERTA and nc is not None and nc <= 2,
            )
        )

    aviso, motivo = _decidir_aviso(dias)
    premissas = [
        f"Telhado '{escola.tipo_telhado}': sala = rua {_br(DELTA_TELHADO_C[escola.tipo_telhado])} °C "
        "(regra provisória de Amankwaa et al., Acra; sem calibração local).",
        "UR da sala estimada conservando a pressão de vapor da rua; ignora umidade dos alunos.",
        "Previsão Open-Meteo com resolução de ~9 km: não distingue escolas vizinhas.",
        "Nível NC é estimativa regionalizada, não o nível oficial do COR.",
        "Feriados e recesso não são considerados (dia letivo = segunda a sexta).",
    ]
    if escola.ajuste_sala_c:
        premissas.append(
            f"Ajuste manual de {_br(escola.ajuste_sala_c)} °C na sala (hipótese do usuário, não medida)."
        )
    if delta_cenario_c:
        premissas.append(
            f"Cenário de sensibilidade: rua {_br(delta_cenario_c)} °C com a mesma UR (não é projeção do El Niño)."
        )
    if escola.climatizacao_funcionando:
        premissas.append(
            f"Sala tratada como climatizada e funcionando (teto de {_br(TEMP_SALA_CLIMATIZADA_C, sinal=False)} °C); "
            "a estatística oficial de climatização é autodeclarada."
        )
    return ResultadoEscola(
        escola=escola,
        gerado_em=pd.Timestamp.now(tz=FUSO).isoformat(timespec="minutes"),
        dias=dias,
        aviso_emitido=aviso,
        motivo_aviso=motivo,
        premissas=premissas,
        horas=_horas(df, escola) if incluir_horas else None,
    )


def _horas(df: pd.DataFrame, escola: Escola) -> list[dict[str, Any]]:
    h = df.index.hour
    aula = (h >= escola.inicio_aula_h) & (h < escola.fim_aula_h) & (df.index.weekday < 5)
    return [
        {
            "hora": ts.strftime("%Y-%m-%dT%H:%M"),
            "t_ext": round(r.t_ext, 1),
            "rh_ext": round(r.rh_ext),
            "ic_ext": round(r.ic_ext, 1),
            "t_sala": round(r.t_in, 1),
            "rh_sala": round(r.rh_in),
            "ic_sala": round(r.ic_in, 1),
            "ibutg_sala": round(r.ibutg_in, 1),
            "faixa": Faixa(int(r.faixa)).rotulo,
            "aula": bool(a),
        }
        for (ts, r), a in zip(df.iterrows(), aula)
    ]


def _br(v: float, sinal: bool = True) -> str:
    return (f"{v:+.1f}" if sinal else f"{v:.1f}").replace(".", ",")


def _decidir_aviso(dias: list[ResumoDia]) -> tuple[bool, str]:
    """Aviso quando a previsão indica Alerta ou pior em 2 dias letivos seguidos."""
    letivos = [d for d in dias if d.previsao and d.dia_letivo]
    graves = {Faixa.ALERTA.rotulo, Faixa.PERIGO.rotulo}
    for a, b in zip(letivos, letivos[1:]):
        if a.faixa_sala in graves and b.faixa_sala in graves:
            return True, (
                f"Faixa {a.faixa_sala} em {a.data[8:10]}/{a.data[5:7]} e "
                f"{b.faixa_sala} em {b.data[8:10]}/{b.data[5:7]} (dois dias letivos seguidos)."
            )
    return False, "Sem dois dias letivos seguidos em Alerta ou Perigo na previsão."


def formatar_resumo(r: ResultadoEscola) -> str:
    linhas = [
        f"--- Termômetro das Escolas: {r.escola.nome} ---",
        f"Telhado: {r.escola.tipo_telhado} | Gerado em {r.gerado_em}",
        f"{'Data':<11}{'NC rua*':>8}{'IC rua':>8}{'T sala':>8}{'IC sala':>9}  Faixa sala",
    ]
    for d in r.dias:
        if not d.previsao:
            continue
        fmt = lambda v: f"{v:.1f}" if v is not None else "-"  # noqa: E731
        linhas.append(
            f"{d.data:<11}{d.nc_estimado_rua or '-':>8}{d.ic_ext_max:>8.1f}"
            f"{fmt(d.t_sala_max_aula):>8}{fmt(d.ic_sala_max_aula):>9}  {d.faixa_sala}"
        )
    linhas += [
        f"Aviso às escolas: {'SIM' if r.aviso_emitido else 'não'} ({r.motivo_aviso})",
        "* estimativa regionalizada, não é o nível oficial do COR.",
        r.aviso_nao_oficial,
    ]
    return "\n".join(linhas)


def main() -> None:
    p = argparse.ArgumentParser(description="Previsão de 72h do Termômetro das Escolas")
    # Exemplo padrão: Zona Norte (Madureira/Irajá)
    p.add_argument("--nome", default="Escola exemplo - Madureira")
    p.add_argument("--lat", type=float, default=-22.8431)
    p.add_argument("--lon", type=float, default=-43.3358)
    p.add_argument("--telhado", choices=list(DELTA_TELHADO_C), default="fibrocimento_sem_forro")
    p.add_argument("--climatizada", action="store_true", help="ar-condicionado funcionando")
    p.add_argument("--json", action="store_true", help="saída em JSON")
    a = p.parse_args()

    escola = Escola(a.nome, a.lat, a.lon, a.telhado, a.climatizada)
    resultado = avaliar_escola(escola, buscar_previsao(a.lat, a.lon))
    if a.json:
        print(json.dumps(resultado.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(formatar_resumo(resultado))


if __name__ == "__main__":
    main()

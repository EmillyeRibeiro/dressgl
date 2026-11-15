"""Hospedeiro medido do AgroView-SC (Passo B2).

Cumpre dressgl.hospedeiro.Hospedeiro (D40): no quadro q recebe o plano de
q-1, monta a lista de Passo (D44, D45, D47), desenha com decimação por hz
(D43) e devolve as leituras de q. frame_budget é o custo do próprio quadro,
sem média (D46). No relógio por carga, o custo é Σ carga × coeficiente do
passo, com coeficientes calibrados por tools/calibrar_relogio.py (D48).
As entradas (drone.battery, terrain.below) ainda vêm do cenário; no B3
passam a vir do CoppeliaSim.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from time import perf_counter
from typing import Any

from dressgl.motor import Plano
from dressgl.simulador import (
    CRONOMETRO, MODELO_PADRAO, PLANO_VAZIO, ErroCenario, _ler_toml, configuracao,
)

from .ordem import desenha, ordem_passos
from .render import Passo, Quadro, Renderizador

# (altura, largura) com scale = 1.0. FPV menor que HD: a renderização é em CPU (D42).
RESOLUCOES = {"FPV": (180, 320), "MAP": (128, 128), "AGRO": (96, 96)}


def _validar_coeficientes(coef: Any) -> float | dict[str, float]:
    """Número único (compatibilidade) ou um coeficiente por nome de passo (D48)."""
    if coef is None or isinstance(coef, bool):
        raise ValueError("relogio='carga' exige ms_por_carga (D42, D48)")
    if isinstance(coef, (int, float)):
        if coef <= 0:
            raise ValueError("ms_por_carga deve ser > 0 (D42)")
        return float(coef)
    if isinstance(coef, Mapping):
        if not coef:
            raise ValueError("ms_por_carga vazio (D48)")
        ruins = sorted(str(k) for k, v in coef.items()
                       if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0)
        if ruins:
            raise ValueError(f"coeficientes não positivos: {ruins} (D48)")
        return {str(k): float(v) for k, v in coef.items()}
    raise ValueError(f"ms_por_carga deve ser número ou mapeamento: {type(coef).__name__}")


class HospedeiroAgroView:
    def __init__(self, cenario, modelo_toml=MODELO_PADRAO, *, relogio: str = "tempo",
                 ms_por_carga: float | Mapping[str, float] | None = None,
                 semente: int = 0,
                 resolucoes: Mapping[str, tuple[int, int]] | None = None,
                 instancias_base: int = 200,
                 renderizador: Renderizador | None = None) -> None:
        """relogio = "tempo": frame_budget medido com perf_counter (medições).
        relogio = "carga": frame_budget = Σ carga × ms_por_carga[passo],
        determinístico (testes, D42, D48). Aceita também um número único,
        aplicado a todos os passos (compatibilidade)."""
        if relogio not in ("tempo", "carga"):
            raise ValueError(f"relogio deve ser 'tempo' ou 'carga': {relogio}")
        coef = _validar_coeficientes(ms_por_carga) if relogio == "carga" else ms_por_carga
        m = _ler_toml(modelo_toml)
        self.cenario = cenario
        self.superficies = m["superficies"]
        self.telemetria = m["telemetria"]
        self.passos_padrao = list(m["custo"]["passos_padrao"])
        self.inst_por_passo = {d["passo"]: n for n, d in m.get("instancias", {}).items()}
        self.resolucoes = {**RESOLUCOES, **(resolucoes or {})}
        faltam = set(self.superficies) - set(self.resolucoes)
        if faltam:
            raise ErroCenario(f"superfícies sem resolução: {sorted(faltam)}")
        for k, s in self.telemetria.items():
            if "instrumento" in s and s["instrumento"] != CRONOMETRO:
                raise ErroCenario(f"instrumento sem medição: {s['instrumento']} ({k})")
        self.relogio = relogio
        self.ms_por_carga = coef
        self.instancias_base = instancias_base
        self.render = renderizador or Renderizador(semente)
        self.ultimo: Quadro | None = None   # para a GUI e para depuração

    # ---- relógio por carga (D42, D48) -----------------------------------

    def _tempo_por_carga(self, execucoes: Iterable[Any]) -> float:
        execucoes = list(execucoes)
        coef = self.ms_por_carga
        if isinstance(coef, float):                       # número único (compatibilidade)
            return sum(e.carga for e in execucoes) * coef
        faltando = {e.nome for e in execucoes} - coef.keys()
        if faltando:
            raise ValueError(f"sem coeficiente de calibração para: {sorted(faltando)} (D48)")
        return sum(e.carga * coef[e.nome] for e in execucoes)

    # ---- montagem da lista de passos ------------------------------------

    def _dim(self, sup: str, conf: dict, plano: Plano) -> tuple[int, int]:
        h, w = self.resolucoes[sup]
        e = conf.get(f"view:{sup}.scale", plano.escalas.get(("resolution", sup), 1.0))
        return max(1, round(h * e)), max(1, round(w * e))

    def _visivel(self, sup: str, quadro: int, conf: dict) -> bool:
        if sup not in self.superficies:
            return False
        if conf.get(f"view:{sup}.enabled", True) is False:
            return False
        hz = conf.get(f"view:{sup}.hz")
        return hz is None or desenha(quadro, hz)          # D43

    def _passo_fpv(self, nome: str, h: int, w: int, plano: Plano) -> Passo:
        if nome in self.inst_por_passo:                    # D23: SCALE instances
            f = plano.escalas.get(("instances", self.inst_por_passo[nome]), 1.0)
            return Passo(nome, "FPV", h, w, instancias=round(self.instancias_base * f))
        if nome == "SuitabilityPass":                      # D47
            return Passo(nome, "FPV", h, w, sobrepor=True)
        return Passo(nome, "FPV", h, w)

    def passos(self, quadro: int, plano: Plano) -> list[Passo]:
        conf = configuracao(self.superficies, plano)
        ordem = ordem_passos(self.passos_padrao, plano.supressoes, plano.injecoes)
        lista: list[Passo] = []
        if self._visivel("FPV", quadro, conf):
            h, w = self._dim("FPV", conf, plano)
            lista += [self._passo_fpv(n, h, w, plano) for n in ordem]
        if self._visivel("MAP", quadro, conf):             # D45
            h, w = self._dim("MAP", conf, plano)
            lista.append(Passo("TerrainPass", "MAP", h, w))
            if conf.get("view:MAP.mode") == "SUITABILITY":
                lista.append(Passo("SuitabilityPass", "MAP", h, w, sobrepor=True))
        if self._visivel("AGRO", quadro, conf):            # D45
            h, w = self._dim("AGRO", conf, plano)
            lista.append(Passo("SuitabilityPass", "AGRO", h, w))
        return lista

    # ---- protocolo Hospedeiro (D40) -------------------------------------

    def leituras(self, quadro: int, plano: Plano = PLANO_VAZIO) -> dict[str, Any]:
        l = dict(self.cenario.entradas[quadro])
        lista = self.passos(quadro, plano)
        t0 = perf_counter()
        q = self.render.quadro(lista)
        dt = (perf_counter() - t0) * 1000.0                # cronômetro de quadro (D46)
        self.ultimo = q
        ms = dt if self.relogio == "tempo" else self._tempo_por_carga(q.execucoes)
        for chave, spec in self.telemetria.items():
            if spec.get("instrumento") == CRONOMETRO:
                l[chave] = ms
        l.update(configuracao(self.superficies, plano))
        return l
    
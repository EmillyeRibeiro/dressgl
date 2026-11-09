"""Hospedeiro simulado da DRESS-GL (P7).

Substitui o AgroView-SC nos experimentos: lê um cenário determinístico
(D28), recebe o plano do motor e produz as leituras do quadro seguinte com
um custo de quadro MODELADO, não medido (D29). Views seguem D32.

Uso: python -m dressgl.simulador examples\\safe_setdown.dgl examples\\cenarios\\listagem3.toml
"""

from __future__ import annotations

import argparse
import random
import tomllib
from dataclasses import dataclass
from pathlib import Path

from . import trace
from .hospedeiro import Hospedeiro
from .interpretador import compilar_programa
from .modelo import MODELO_PADRAO, carregar
from .motor import Motor, Plano, compor

PLANO_VAZIO, _ = compor(())
CRONOMETRO = "cronometro_quadro"


class ErroCenario(Exception):
    """Cenário ou seção [custo] inconsistente com o modelo."""


def _ler_toml(caminho):
    with open(caminho, "rb") as f:
        return tomllib.load(f)


def _entradas(telemetria):
    """Chaves que o cenário fornece: nem instrumento, nem campo escalar."""
    return {k: s for k, s in telemetria.items()
            if "instrumento" not in s and not s.get("campo_escalar")}


def padrao(spec):
    """D32: valores -> maior; enum -> primeiro; bool -> True."""
    if "valores" in spec:
        return max(spec["valores"])
    if "enum" in spec:
        return spec["enum"][0]
    if spec.get("tipo") == "bool":
        return True
    raise ErroCenario(f"atributo sem valor padrão: {spec}")


@dataclass(frozen=True)
class Cenario:
    nome: str
    quadros: int
    entradas: tuple          # por quadro: {chave de telemetria: valor}
    semente: int = 0
    ruido_ms: float = 0.0


def _valor(v, q, ini, fim):
    if isinstance(v, dict):                       # rampa linear {de, ate}
        if fim == ini:
            return float(v["de"])
        return v["de"] + (v["ate"] - v["de"]) * (q - ini) / (fim - ini)
    return v


def carregar_cenario(caminho, modelo_toml=MODELO_PADRAO) -> Cenario:
    caminho = Path(caminho)
    dados = _ler_toml(caminho)
    esperadas = _entradas(_ler_toml(modelo_toml)["telemetria"])
    n = dados["quadros"]
    por_quadro = [{} for _ in range(n)]
    for i, t in enumerate(dados.get("trechos", ()), 1):
        ini, fim = t["inicio"], t["fim"]
        if not 0 <= ini <= fim < n:
            raise ErroCenario(f"trecho {i}: [{ini}, {fim}] fora de 0..{n - 1}")
        for chave, v in t.items():
            if chave in ("inicio", "fim"):
                continue
            if chave not in esperadas:
                raise ErroCenario(f"trecho {i}: '{chave}' não é entrada de telemetria do modelo")
            for q in range(ini, fim + 1):
                por_quadro[q][chave] = _valor(v, q, ini, fim)
    for q, e in enumerate(por_quadro):
        for chave, spec in esperadas.items():
            if chave not in e:
                raise ErroCenario(f"quadro {q}: falta '{chave}'")
            v = e[chave]
            if "enum" in spec and v not in spec["enum"]:
                raise ErroCenario(f"quadro {q}: '{chave}' = {v!r} fora de {spec['enum']}")
            if ("min" in spec and v < spec["min"]) or ("max" in spec and v > spec["max"]):
                raise ErroCenario(f"quadro {q}: '{chave}' = {v} fora de [{spec.get('min')}, {spec.get('max')}]")
    return Cenario(dados.get("nome", caminho.stem), n, tuple(por_quadro),
                   dados.get("semente", 0), float(dados.get("ruido_ms", 0.0)))


class HospedeiroSimulado:
    def __init__(self, cenario: Cenario, modelo_toml=MODELO_PADRAO):
        m = _ler_toml(modelo_toml)
        self.cenario = cenario
        self.superficies = m["superficies"]
        self.telemetria = m["telemetria"]
        self.instancias = {n: d["passo"] for n, d in m.get("instancias", {}).items()}
        if "custo" not in m:
            raise ErroCenario("modelo sem seção [custo] (D29)")
        self.param = c = m["custo"]
        nomes = set(m["passos"]["nomes"])
        if (nomes - set(c["passos"]) or not set(c["passos_padrao"]) <= nomes
                or not set(c["superficies"]) <= set(self.superficies)):
            raise ErroCenario("[custo] inconsistente com [passos]/[superficies]")
        for k, s in self.telemetria.items():
            if "instrumento" in s and s["instrumento"] != CRONOMETRO:
                raise ErroCenario(f"instrumento sem simulação: {s['instrumento']} ({k})")

    def configuracao(self, plano: Plano) -> dict:
        """'view:SUP.attr' -> valor em vigor (D21, D23, D32)."""
        conf = {}
        for sup, d in self.superficies.items():
            for attr, spec in d.get("atributos", {}).items():
                v = plano.sets.get((sup, attr), padrao(spec))
                if attr == "scale":
                    v *= plano.escalas.get(("resolution", sup), 1.0)
                conf[f"view:{sup}.{attr}"] = v
        return conf

    def custo_ms(self, plano: Plano) -> float:
        """D29 (modelado)."""
        c, conf = self.param, self.configuracao(plano)
        executados = ((set(c["passos_padrao"]) - plano.supressoes)
                      | {inj.passo for inj in plano.injecoes})
        fracao = {passo: plano.escalas.get(("instances", nome), 1.0)
                  for nome, passo in self.instancias.items()}
        total = c["base_ms"] + sum(c["passos"][p] * fracao.get(p, 1.0) for p in executados)
        for sup, ms in c["superficies"].items():
            if conf.get(f"view:{sup}.enabled", True) is False:
                continue
            escala = conf.get(f"view:{sup}.scale", plano.escalas.get(("resolution", sup), 1.0))
            atualiz = 1.0
            if f"view:{sup}.hz" in conf:
                atualiz = conf[f"view:{sup}.hz"] / padrao(self.superficies[sup]["atributos"]["hz"])
            total += ms * escala ** 2 * atualiz
        return total

    def leituras(self, quadro: int, plano: Plano = PLANO_VAZIO) -> dict:
        """Leituras do quadro `quadro`, que medem o efeito de `plano`,
        o plano do quadro anterior (D25, D29)."""
        l = dict(self.cenario.entradas[quadro])
        for chave, spec in self.telemetria.items():
            if spec.get("instrumento") == CRONOMETRO:
                ms = self.custo_ms(plano)
                if self.cenario.ruido_ms:
                    rng = random.Random(f"{self.cenario.semente}:{quadro}")
                    ms = max(0.0, ms + rng.gauss(0.0, self.cenario.ruido_ms))
                l[chave] = ms
        l.update(self.configuracao(plano))
        return l


def executar(programa, cenario: Cenario, hospedeiro: Hospedeiro | None = None) -> list[dict]:
    """Roda o cenário inteiro e devolve as linhas do trace (D30)."""
    host = hospedeiro or HospedeiroSimulado(cenario)
    motor = Motor(programa)
    plano, linhas = PLANO_VAZIO, []
    for q in range(cenario.quadros):
        leit = host.leituras(q, plano)
        condicoes = {r.nome: bool(r.predicado(leit)) for r in motor.regras}
        reg = motor.passo(leit)
        linhas.append(trace.linha(reg, leit, condicoes))
        plano = reg.plano
    return linhas


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m dressgl.simulador")
    p.add_argument("programa", type=Path)
    p.add_argument("cenario", type=Path)
    p.add_argument("--saida", type=Path, default=Path("results"))
    a = p.parse_args(argv)
    programa = compilar_programa(a.programa.read_text(encoding="utf-8-sig"),
                                 carregar(MODELO_PADRAO))
    cenario = carregar_cenario(a.cenario)
    linhas = executar(programa, cenario)
    destino = a.saida / f"trace_{cenario.nome}.jsonl"
    trace.gravar(destino, linhas)
    orc = programa.politica.budget_ms if programa.politica else None   # conferir o nome
    for k, v in trace.metricas(linhas, orc).items():
        print(f"{k:24} {v}")
    print(f"trace: {destino}")


if __name__ == "__main__":
    main()
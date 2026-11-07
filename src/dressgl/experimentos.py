"""Matriz de experimentos programa × cenário (Passo 5; D33–D37).

Uso: python -m dressgl.experimentos [--saida results]
Gera results/metricas.csv, results/metricas.md e um trace por combinação.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
from pathlib import Path

from . import trace
from .interpretador import ProgramaExecutavel, compilar_programa
from .modelo import MODELO_PADRAO, carregar
from .simulador import carregar_cenario, executar

EX = MODELO_PADRAO.parent.parent / "examples"


def sem_cooldown(p: ProgramaExecutavel) -> ProgramaExecutavel:
    """Ablação D35: mesmo fonte, cooldown_frames = 0."""
    return ProgramaExecutavel(dataclasses.replace(p.politica, cooldown_frames=0), p.regras)


PROGRAMAS = {
    "dsl":              (EX / "safe_setdown.dgl", None),
    "dsl_sem_cooldown": (EX / "safe_setdown.dgl", sem_cooldown),
    "baseline":         (EX / "baseline_sem_compensacao.dgl", None),
    "multiplas":        (EX / "multiplas_regras.dgl", None),
}
CENARIOS = ("listagem3", "listagem3_ruido", "oscilacao")
COLUNAS = ("programa", "cenario", "quadros", "acima_orcamento_pct", "pior_quadro_ms",
           "ativacoes", "desativacoes", "retencoes", "violacoes_assert", "conflitos",
           "atraso_ativacao_medio", "atraso_ativacao_max")


def carregar_programa(nome, modelo=None) -> ProgramaExecutavel:
    arquivo, transformar = PROGRAMAS[nome]
    p = compilar_programa(arquivo.read_text(encoding="utf-8-sig"),
                          modelo or carregar(MODELO_PADRAO))
    return transformar(p) if transformar else p


def rodar(programas=tuple(PROGRAMAS), cenarios=CENARIOS, saida=None) -> list[dict]:
    modelo = carregar(MODELO_PADRAO)
    tabela = []
    for nc in cenarios:
        cenario = carregar_cenario(EX / "cenarios" / f"{nc}.toml")
        for np_ in programas:
            programa = carregar_programa(np_, modelo)
            linhas = executar(programa, cenario)
            if saida is not None:
                trace.gravar(Path(saida) / f"trace_{np_}__{nc}.jsonl", linhas)
            orc = programa.politica.budget_ms if programa.politica else None
            tabela.append({"programa": np_, "cenario": nc, **trace.metricas(linhas, orc)})
    return tabela


def _fmt(v):
    if v is None:
        return "-"
    return f"{v:.2f}" if isinstance(v, float) else str(v)


def markdown(tabela) -> str:
    linhas = ["| " + " | ".join(COLUNAS) + " |", "|" + "---|" * len(COLUNAS)]
    linhas += ["| " + " | ".join(_fmt(l.get(c)) for c in COLUNAS) + " |" for l in tabela]
    return "\n".join(linhas)


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m dressgl.experimentos")
    p.add_argument("--saida", type=Path, default=Path("results"))
    a = p.parse_args(argv)
    tabela = rodar(saida=a.saida)
    a.saida.mkdir(parents=True, exist_ok=True)
    with open(a.saida / "metricas.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, COLUNAS, restval="", extrasaction="ignore")
        w.writeheader()
        w.writerows(tabela)
    md = markdown(tabela)
    (a.saida / "metricas.md").write_text(md + "\n", encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
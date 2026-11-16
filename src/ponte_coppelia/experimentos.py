"""Matriz programa × gravação × hospedeiro sobre voos gravados (C4; D53, D54).

Uso: python -m ponte_coppelia.experimentos [--gravacoes results] [--saida results]
Não precisa do CoppeliaSim: usa as gravações de tools/rodar_coppelia.py.
Os experimentos da v1.0 (dressgl.experimentos) não mudam.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from dressgl import trace
from dressgl.experimentos import PROGRAMAS, carregar_programa
from dressgl.modelo import MODELO_PADRAO, carregar
from dressgl.simulador import executar

from .fonte import carregar_gravacao

RAIZ = MODELO_PADRAO.parent.parent
CALIBRACAO = RAIZ / "results" / "calibracao.toml"
HOSPEDEIROS = ("simulado", "agroview")
COLUNAS = ("programa", "gravacao", "hospedeiro", "quadros", "acima_orcamento_pct",
           "pior_quadro_ms", "ativacoes", "desativacoes", "retencoes", "violacoes_assert",
           "conflitos", "atraso_ativacao_medio", "atraso_ativacao_max",
           "atraso_fisico_quadros")


def _hospedeiro(nome, cenario):
    if nome == "simulado":
        return None                                   # executar cria o HospedeiroSimulado
    from agroview.calibracao import carregar_calibracao   # extra [render]
    from agroview.hospedeiro import HospedeiroAgroView
    return HospedeiroAgroView(cenario, relogio="carga",
                              ms_por_carga=carregar_calibracao(CALIBRACAO))


def atraso_fisico(caminho, solo="WATER") -> int | None:
    """D53: quadros entre o alvo e o drone entrarem na zona `solo`.
    None se a gravação não tem o alvo ou se não houve entrada."""
    with open(caminho, encoding="utf-8") as f:
        regs = [json.loads(s) for s in f if s.strip()]
    if not regs or "solo_alvo" not in regs[0]:
        return None
    qa = next((r["quadro"] for r in regs if r["solo_alvo"] == solo), None)
    qd = next((r["quadro"] for r in regs if r["terrain.below"] == solo), None)
    return None if qa is None or qd is None else qd - qa


def gravacoes_em(pasta) -> list[Path]:
    return sorted(Path(pasta).glob("gravacao_*.jsonl"))


def rodar(gravacoes, programas=tuple(PROGRAMAS), hospedeiros=HOSPEDEIROS,
          saida=None) -> list[dict]:
    modelo = carregar(MODELO_PADRAO)
    progs = {n: carregar_programa(n, modelo) for n in programas}
    tabela = []
    for g in gravacoes:
        cenario = carregar_gravacao(g)
        af = atraso_fisico(g)
        for nh in hospedeiros:
            for np_, prog in progs.items():
                linhas = executar(prog, cenario, _hospedeiro(nh, cenario))
                if saida is not None:
                    trace.gravar(Path(saida) / f"trace_coppelia_{nh}__{np_}__{cenario.nome}.jsonl",
                                 linhas)
                orc = prog.politica.budget_ms if prog.politica else None
                tabela.append({"programa": np_, "gravacao": cenario.nome, "hospedeiro": nh,
                               **trace.metricas(linhas, orc), "atraso_fisico_quadros": af})
    return tabela


def _fmt(v):
    if v is None:
        return "-"
    return f"{v:.2f}" if isinstance(v, float) else str(v)


def markdown(tabela) -> str:
    linhas = ["| " + " | ".join(COLUNAS) + " |", "|" + "---|" * len(COLUNAS)]
    linhas += ["| " + " | ".join(_fmt(l.get(c)) for c in COLUNAS) + " |" for l in tabela]
    return "\n".join(linhas)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m ponte_coppelia.experimentos")
    p.add_argument("--gravacoes", type=Path, default=RAIZ / "results")
    p.add_argument("--saida", type=Path, default=Path("results"))
    p.add_argument("--hospedeiros", nargs="+", choices=HOSPEDEIROS, default=list(HOSPEDEIROS))
    a = p.parse_args(argv)
    gravs = gravacoes_em(a.gravacoes)
    if not gravs:
        raise SystemExit(f"nenhuma gravacao_*.jsonl em {a.gravacoes}; rode tools\\rodar_coppelia.py")
    tabela = rodar(gravs, hospedeiros=tuple(a.hospedeiros), saida=a.saida)
    a.saida.mkdir(parents=True, exist_ok=True)
    with open(a.saida / "metricas_coppelia.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, COLUNAS, restval="", extrasaction="ignore")
        w.writeheader()
        w.writerows(tabela)
    md = markdown(tabela)
    (a.saida / "metricas_coppelia.md").write_text(md + "\n", encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
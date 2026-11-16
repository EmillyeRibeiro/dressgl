"""Roda uma política com entradas do CoppeliaSim (D49-D52).

Uso: python tools\\rodar_coppelia.py examples\\safe_setdown.dgl examples\\missoes\\pouso_agua.toml [--hospedeiro simulado|agroview]
Exige o CoppeliaSim aberto, com o Quadcopter na cena e a simulação parada.
"""
import argparse
from pathlib import Path

from dressgl import trace
from dressgl.interpretador import compilar_programa
from dressgl.modelo import MODELO_PADRAO, carregar
from dressgl.simulador import executar
from ponte_coppelia.cliente import SessaoZmq
from ponte_coppelia.fonte import CenarioCoppelia, EntradasCoppelia, gravar
from ponte_coppelia.missao import carregar_missao


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("programa", type=Path)
    p.add_argument("missao", type=Path)
    p.add_argument("--hospedeiro", choices=("simulado", "agroview"), default="simulado")
    p.add_argument("--saida", type=Path, default=Path("results"))
    a = p.parse_args(argv)

    missao = carregar_missao(a.missao)
    programa = compilar_programa(a.programa.read_text(encoding="utf-8-sig"),
                                 carregar(MODELO_PADRAO))
    with SessaoZmq() as sessao:
        entradas = EntradasCoppelia(sessao, missao)
        cenario = CenarioCoppelia(missao.nome, missao.quadros, entradas)
        host = None                                   # None = HospedeiroSimulado
        if a.hospedeiro == "agroview":
            from agroview.calibracao import carregar_calibracao
            from agroview.hospedeiro import HospedeiroAgroView
            host = HospedeiroAgroView(cenario, relogio="carga",
                                      ms_por_carga=carregar_calibracao())
        linhas = executar(programa, cenario, host)

    gravar(a.saida / f"gravacao_{missao.nome}.jsonl", entradas.registros)
    destino = a.saida / f"trace_coppelia_{a.hospedeiro}__{missao.nome}.jsonl"
    trace.gravar(destino, linhas)
    orc = programa.politica.budget_ms if programa.politica else None
    for k, v in trace.metricas(linhas, orc).items():
        print(f"{k:24} {v}")
    print(f"trace: {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
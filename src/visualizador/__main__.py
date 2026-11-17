import argparse
import tkinter as tk

from .fonte import (GRAVACOES, HOSPEDEIROS, MISSOES, PROGRAMAS, caminho_trace,
                    carregar_missao, quadros)
from .janela import Janela


def main():
    ap = argparse.ArgumentParser(prog="python -m visualizador")
    ap.add_argument("--gravacao", default="borda_agua", choices=GRAVACOES)
    ap.add_argument("--programa", default="dsl", choices=PROGRAMAS)
    ap.add_argument("--hospedeiro", default="agroview", choices=HOSPEDEIROS)
    ap.add_argument("--erro-pos", type=float, default=0.0,
                    help="ainda não suportado: exige o laço ao vivo (D62)")
    ap.add_argument("--semente", type=int, default=0)
    a = ap.parse_args()

    if a.erro_pos:
        raise SystemExit("--erro-pos > 0 ainda não é suportado: os traces gravados são sem ruído (D62)")
    try:
        missao = carregar_missao(a.gravacao)
    except FileNotFoundError:
        raise SystemExit(f"missão não encontrada: {MISSOES / (a.gravacao + '.toml')}")
    trace = caminho_trace(a.gravacao, a.programa, a.hospedeiro)
    if not trace.exists():
        raise SystemExit(f"trace não encontrado: {trace}")

    raiz = tk.Tk()
    j = Janela(raiz,
               lambda: quadros(a.gravacao, a.programa, a.hospedeiro),
               int(missao["quadros"]),
               f"DRESS-GL · {a.gravacao} · {a.programa} · {a.hospedeiro}",
               zonas=missao.get("zonas", ()),
               waypoints=missao.get("waypoints", ()))
    raiz.protocol("WM_DELETE_WINDOW", j.fechar)
    raiz.mainloop()


if __name__ == "__main__":
    main()
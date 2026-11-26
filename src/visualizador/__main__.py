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
    ap.add_argument("--sem-imagens", action="store_true",
                    help="não reconstrói as superfícies do AgroView")
    ap.add_argument("--coppelia", action="store_true",
                    help="reproduz a gravação no CoppeliaSim (simulação parada) em vez da janela Tk")
    ap.add_argument("--fps", type=float, default=30.0,
                    help="quadros por segundo do replay no CoppeliaSim")
    ap.add_argument("--vista-topo", action="store_true",
                    help="(com --coppelia) câmera principal acima do campo")
    ap.add_argument("--duas-vistas", action="store_true",
                    help="(com --coppelia) 3D panorâmica na principal + topo em janela flutuante")
    ap.add_argument("--seguir-drone", action="store_true",
                    help="(com --coppelia) câmera 3D principal acompanha o drone")
    ap.add_argument("--ortografica", action="store_true",
                    help="(com --vista-topo ou --duas-vistas) topo sem perspectiva")
    ap.add_argument("--manter-rastro", action="store_true",
                    help="(com --coppelia) não apaga rastro nem vistas no fim")
    ap.add_argument("--restaurar-cena", action="store_true",
                    help="(com --coppelia) limpa restos e devolve câmera e drone ao original")
    ap.add_argument("--altura-camera", type=float, default=None,
                    help="altura da câmera de topo em m (padrão 9 na principal, 8 na janela)")
    a = ap.parse_args()

    so_coppelia = (a.vista_topo, a.duas_vistas, a.seguir_drone, a.ortografica,
                   a.manter_rastro, a.restaurar_cena, a.altura_camera is not None)
    if any(so_coppelia) and not a.coppelia:
        ap.error("essas opções só valem junto com --coppelia")
    if a.vista_topo and (a.duas_vistas or a.seguir_drone):
        ap.error("--vista-topo não combina com --duas-vistas/--seguir-drone "
                 "(nesse modo o topo já fica na janela flutuante)")
    if a.ortografica and not (a.vista_topo or a.duas_vistas):
        ap.error("--ortografica precisa de --vista-topo ou --duas-vistas")

    if a.coppelia and a.restaurar_cena:
        from .coppelia import restaurar_cena
        restaurar_cena()
        return

    if a.erro_pos:
        raise SystemExit("--erro-pos > 0 ainda não é suportado: os traces gravados são sem ruído (D62)")
    try:
        missao = carregar_missao(a.gravacao)
    except FileNotFoundError:
        raise SystemExit(f"missão não encontrada: {MISSOES / (a.gravacao + '.toml')}")
    trace = caminho_trace(a.gravacao, a.programa, a.hospedeiro)
    if not trace.exists():
        raise SystemExit(f"trace não encontrado: {trace}")

    if a.coppelia:
        from .coppelia import reproduzir     # importa o cliente ZMQ só quando precisa
        reproduzir(lambda: quadros(a.gravacao, a.programa, a.hospedeiro, imagens=False),
                   zonas=missao.get("zonas", ()), fps=a.fps, vista_topo=a.vista_topo,
                   manter_rastro=a.manter_rastro, altura_camera=a.altura_camera,
                   duas_vistas=a.duas_vistas, seguir_drone=a.seguir_drone,
                   ortografica=a.ortografica)
        return

    raiz = tk.Tk()
    j = Janela(raiz,
               lambda: quadros(a.gravacao, a.programa, a.hospedeiro,
                               imagens=not a.sem_imagens),
               int(missao["quadros"]),
               f"DRESS-GL · {a.gravacao} · {a.programa} · {a.hospedeiro}",
               zonas=missao.get("zonas", ()),
               waypoints=missao.get("waypoints", ()))
    raiz.protocol("WM_DELETE_WINDOW", j.fechar)
    try:
        raiz.mainloop()
    except KeyboardInterrupt:        # Ctrl+C no console: fecha sem traceback
        j.fechar()


if __name__ == "__main__":
    main()
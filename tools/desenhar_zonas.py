"""Desenha as zonas de uma missão como planos coloridos na cena aberta (D55).

Uso: python tools\\desenhar_zonas.py examples\\missoes\\pouso_agua.toml
Com a simulação PARADA. Os planos são estáticos e não respondable: só visuais.
Rodar de novo substitui os planos anteriores.
"""
import argparse

from coppeliasim_zmqremoteapi_client import RemoteAPIClient

from ponte_coppelia.missao import carregar_missao

CORES = {"WATER": [0.15, 0.35, 0.75], "STANDING_CROP": [0.20, 0.60, 0.20],
         "BARE_SOIL": [0.55, 0.42, 0.28]}


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("missao")
    m = carregar_missao(p.parse_args(argv).missao)
    sim = RemoteAPIClient().require("sim")
    if sim.getSimulationState() != sim.simulation_stopped:
        raise SystemExit("pare a simulação antes de desenhar as zonas")
    for i, z in enumerate(m.zonas):
        nome = f"zona_{i}_{z.solo.lower()}"
        try:
            sim.removeObjects([sim.getObject("/" + nome)])
        except Exception:
            pass                                    # ainda não existia
        h = sim.createPrimitiveShape(sim.primitiveshape_plane,
                                     [z.x[1] - z.x[0], z.y[1] - z.y[0], 0])
        # A zona seguinte fica 1 mm acima: a última zona vence, como em solo_em.
        sim.setObjectPosition(h, [(z.x[0] + z.x[1]) / 2, (z.y[0] + z.y[1]) / 2,
                                  0.001 * (i + 1)], sim.handle_world)
        sim.setShapeColor(h, None, sim.colorcomponent_ambient_diffuse, CORES[z.solo])
        sim.setObjectInt32Param(h, sim.shapeintparam_static, 1)
        sim.setObjectInt32Param(h, sim.shapeintparam_respondable, 0)
        sim.setObjectAlias(h, nome)
        print(f"{nome}: x={z.x} y={z.y}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""Calibra o relógio por carga (D48): mediana de ms/carga por passo."""
import statistics
from pathlib import Path
from types import SimpleNamespace as N

from agroview.hospedeiro import HospedeiroAgroView
from dressgl.simulador import PLANO_VAZIO

QUADROS, AQUECIMENTO = 600, 60
SAIDA = Path("results/calibracao.toml")


def main() -> None:
    cenario = N(entradas=[{"drone.battery": 50.0, "terrain.below": "BARE_SOIL"}] * QUADROS)
    h = HospedeiroAgroView(cenario)
    amostras: dict[str, list[float]] = {}
    for q in range(QUADROS):
        h.leituras(q, PLANO_VAZIO)
        if q < AQUECIMENTO:          # descarta caches frios e alocações iniciais
            continue
        for e in h.ultimo.execucoes:
            amostras.setdefault(e.nome, []).append(e.tempo_ms / e.carga)

    linhas = ["# Gerado por tools/calibrar_relogio.py (D48). ms por unidade de carga.",
              f"# {QUADROS - AQUECIMENTO} quadros medidos; ver results/ambiente.json.",
              "[ms_por_carga]"]
    for nome in sorted(amostras):
        linhas.append(f'"{nome}" = {statistics.median(amostras[nome]):.6e}'
                      f"  # n={len(amostras[nome])}")
    SAIDA.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(SAIDA.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
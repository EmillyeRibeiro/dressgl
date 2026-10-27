"""Marco C0: conexao minima com o CoppeliaSim via ZeroMQ Remote API.

Pre-requisito: CoppeliaSim ABERTO, com qualquer cena carregada.
Baseado no exemplo oficial (manual: ZeroMQ remote API).
Mede separadamente a latencia de cada chamada sim.step() (IPC + passo).
"""
from __future__ import annotations

import statistics
import sys
import time

try:
    from coppeliasim_zmqremoteapi_client import RemoteAPIClient
except ImportError:
    print("Instale: pip install coppeliasim-zmqremoteapi-client")
    sys.exit(2)


def main() -> int:
    print("Conectando ao CoppeliaSim (host/porta padrao do cliente)...")
    client = RemoteAPIClient()
    sim = client.require("sim")
    dt = sim.getSimulationTimeStep()
    print(f"Conectado. Passo de simulacao configurado na cena: {dt * 1000:.1f} ms")

    sim.setStepping(True)
    sim.startSimulation()
    latencias_ms: list[float] = []
    try:
        while (t := sim.getSimulationTime()) < 3.0:
            t0 = time.perf_counter()
            sim.step()
            latencias_ms.append((time.perf_counter() - t0) * 1000.0)
        print(f"Tempo simulado final: {t:.2f} s | passos: {len(latencias_ms)}")
    finally:
        sim.stopSimulation()

    if len(latencias_ms) >= 2:
        ordenadas = sorted(latencias_ms)
        p95 = ordenadas[int(0.95 * (len(ordenadas) - 1))]
        print(f"Latencia de sim.step(): media={statistics.mean(latencias_ms):.2f} ms "
              f"mediana={statistics.median(latencias_ms):.2f} ms p95={p95:.2f} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
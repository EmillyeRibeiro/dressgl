"""Sessão ZMQ síncrona com o CoppeliaSim 4.10 (D49). Único módulo que importa o cliente."""
from __future__ import annotations

from .missao import ErroMissao


class SessaoZmq:
    def __init__(self, host="localhost", porta=23000,
                 drone="/Quadcopter", alvo="/Quadcopter/target"):
        try:
            from coppeliasim_zmqremoteapi_client import RemoteAPIClient
        except ImportError as e:
            raise ErroMissao('instale o extra: pip install -e ".[coppelia]"') from e
        self.client = RemoteAPIClient(host, porta)
        self.sim = self.client.require("sim")
        # Handles obtidos antes de iniciar: continuam válidos mesmo que o
        # script do modelo desanexe o alvo do drone ao iniciar.
        self.h_drone = self.sim.getObject(drone)
        self.h_alvo = self.sim.getObject(alvo)
        self.dt = self.sim.getSimulationTimeStep()

    def __enter__(self):
        if self.sim.getSimulationState() != self.sim.simulation_stopped:
            raise ErroMissao("pare a simulação no CoppeliaSim antes de rodar")
        self.sim.setStepping(True)
        self.sim.startSimulation()
        return self

    def __exit__(self, *exc):
        self.sim.stopSimulation()

    def mover_alvo(self, xyz) -> None:
        self.sim.setObjectPosition(self.h_alvo, list(xyz), self.sim.handle_world)

    def passo(self) -> None:
        self.sim.step()

    def estado(self):
        pos = self.sim.getObjectPosition(self.h_drone, self.sim.handle_world)
        return self.sim.getSimulationTime(), tuple(pos)
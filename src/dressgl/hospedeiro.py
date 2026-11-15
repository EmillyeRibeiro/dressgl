"""Contrato entre o motor e qualquer hospedeiro (D40).

O motor não conhece o hospedeiro (D26, D27). Este protocolo formaliza o que
simulador.executar já usa: no quadro q, o hospedeiro recebe o plano decidido
em q-1, aplica-o e devolve as leituras de q, que medem o efeito desse plano
(D25, D29). HospedeiroSimulado, o adaptador do AgroView-SC e a ponte com o
CoppeliaSim devem cumprir o mesmo contrato.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from .motor import Plano


@runtime_checkable
class Hospedeiro(Protocol):
    def leituras(self, quadro: int, plano: Plano) -> Mapping[str, Any]:
        """Aplica `plano` e devolve as leituras do quadro `quadro`:
        telemetria pela chave do modelo e configuração como 'view:SUP.attr'
        (D21)."""
        ...
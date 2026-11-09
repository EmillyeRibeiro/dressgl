import subprocess
import sys
import tomllib

from dressgl.hospedeiro import Hospedeiro
from dressgl.interpretador import compilar_programa
from dressgl.modelo import MODELO_PADRAO, carregar
from dressgl.simulador import HospedeiroSimulado, carregar_cenario, executar

RAIZ = MODELO_PADRAO.parent.parent
CENARIO = RAIZ / "examples" / "cenarios" / "listagem3.toml"
EXEMPLO = RAIZ / "examples" / "safe_setdown.dgl"


def test_simulado_cumpre_o_protocolo():
    assert isinstance(HospedeiroSimulado(carregar_cenario(CENARIO)), Hospedeiro)


def test_executar_aceita_outro_hospedeiro():
    class Fixo:                       # hospedeiro mínimo: leituras constantes
        def leituras(self, quadro, plano):
            return {"drone.battery": 10.0, "terrain.below": "WATER",
                    "frame_budget": 12.0, "view:FPV.scale": 1.0}
    prog = compilar_programa(EXEMPLO.read_text(encoding="utf-8-sig"), carregar(MODELO_PADRAO))
    linhas = executar(prog, carregar_cenario(CENARIO), Fixo())
    assert isinstance(Fixo(), Hospedeiro)
    assert linhas[0]["ativadas"] == ["SafeSetdownAssist"]
    assert all(l["violacoes"] == [] for l in linhas)


def test_coppelia_e_dependencia_opcional():                     # D39
    with open(RAIZ / "pyproject.toml", "rb") as f:
        proj = tomllib.load(f)["project"]
    assert proj["dependencies"] == []
    assert any("coppeliasim" in d for d in proj["optional-dependencies"]["coppelia"])


def test_nucleo_nao_importa_o_cliente_zmq():                    # D39
    codigo = ("import sys, dressgl.experimentos, dressgl.hospedeiro; "
              "print('coppeliasim_zmqremoteapi_client' in sys.modules)")
    saida = subprocess.run([sys.executable, "-c", codigo],
                           capture_output=True, text=True, check=True).stdout
    assert saida.strip() == "False"
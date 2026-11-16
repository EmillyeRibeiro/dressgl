import pytest

from dressgl.interpretador import compilar_programa
from dressgl.modelo import MODELO_PADRAO, carregar
from dressgl.simulador import executar
from ponte_coppelia.fonte import (CenarioCoppelia, EntradasCoppelia,
                                  carregar_gravacao, gravar)
from ponte_coppelia.missao import ErroMissao, carregar_missao

RAIZ = MODELO_PADRAO.parent.parent
MISSAO = RAIZ / "examples" / "missoes" / "pouso_agua.toml"
EXEMPLO = RAIZ / "examples" / "safe_setdown.dgl"


class SessaoFalsa:
    """O drone 'teleporta' para o alvo: testa a ponte, não a física."""
    def __init__(self, dt=0.05):
        self.dt, self.t, self.alvo, self.passos = dt, 0.0, (0.0, 0.0, 0.0), 0
    def mover_alvo(self, xyz): self.alvo = tuple(xyz)
    def passo(self): self.t += self.dt; self.passos += 1
    def estado(self): return self.t, self.alvo


@pytest.fixture
def missao():
    return carregar_missao(MISSAO)


def rodar_falso(missao):
    ent = EntradasCoppelia(SessaoFalsa(), missao)
    prog = compilar_programa(EXEMPLO.read_text(encoding="utf-8-sig"), carregar(MODELO_PADRAO))
    return ent, executar(prog, CenarioCoppelia(missao.nome, missao.quadros, ent))


def test_um_passo_a_cada_tres_quadros(missao):                 # D50
    s = SessaoFalsa()
    ent = EntradasCoppelia(s, missao)
    for q in range(10):
        ent[q]
    assert s.passos == 3                                         # quadros 3, 6, 9


def test_acesso_fora_de_ordem_e_erro(missao):
    ent = EntradasCoppelia(SessaoFalsa(), missao)
    ent[0]
    with pytest.raises(ErroMissao):
        ent[2]


def test_passo_da_cena_incompativel(missao):
    with pytest.raises(ErroMissao):
        EntradasCoppelia(SessaoFalsa(dt=0.01), missao)


def test_alvo_percorre_waypoints(missao):
    assert missao.alvo_em(0) == missao.waypoints[0]
    assert missao.alvo_em(1e6) == missao.waypoints[-1]


def test_zonas_e_bateria(missao):
    assert missao.solo_em(1.5, 0.0) == "WATER"
    assert missao.solo_em(-2.0, 0.0) == "STANDING_CROP"
    assert missao.bateria_em(10.0) == pytest.approx(18.0)


def test_missao_dispara_a_regra_sobre_agua(missao):
    _, linhas = rodar_falso(missao)
    ativ = [l for l in linhas if l["ativadas"]]
    assert ativ, "a regra deveria disparar"
    l = ativ[0]["leituras"]
    assert l["drone.battery"] < 18 and l["terrain.below"] == "WATER"
    assert any(l["desativadas"] for l in linhas)                # sai da água


def test_gravacao_reproduz_o_trace(missao, tmp_path):            # D52
    ent, ao_vivo = rodar_falso(missao)
    gravar(tmp_path / "gravacao_x.jsonl", ent.registros)
    cen = carregar_gravacao(tmp_path / "gravacao_x.jsonl")
    prog = compilar_programa(EXEMPLO.read_text(encoding="utf-8-sig"), carregar(MODELO_PADRAO))
    assert executar(prog, cen) == ao_vivo


@pytest.mark.parametrize("trecho", ['hz_sim = 7', 'solo = "LAVA"'])
def test_missao_invalida(tmp_path, trecho):
    texto = MISSAO.read_text(encoding="utf-8")
    texto = texto.replace("hz_sim        = 20", trecho) if "hz" in trecho \
        else texto.replace('solo = "WATER"', trecho)
    (tmp_path / "m.toml").write_text(texto, encoding="utf-8")
    with pytest.raises(ErroMissao):
        carregar_missao(tmp_path / "m.toml")
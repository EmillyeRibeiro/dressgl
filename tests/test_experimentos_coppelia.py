import dataclasses
import json

import pytest

from ponte_coppelia import experimentos as ex
from ponte_coppelia.fonte import EntradasCoppelia, gravar
from ponte_coppelia.missao import carregar_missao

MISSOES = ex.RAIZ / "examples" / "missoes"


class SessaoFalsa:
    """O drone 'teleporta' para o alvo: atraso físico zero."""
    def __init__(self, dt=0.05):
        self.dt, self.t, self.alvo = dt, 0.0, (0.0, 0.0, 0.0)
    def mover_alvo(self, xyz): self.alvo = tuple(xyz)
    def passo(self): self.t += self.dt
    def estado(self): return self.t, self.alvo


def gravar_falso(nome, pasta, quadros=None):
    m = carregar_missao(MISSOES / f"{nome}.toml")
    if quadros:
        m = dataclasses.replace(m, quadros=quadros)
    ent = EntradasCoppelia(SessaoFalsa(), m)
    for q in range(m.quadros):
        ent[q]
    caminho = pasta / f"gravacao_{m.nome}.jsonl"
    gravar(caminho, ent.registros)
    return caminho


def test_matriz_pouso_agua_simulado(tmp_path):
    tab = ex.rodar([gravar_falso("pouso_agua", tmp_path)], hospedeiros=("simulado",))
    por = {l["programa"]: l for l in tab}
    assert set(por) == set(ex.PROGRAMAS)
    assert (por["dsl"]["ativacoes"], por["dsl"]["desativacoes"]) == (1, 1)
    assert por["dsl"]["violacoes_assert"] == 0
    assert por["baseline"]["violacoes_assert"] > 0          # injeção sem compensação: 18 ms
    assert por["dsl"]["atraso_fisico_quadros"] == 0          # sessão falsa não tem inércia


def test_borda_agua_alterna_o_solo_com_bateria_baixa():
    m = carregar_missao(MISSOES / "borda_agua.toml")
    assert m.bateria_em(0) < 18 and m.bateria_em(m.quadros / 60) < 18
    solos = [m.solo_em(*m.alvo_em(q / 60)[:2]) for q in range(m.quadros)]
    assert sum(a != b for a, b in zip(solos, solos[1:])) >= 6


def test_borda_agua_ativa_e_desativa_varias_vezes(tmp_path):
    tab = ex.rodar([gravar_falso("borda_agua", tmp_path)], programas=("dsl",),
                   hospedeiros=("simulado",))
    assert tab[0]["ativacoes"] == tab[0]["desativacoes"] >= 3


def test_gravacao_antiga_sem_alvo(tmp_path):
    g = tmp_path / "gravacao_velha.jsonl"
    g.write_text(json.dumps({"quadro": 0, "drone.battery": 50.0,
                             "terrain.below": "WATER"}) + "\n", encoding="utf-8")
    assert ex.atraso_fisico(g) is None


def test_agroview_sobre_gravacao_curta(tmp_path):
    pytest.importorskip("numpy")
    g = gravar_falso("pouso_agua", tmp_path, quadros=30)
    [l] = ex.rodar([g], programas=("dsl",), hospedeiros=("agroview",))
    assert l["pior_quadro_ms"] > 0
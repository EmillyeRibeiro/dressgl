import pytest

from dressgl import experimentos as ex

PADRAO = dict(ativacoes=1, desativacoes=1, retencoes=0, violacoes_assert=0,
              conflitos=0, pior_quadro_ms=15.0, acima_orcamento_pct=0.0)
ESPERADO = {
    ("dsl", "listagem3"): PADRAO,
    ("dsl_sem_cooldown", "listagem3"): PADRAO,
    ("baseline", "listagem3"): {**PADRAO, "violacoes_assert": 40, "pior_quadro_ms": 18.0,
                                "acima_orcamento_pct": 100 * 40 / 300},
    ("multiplas", "listagem3"): {**PADRAO, "ativacoes": 2, "conflitos": 40},
    ("dsl", "oscilacao"): {**PADRAO, "ativacoes": 2, "retencoes": 10,
                           "atraso_ativacao_max": 5, "atraso_ativacao_medio": 2.5},
    ("dsl_sem_cooldown", "oscilacao"): {**PADRAO, "ativacoes": 3, "desativacoes": 2,
                                        "atraso_ativacao_max": 0},
    ("baseline", "oscilacao"): {**PADRAO, "ativacoes": 2, "retencoes": 10,
                                "violacoes_assert": 89, "pior_quadro_ms": 18.0,
                                "acima_orcamento_pct": 100 * 89 / 150},
    ("multiplas", "oscilacao"): {**PADRAO, "ativacoes": 3, "retencoes": 10,
                                 "conflitos": 90, "atraso_ativacao_max": 5},
}


@pytest.fixture(scope="module")
def tabela():
    return {(l["programa"], l["cenario"]): l for l in ex.rodar()}


@pytest.mark.parametrize("chave", list(ESPERADO), ids=lambda k: f"{k[0]}-{k[1]}")
def test_matriz(tabela, chave):
    obtido = tabela[chave]
    for k, v in ESPERADO[chave].items():
        assert obtido[k] == pytest.approx(v), k


def test_ruido_preserva_decisoes(tabela):
    for p in ex.PROGRAMAS:
        a, b = tabela[(p, "listagem3")], tabela[(p, "listagem3_ruido")]
        assert (a["ativacoes"], a["desativacoes"], a["conflitos"]) == \
               (b["ativacoes"], b["desativacoes"], b["conflitos"])


def test_ruido_dsl_melhor_que_baseline(tabela):
    assert (tabela[("dsl", "listagem3_ruido")]["acima_orcamento_pct"]
            < tabela[("baseline", "listagem3_ruido")]["acima_orcamento_pct"])


def test_sem_cooldown_so_muda_o_cooldown():
    a, b = ex.carregar_programa("dsl"), ex.carregar_programa("dsl_sem_cooldown")
    assert (a.politica.cooldown_frames, b.politica.cooldown_frames) == (10, 0)
    assert a.politica.budget_ms == b.politica.budget_ms
    assert [r.nome for r in a.regras] == [r.nome for r in b.regras]


def test_main_gera_tabela(tmp_path, capsys):
    ex.main(["--saida", str(tmp_path)])
    csv_linhas = (tmp_path / "metricas.csv").read_text(encoding="utf-8").splitlines()
    assert len(csv_linhas) == 1 + len(ex.PROGRAMAS) * len(ex.CENARIOS)
    assert len(list(tmp_path.glob("trace_*__*.jsonl"))) == 12
    assert "| baseline | oscilacao |" in capsys.readouterr().out
"""Fixa as Listagens 4 e 6 do artigo: se o compilador mudar, o texto muda junto."""

from dressgl.interpretador import main as interpretar
from dressgl.modelo import MODELO_PADRAO, carregar
from dressgl.semantica import compilar

RAIZ = MODELO_PADRAO.parent.parent
MODELO = carregar(MODELO_PADRAO)

DIAGNOSTICOS = [
    "6:9: erro semântico [V1]: telemetria drone.altitude não existe no modelo; "
    "disponíveis: drone.battery, frame_budget, terrain.below, terrain.suitability",
    '8:9: erro semântico [V4]: a superfície "FPV" é CRITICA e não pode ser desativada',
    '9:30: erro semântico [V2]: view "AGRO".hz exige unidade Hz',
    "13:30: erro semântico [V7]: a condição GIVEN de PousoImpossivel nunca é "
    "verdadeira no domínio do modelo; a regra é inalcançável",
    '14:9: erro semântico [V5]: WHEN AROUND pass "SuitabilityPass": o passo é '
    "injetado pela própria regra, que dependeria de si mesma para disparar",
    "16:10: erro semântico [V8]: ASSERT usa drone.battery, que o hospedeiro não "
    "mede; declare um instrumento para ela em [telemetria]",
]

RI_LISTAGEM_3 = [
    'RULE SafeSetdownAssist (linha 7, prioridade 90) AROUND pass "TerrainPass"',
    "  GIVEN lê: drone.battery, terrain.below",
    "  EfeitoInject(passo='SuitabilityPass', fase='AFTER', ancora='TerrainPass', linha=11)",
    "  EfeitoSet(superficie='MAP', atributo='mode', valor='SUITABILITY', linha=12)",
    "  EfeitoHighlight(extremo='ARGMAX', campo='terrain.suitability', raio_m=400, linha=13)",
    "  EfeitoSet(superficie='AGRO', atributo='hz', valor=2, linha=14)",
    "  EfeitoScale(recurso='instances', nome='crops', fator=0.25, linha=15)",
    "  ASSERT lê: frame_budget, view:FPV.scale",
]


def test_diagnosticos_da_listagem_de_erros():
    fonte = (RAIZ / "examples" / "erros_semanticos.dgl").read_text(encoding="utf-8-sig")
    _, diags = compilar(fonte, MODELO)
    assert diags == DIAGNOSTICOS


def test_ri_da_listagem_3(capsys):
    assert interpretar([str(RAIZ / "examples" / "safe_setdown.dgl")]) == 0
    assert capsys.readouterr().out.splitlines() == RI_LISTAGEM_3
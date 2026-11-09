# DRESS-GL

Linguagem específica de domínio (DSL) para escrever **políticas de degradação
gráfica** em estações de controle de solo de VANT agrícolas: o que degradar,
quando, em que ordem e com quais garantias quando o orçamento de quadro
(16,67 ms a 60 Hz) é excedido.

Este repositório contém o processador completo, escrito à mão em Python, sem
geradores de analisador:

| Fase | Módulo |
|---|---|
| Análise léxica (AFD, unidades no literal) | `src/dressgl/lexer.py` |
| Gramática BNF e verificação LL(1) | `src/dressgl/gramatica_ll1.py` |
| Análise sintática descendente recursiva | `src/dressgl/parser.py` |
| Tabela de símbolos (modelo do hospedeiro) | `src/dressgl/modelo.py` |
| Análise semântica V1–V8, C1, C2 | `src/dressgl/semantica.py`, `src/dressgl/decisao.py` |
| Geração da representação intermediária | `src/dressgl/interpretador.py` |
| Motor de execução por quadro | `src/dressgl/motor.py` |
| Hospedeiro simulado, trace e métricas | `src/dressgl/simulador.py`, `src/dressgl/trace.py` |
| Matriz de experimentos | `src/dressgl/experimentos.py` |

> **Escopo atual.** As políticas são executadas sobre um **hospedeiro
> simulado**, com custo de quadro **modelado** (não medido). Ainda não há
> integração com o compositor gráfico AgroView-SC nem ponte de telemetria com o
> CoppeliaSim. O CoppeliaSim só passou por um teste de conexão
> (`tools/coppeliasim_smoke.py`).

## Exemplo

```text
POLICY AgroViewSC {
  budget   = 16.67 ms;
  reserve  =  2.00 ms;
  cooldown =    10 frames;
}

RULE SafeSetdownAssist PRIORITY 90
  GIVEN drone.battery < 18 %
    AND terrain.below IN { WATER, STANDING_CROP }
  WHEN  AROUND pass "TerrainPass"
  THEN  INJECT pass "SuitabilityPass" AFTER "TerrainPass";
        SET view "MAP".mode = SUITABILITY;
        HIGHLIGHT ARGMAX terrain.suitability WITHIN 400 m;
        SET view "AGRO".hz = 2 Hz;
        SCALE instances "crops" BY 0.25;
  ASSERT frame_budget <= 16.67 ms
     AND view "FPV".scale >= 0.75
END
```

O manual completo da linguagem está em [`docs/manual.md`](docs/manual.md).

## Requisitos

- Python **3.11 ou superior** (usa `tomllib` da biblioteca padrão).
- Git.
- Opcional: CoppeliaSim 4.10 Edu, apenas para `tools/coppeliasim_smoke.py`.

O cliente `coppeliasim-zmqremoteapi-client` é opcional (extra `coppelia`) e só
é usado pelas ferramentas do CoppeliaSim. O compilador e o simulador usam
apenas a biblioteca padrão.

## Instalação

Windows (cmd):

```bat
git clone https://github.com/EmillyeRibeiro/dressgl.git
cd dressgl
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -e ".[dev,coppelia]"
```

Linux/macOS:

```bash
git clone https://github.com/EmillyeRibeiro/dressgl.git
cd dressgl
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Verifique a instalação:

```bat
python -m pytest -q
```

Saída esperada: `150 passed`.

## Uso

Todos os comandos são executados na raiz do repositório. Nos exemplos abaixo,
os caminhos usam `\` (Windows); no Linux/macOS, use `/`.

### Verificar só a sintaxe

```bat
python -m dressgl.parser examples\safe_setdown.dgl
```

```text
OK: 1 política(s), 1 regra(s)
```

### Verificar o programa (léxico, sintático e semântico)

```bat
python -m dressgl.semantica examples\erros_semanticos.dgl
```

```text
examples\erros_semanticos.dgl:6:9: erro semântico [V1]: telemetria drone.altitude não existe no modelo; ...
examples\erros_semanticos.dgl:8:9: erro semântico [V4]: a superfície "FPV" é CRITICA e não pode ser desativada
...
6 erro(s), 0 aviso(s)
```

Código de saída: `0` sem erros (avisos não contam), `1` com erros, `2` se o
modelo do hospedeiro for inválido. Para usar outro modelo, acrescente
`--modelo caminho.toml`.

### Compilar e ver a representação intermediária

```bat
python -m dressgl.interpretador examples\safe_setdown.dgl
```

```text
RULE SafeSetdownAssist (linha 7, prioridade 90) AROUND pass "TerrainPass"
  GIVEN lê: drone.battery, terrain.below
  EfeitoInject(passo='SuitabilityPass', fase='AFTER', ancora='TerrainPass', linha=11)
  ...
  ASSERT lê: frame_budget, view:FPV.scale
```

Diferentemente de `dressgl.semantica`, este comando para na primeira fase com
erro: erros léxicos ou sintáticos impedem a análise semântica, e erros
semânticos impedem a geração.

### Executar uma política num cenário simulado

```bat
python -m dressgl.simulador examples\safe_setdown.dgl examples\cenarios\listagem3.toml
```

Imprime as métricas e grava `results\trace_<nome do cenário>.jsonl`. Use
`--saida pasta` para mudar o destino. O simulador usa sempre o modelo padrão
(`modelo/agroview.toml`). Se o programa tiver erros de compilação, o comando
termina com um *traceback* de `ErroCompilacao`; nesse caso, rode antes
`dressgl.semantica`.

### Reproduzir os experimentos do artigo

```bat
python -m dressgl.experimentos
```

Executa 4 programas × 3 cenários e grava `results/metricas.csv`,
`results/metricas.md` e 12 traces `results/trace_<programa>__<cenario>.jsonl`.
Os traces não são versionados (`.gitignore`); as tabelas de métricas são.

### Tabela FIRST/FOLLOW e verificação LL(1)

```bat
python -m dressgl.gramatica_ll1
```

Termina com `Conflitos LL(1): nenhum, a gramática é LL(1)` (código de saída 0).

### Ferramentas

| Comando | O que faz |
|---|---|
| `python tools\env_report.py` | grava `results/ambiente.json` (SO, CPU, Python) |
| `python tools\coppeliasim_smoke.py` | testa a conexão ZeroMQ; exige o CoppeliaSim aberto |

## Estrutura do repositório

```text
src/dressgl/        processador (ver tabela no topo)
tests/              testes automatizados (pytest)
examples/           programas .dgl de exemplo
examples/cenarios/  cenários do hospedeiro simulado (TOML)
modelo/             modelo do hospedeiro (agroview.toml)
results/            métricas, ambiente e dependências travadas
docs/decisions.md   registro numerado das decisões de projeto (D1–D38)
docs/manual.md      manual da linguagem
tools/              utilitários de ambiente e de CoppeliaSim
```

## Exemplos incluídos

| Arquivo | Conteúdo |
|---|---|
| `examples/safe_setdown.dgl` | política de pouso seguro (Listagem 3 do artigo) |
| `examples/baseline_sem_compensacao.dgl` | a mesma regra sem as compensações |
| `examples/multiplas_regras.dgl` | pouso seguro + `EconomiaBateria` (regra sintética) |
| `examples/erros_semanticos.dgl` | programa com seis erros semânticos |

## Documentação

- [`docs/manual.md`](docs/manual.md): manual da linguagem, do modelo do
  hospedeiro, dos cenários e do trace.
- [`docs/decisions.md`](docs/decisions.md): decisões de projeto e motivos.

## Limitações conhecidas

- Custo de quadro modelado, com parâmetros calibrados à mão; não há medição
  sobre GPU.
- Pontos de junção (`WHEN`), `HIGHLIGHT` e `MARK` são verificados e compilados,
  mas não alteram o hospedeiro simulado.
- Identificadores aceitam apenas letras ASCII; não há números negativos nem
  conversão de unidades.

## Autoras

Caroline Silva Grizante, Emilly Emanuely Ribeiro dos Santos e Marcela Lovatto.
Engenharia de Computação, Centro Universitário da Fundação Hermínio Ometto
(FHO), Araras, SP. Trabalho final da disciplina Teoria da Computação e
Compiladores.

## Licença

Ainda não definida.
# DRESS-GL

Linguagem específica de domínio (DSL) para escrever **políticas de degradação
gráfica** em estações de controle de solo de VANT agrícolas: o que degradar,
quando, em que ordem e com quais garantias quando o orçamento de quadro
(16,67 ms a 60 Hz) é excedido.

Este repositório contém o processador completo, escrito à mão em Python, sem
geradores de analisador, e dois hospedeiros onde as políticas são executadas:

| Fase | Módulo |
|---|---|
| Análise léxica (AFD, unidades no literal) | `src/dressgl/lexer.py` |
| Gramática BNF e verificação LL(1) | `src/dressgl/gramatica_ll1.py` |
| Análise sintática descendente recursiva | `src/dressgl/parser.py` |
| Tabela de símbolos (modelo do hospedeiro) | `src/dressgl/modelo.py` |
| Análise semântica V1–V8, C1, C2 | `src/dressgl/semantica.py`, `src/dressgl/decisao.py` |
| Geração da representação intermediária | `src/dressgl/interpretador.py` |
| Motor de execução por quadro | `src/dressgl/motor.py` |
| Contrato do hospedeiro (D40) | `src/dressgl/hospedeiro.py` |
| Hospedeiro simulado, trace e métricas | `src/dressgl/simulador.py`, `src/dressgl/trace.py` |
| Hospedeiro medido AgroView-SC | `src/agroview/` |
| Matriz de experimentos | `src/dressgl/experimentos.py` |

> **Versões.** A versão entregue na disciplina está na tag
> [`v1.0`](https://github.com/EmillyeRibeiro/dressgl/tree/v1.0): processador
> completo, hospedeiro simulado com custo de quadro modelado e 150 testes.
> Este README descreve a versão atual, que acrescenta o hospedeiro medido
> AgroView-SC.

## Hospedeiros

O motor conversa com o hospedeiro apenas pelo contrato de
`src/dressgl/hospedeiro.py` (D40). No quadro *q*, o hospedeiro recebe o plano
calculado no quadro *q*−1, desenha e devolve as leituras de *q*. Há duas
implementações:

| Hospedeiro | Custo de quadro | Uso |
|---|---|---|
| Simulado (`dressgl.simulador`) | modelado, com parâmetros calibrados à mão | experimentos do artigo, linha de comando |
| AgroView-SC (`agroview`) | renderização real em CPU com NumPy (D42) | medições, uso a partir de Python |

O AgroView-SC renderiza três superfícies: FPV (320×180), MAP (128×128) e AGRO
(96×96), nas resoluções com `scale = 1.0`, com 200 instâncias base de cultura.
Cada superfície é desenhada na sua própria frequência (`hz`), com decimação em
relação aos 60 Hz do quadro (D43). `frame_budget` é o custo do próprio quadro,
sem média (D46). O relógio tem dois modos:

- **`tempo`** (padrão): `frame_budget` é o tempo de parede do quadro, medido
  com `perf_counter`.
- **`carga`**: `frame_budget = Σ carga × ms_por_carga[passo]`, com um
  coeficiente por passo obtido por calibração (D48). A carga é uma contagem
  estrutural (pixels × operações por pixel). O resultado é determinístico e
  próximo do tempo medido na máquina calibrada. Um número único, aplicado a
  todos os passos, continua aceito por compatibilidade.

As entradas (`drone.battery`, `terrain.below`) ainda vêm do cenário. O
CoppeliaSim só passou por um teste de conexão (`tools/coppeliasim_smoke.py`);
a ponte de telemetria é o próximo passo.

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

O núcleo `dressgl` (compilador, motor e hospedeiro simulado) usa apenas a
biblioteca padrão. As demais dependências são extras do `pyproject.toml`:

| Extra | Instala | Para quê |
|---|---|---|
| `dev` | pytest | testes |
| `render` | NumPy | renderização do AgroView-SC |
| `coppelia` | `coppeliasim-zmqremoteapi-client` | `tools/coppeliasim_smoke.py` |
| `gui` | NumPy + PySide6 | reservado para a janela do AgroView-SC, que ainda não existe |

## Instalação

Windows (cmd):

```bat
git clone https://github.com/EmillyeRibeiro/dressgl.git
cd dressgl
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -e ".[dev,render,coppelia]"
```

Linux/macOS:

```bash
git clone https://github.com/EmillyeRibeiro/dressgl.git
cd dressgl
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev,render,coppelia]"
```

Verifique a instalação:

```bat
python -m pytest -q
```

Saída esperada: `195 passed`. Os testes do AgroView-SC precisam do NumPy
(extra `render`).

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

### Usar o hospedeiro AgroView-SC

O AgroView-SC ainda não tem comando de linha nem janela; ele é usado a partir
de Python. O cenário precisa apenas de uma lista `entradas`, com um dicionário
de telemetria por quadro:

```python
from types import SimpleNamespace

from agroview.calibracao import carregar_calibracao
from agroview.hospedeiro import HospedeiroAgroView
from dressgl.simulador import PLANO_VAZIO

cenario = SimpleNamespace(
    entradas=[{"drone.battery": 50.0, "terrain.below": "BARE_SOIL"}] * 600)

medido = HospedeiroAgroView(cenario)                          # relógio "tempo"
por_carga = HospedeiroAgroView(cenario, relogio="carga",
                               ms_por_carga=carregar_calibracao())

for q in range(600):
    l = por_carga.leituras(q, PLANO_VAZIO)
print(l["frame_budget"], por_carga.ultimo.execucoes)
```

`leituras(q, plano)` aplica o plano ao quadro *q*, desenha e devolve a
telemetria com `frame_budget` e a configuração das vistas. O último quadro
desenhado fica em `ultimo`. Um passo sem coeficiente no arquivo de calibração
gera `ValueError`.

### Calibrar o relógio por carga

```bat
python tools\env_report.py
python tools\calibrar_relogio.py
```

Mede 540 quadros (depois de 60 de aquecimento) e grava, em
`results/calibracao.toml`, a mediana de ms por unidade de carga de cada passo
(D48). A calibração versionada foi feita na máquina descrita em
`results/ambiente.json`:

| Passo | ns por unidade de carga | Amostras |
|---|---|---|
| `TerrainPass` (FPV e MAP) | 50,8 | 1080 |
| `CropInstancesPass` | 87,8 | 540 |
| `SuitabilityPass` (AGRO) | 1,55 | 90 |

Com esses coeficientes, o quadro comum (FPV + MAP) vale ≈ 3,9 ms e o quadro
com AGRO vale ≈ 5,1 ms. Recalibre ao trocar de máquina.

### Reproduzir os experimentos do artigo

```bat
python -m dressgl.experimentos
```

Executa 4 programas × 3 cenários no hospedeiro simulado e grava
`results/metricas.csv`, `results/metricas.md` e 12 traces
`results/trace_<programa>__<cenario>.jsonl`. Os traces não são versionados
(`.gitignore`); as tabelas de métricas são. Os experimentos são os mesmos da
`v1.0` e ainda não usam o AgroView-SC.

### Tabela FIRST/FOLLOW e verificação LL(1)

```bat
python -m dressgl.gramatica_ll1
```

Termina com `Conflitos LL(1): nenhum, a gramática é LL(1)` (código de saída 0).

### Ferramentas

| Comando | O que faz |
|---|---|
| `python tools\env_report.py` | grava `results/ambiente.json` (SO, CPU, Python) |
| `python tools\calibrar_relogio.py` | grava `results/calibracao.toml` (D48) |
| `python tools\coppeliasim_smoke.py` | testa a conexão ZeroMQ; exige o CoppeliaSim aberto |

## Estrutura do repositório

```text
src/dressgl/        processador, contrato do hospedeiro e hospedeiro simulado
src/agroview/       hospedeiro medido AgroView-SC (ordem dos passos, render em CPU, calibração)
tests/              testes automatizados (pytest)
examples/           programas .dgl de exemplo
examples/cenarios/  cenários do hospedeiro simulado (TOML)
modelo/             modelo do hospedeiro (agroview.toml)
results/            métricas, ambiente, calibração e dependências travadas
docs/decisions.md   registro numerado das decisões de projeto (D1–D48)
docs/manual.md      manual da linguagem
tools/              utilitários de ambiente, calibração e CoppeliaSim
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

- O AgroView-SC renderiza em CPU (NumPy), não em GPU, e em resolução reduzida.
  Os tempos medidos refletem esse renderizador, não um compositor gráfico de
  produção.
- O AgroView-SC ainda não tem comando de linha nem janela, e os experimentos
  do artigo continuam no hospedeiro simulado.
- O relógio por carga é linear e não tem termo fixo por passo. Passos com
  custo fixo relevante (por exemplo, `CropInstancesPass`) ficam subestimados
  quando a carga cai.
- O `SuitabilityPass` foi calibrado só no AGRO. As variantes sobrepostas no
  MAP e no FPV usam o mesmo coeficiente sem medição própria.
- A calibração mede os passos, e não o intervalo entre eles. Por isso, o modo
  `carga` tende a ficar um pouco abaixo do modo `tempo`. A calibração vale
  para a máquina em que foi feita.
- O hospedeiro simulado mantém o custo modelado da `v1.0`, com parâmetros
  calibrados à mão.
- Pontos de junção (`WHEN`), `HIGHLIGHT` e `MARK` são verificados e compilados,
  mas não alteram nenhum dos dois hospedeiros.
- As entradas do AgroView-SC ainda vêm do cenário, não do CoppeliaSim.
- Identificadores aceitam apenas letras ASCII; não há números negativos nem
  conversão de unidades.

## Autoras

Caroline Silva Grizante, Emilly Emanuely Ribeiro dos Santos e Marcela Lovatto.
Engenharia de Computação, Centro Universitário da Fundação Hermínio Ometto
(FHO), Araras, SP. Trabalho final da disciplina Teoria da Computação e
Compiladores.

## Licença

Ainda não definida.
# DRESS-GL

Linguagem específica de domínio (DSL) para escrever **políticas de degradação
gráfica** em estações de controle de solo de VANT agrícolas: o que degradar,
quando, em que ordem e com quais garantias quando o orçamento de quadro
(16,67 ms a 60 Hz) é excedido.

Este repositório contém o processador completo, escrito à mão em Python, sem
geradores de analisador, dois hospedeiros onde as políticas são executadas e
uma ponte com o CoppeliaSim que fornece telemetria de voos simulados:

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
| Ponte com o CoppeliaSim, missões e gravações | `src/ponte_coppelia/` |
| Matriz de experimentos | `src/dressgl/experimentos.py`, `src/ponte_coppelia/experimentos.py` |
| Janela de reprodução de traces e replay 3D | `src/visualizador/` |

> **Versões.** A versão atual está na tag
> [`v3.1`](https://github.com/EmillyeRibeiro/dressgl/tree/v3.1): acrescenta a
> janela de reprodução de traces e o replay 3D no CoppeliaSim
> (`src/visualizador/`, D61–D64) e a fonte do artigo (`artigo/`), sem alterar
> o processador, os hospedeiros nem as tabelas de `results/`; 264 testes, com os traces gerados (ver Instalação).
> A versão descrita no artigo final está na tag
> [`v3.0`](https://github.com/EmillyeRibeiro/dressgl/tree/v3.0): processador,
> hospedeiro simulado, hospedeiro medido AgroView-SC, ponte com o CoppeliaSim
> e 223 testes. A primeira entrega da disciplina está na tag
> [`v1.0`](https://github.com/EmillyeRibeiro/dressgl/tree/v1.0): processador
> completo, hospedeiro simulado com custo de quadro modelado e 150 testes.

## Hospedeiros

O motor conversa com o hospedeiro apenas pelo contrato de
`src/dressgl/hospedeiro.py` (D40). No quadro *q*, o hospedeiro recebe o plano
calculado no quadro *q*−1, desenha e devolve as leituras de *q*. Há duas
implementações:

| Hospedeiro | Custo de quadro | Uso |
|---|---|---|
| Simulado (`dressgl.simulador`) | modelado, com parâmetros calibrados à mão | experimentos da `v1.0`, gravações do CoppeliaSim, varredura de ruído, linha de comando |
| AgroView-SC (`agroview`) | renderização real em CPU com NumPy (D42) | medições, gravações do CoppeliaSim |

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

As entradas (`drone.battery`, `terrain.below`) vêm de uma de duas fontes: um
cenário TOML em `examples/cenarios/` (D28) ou a gravação de um voo no
CoppeliaSim (D52).

## Ponte com o CoppeliaSim

A ponte é síncrona, em modo *stepping*: a física só avança quando a ponte
pede, e o motor continua síncrono e puro (D49). Cada passo de física tem
50 ms e corresponde a 3 quadros de 60 Hz. Entre um passo e outro, vale a
última leitura (D50). O passo da cena precisa ser de 50 ms.

O CoppeliaSim fornece a posição do drone e o tempo simulado. `terrain.below`
vem das zonas retangulares da missão (`examples/missoes/*.toml`); se zonas se
sobrepõem, vale a última. `drone.battery` cai linearmente com o tempo
simulado (D51).

Cada voo é gravado em `gravacao_<missao>.jsonl`, na pasta de `--saida`
(padrão: `results/`). A gravação inclui o alvo e o solo sob o alvo, o que
separa o atraso da física do atraso do cooldown (D53). Ela pode ser repetida
como cenário **sem o CoppeliaSim** (D52); por isso, os experimentos com
física são reprodutíveis e testados.

As gravações de referência (`results/gravacao_*.jsonl`) foram feitas no ciclo
C4 do desenvolvimento (commit `a7686a4`). Regravar `borda_agua` com
`cenas/borda_agua.ttt`, reabrindo a cena antes de cada voo, dá sempre o mesmo
arquivo, idêntico a `results/rep1/`. Esse arquivo difere da referência só em
`pos`, por no máximo 5,0e-8 m (resíduo de float32), e gera o mesmo trace
(D58, D60).

Um ruído de percepção pode ser aplicado sobre as gravações (D56). Cada eixo
(x, y) recebe um processo Gauss-Markov de 1ª ordem com desvio padrão
estacionário `erro_pos_m` e constante de tempo `tau_s` (0,5 s nos
experimentos), atualizado a 10 Hz e mantido entre amostras. Ele altera a
posição *percebida*, e com ela `terrain.below`, sem mexer na física.

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
- Opcional: CoppeliaSim 4.10 Edu, só para gravar voos novos e para
  `tools/coppeliasim_smoke.py`. Os experimentos com as gravações versionadas
  não precisam dele.

O núcleo `dressgl` (compilador, motor e hospedeiro simulado) usa apenas a
biblioteca padrão. As demais dependências são extras do `pyproject.toml`:

| Extra | Instala | Para quê |
|---|---|---|
| `dev` | pytest + NumPy | testes, inclusive os do AgroView-SC e a regressão lenta |
| `render` | NumPy | renderização do AgroView-SC |
| `coppelia` | `coppeliasim-zmqremoteapi-client` | comunicação com o CoppeliaSim aberto |
| `gui` | NumPy | janela de reprodução de traces (`python -m visualizador`), em tkinter (D61) |

As versões usadas nos resultados versionados estão em
`results/requirements-lock.txt`.

## Instalação

Windows (cmd):

```bat
git clone https://github.com/EmillyeRibeiro/dressgl.git
cd dressgl
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
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

Para gravar voos com o CoppeliaSim aberto, instale `".[dev,coppelia]"`.

Verifique a instalação:

```bat
python -m pytest -q
```

Num clone recém-feito, a saída esperada é `230 passed, 19 skipped, 1 deselected`.
Os testes de `tests/test_visualizador.py` e `tests/test_render_trace.py` leem
os traces `results/trace_coppelia_*.jsonl`, que não são versionados (D38).
Sem esses traces, eles são pulados. Para rodá-los, gere os traces (cerca de
1 min) e repita:

```bat
python -m ponte_coppelia.experimentos --gravacoes results --saida results --hospedeiros simulado agroview
python -m pytest -q
```

Saída esperada: `263 passed, 1 deselected`. O comando também regenera
`results/metricas_coppelia.{csv,md}`, idênticos aos versionados. O teste
deixado de fora tem o marcador `lento` (D59). Ele regenera
`results/metricas_coppelia.csv`, compara o resultado com a versão versionada
e leva cerca de 1 min. Rode-o antes de commitar mudanças em `results/`,
`src/ponte_coppelia` ou `src/agroview`:

```bat
python -m pytest -q -m lento
```

Saída esperada: `1 passed, 263 deselected` (ou `249 deselected`, se os traces
ainda não tiverem sido gerados).

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

### Usar o hospedeiro AgroView-SC a partir de Python

O AgroView-SC não tem laço interativo: a janela de `visualizador` só reproduz
traces gravados (D62). Fora dos experimentos com física, ele é usado a
partir de Python. O cenário precisa apenas de uma lista `entradas`, com um
dicionário de telemetria por quadro:

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
desenhado fica em `ultimo`. No exemplo, o quadro 599 não redesenha o AGRO, e o
`frame_budget` impresso fica em torno de 3,91 ms. Um passo sem coeficiente no
arquivo de calibração gera `ValueError`.

### Calibrar o relógio por carga

```bat
python tools\env_report.py
python tools\calibrar_relogio.py
```

Mede 540 quadros (depois de 60 de aquecimento) e grava, em
`results/calibracao.toml`, a mediana de ms por unidade de carga de cada passo
(D48). A tabela abaixo mostra esses valores convertidos para ns. A calibração
versionada foi feita na máquina descrita em `results/ambiente.json`:

| Passo | ns por unidade de carga | Amostras |
|---|---|---|
| `TerrainPass` (FPV e MAP) | 50,8 | 1080 |
| `CropInstancesPass` | 87,8 | 540 |
| `SuitabilityPass` (AGRO) | 1,55 | 90 |

Com esses coeficientes e nenhuma regra ativa, o quadro comum (`TerrainPass`
em FPV e MAP, mais as 200 instâncias de cultura) vale ≈ 3,9 ms. O quadro em
que o AGRO também é redesenhado (a cada 6 quadros, a 10 Hz) vale ≈ 5,1 ms.
Com a política de pouso ativa, o `SuitabilityPass` é sobreposto a FPV e MAP
(D45, D47), e o pior quadro nas gravações chega a ≈ 14,2 ms. Recalibre ao
trocar de máquina.

### Reproduzir os experimentos do artigo

O escopo da avaliação é um cenário excepcional (bateria em reserva sobre solo
impróprio) em sete condições (D57). Os três comandos abaixo regeneram as
tabelas versionadas em `results/`.

**Hospedeiro simulado, cenários TOML** (os mesmos experimentos da `v1.0`):

```bat
python -m dressgl.experimentos
```

Executa 4 programas × 3 cenários e grava `results/metricas.csv`,
`results/metricas.md` e 12 traces `results/trace_<programa>__<cenario>.jsonl`.
Os traces não são versionados (`.gitignore`); as tabelas de métricas são.

**Gravações de voo, sem o CoppeliaSim** (D54):

```bat
python -m ponte_coppelia.experimentos --gravacoes results --saida results --hospedeiros simulado agroview
```

Executa os mesmos 4 programas sobre as gravações de referência de
`results/`, nos dois hospedeiros (o AgroView-SC com relógio por carga), e
grava `results/metricas_coppelia.csv` e `results/metricas_coppelia.md`. O
teste `lento` confere se o resultado é idêntico ao versionado.

**Ruído de percepção** (D56):

```bat
python tools\varredura_ruido.py examples\missoes\margem_ruido.toml
```

São 4 níveis de erro (0; 0,02; 0,05 e 0,10 m) × 10 sementes × 2 programas
(`dsl` e `dsl_sem_cooldown`), no hospedeiro simulado, num total de 80 linhas
em `results/varredura_ruido.csv`. Os parâmetros e a hipótese foram fixados
antes da execução (D56).

### Gravar um voo no CoppeliaSim

Exige o CoppeliaSim 4.10 aberto e o extra `coppelia`. Os experimentos acima
**não** precisam disto, porque usam as gravações versionadas.

1. Abra a cena da missão **recém-carregada** (File → Open scene) e confira
   que o título da janela mostra o nome dela. Não reaproveite uma cena que já
   simulou, porque a repetição diverge (D58). Não salve a cena depois do voo.

   | Missão | Cena | Gravação para comparar |
   |---|---|---|
   | `examples\missoes\borda_agua.toml` | `cenas\borda_agua.ttt` | `results\rep1\gravacao_borda_agua.jsonl` |
   | `examples\missoes\pouso_agua.toml` | não versionada | não há (D60) |

   O passo da simulação da cena deve ser de 50 ms (D50).
2. Rode, **sempre com `--saida`**:

   ```bat
   python tools\rodar_coppelia.py examples\safe_setdown.dgl examples\missoes\borda_agua.toml --saida results\rep3
   ```

   Cada execução grava `gravacao_<missao>.jsonl` e
   `trace_coppelia_<hospedeiro>__<missao>.jsonl`, em que `<missao>` é o
   campo `nome` do TOML. Sem `--saida`, o destino é `results\`, e a gravação
   de referência é sobrescrita. Para restaurá-la:
   `git checkout -- results\gravacao_borda_agua.jsonl`.
3. Compare com `rep1`. O resultado esperado é `quadros_divergentes 0`:

   ```bat
   python tools\comparar_gravacoes.py results\rep1\gravacao_borda_agua.jsonl results\rep3\gravacao_borda_agua.jsonl
   ```

Comparada com a referência do C4 (`results\gravacao_borda_agua.jsonl`), a
regravação diverge em todos os 720 quadros, mas só em `pos`, com diferença
máxima de 5,0e-8 m. Os demais campos e o trace são iguais (D58, D60).

### Reproduzir um voo na janela

A janela **não executa o motor**: ela reproduz os traces gerados pelos
experimentos (D62). O que aparece na tela é o que está em
`results/metricas_coppelia.{csv,md}`. Os traces não são versionados (D38),
então gere-os antes:

```bat
pip install -e ".[gui]"
python -m ponte_coppelia.experimentos --gravacoes results --saida results --hospedeiros simulado agroview
python -m visualizador --gravacao borda_agua --programa dsl --hospedeiro agroview
```

Opções: `--gravacao {borda_agua,pouso_agua}`,
`--programa {dsl,baseline,dsl_sem_cooldown,multiplas}`,
`--hospedeiro {agroview,simulado}` e `--sem-imagens` (não reconstrói as
superfícies). `--erro-pos` e `--semente` estão reservadas: `--erro-pos > 0`
é recusado, porque o ruído de percepção exige o laço ao vivo (D62).

#### Replay 3D no CoppeliaSim

Exige o CoppeliaSim aberto, a simulação **parada** e o extra `coppelia`:

```bat
pip install -e ".[coppelia]"
python -m visualizador --coppelia --gravacao borda_agua --duas-vistas
```

O replay só posiciona o drone com o `pos` gravado: não há física nem motor,
e nada é gravado em `results/` (D63). Câmeras: `--vista-topo`,
`--duas-vistas`, `--seguir-drone`, `--ortografica`, `--altura-camera`
(padrão 9 m na principal e 8 m na janela). `--fps` define a velocidade
(padrão 30). Ao terminar (Enter), o replay remove o que criou, a menos que
se use `--manter-rastro`. **Não salve a cena antes disso.** Se o replay for
interrompido, rode `python -m visualizador --coppelia --restaurar-cena`.

Limitações: HIGHLIGHT e MARK não são desenhados (D64); o FPV usa terreno
sintético (D45); o `frame_budget` exibido vem do trace, não do tempo de
desenho no Tk (D61). Durante o replay, trocar de aba de cena, usar Desfazer
ou apagar o drone encerra o replay. Em algumas distribuições Linux, é
preciso instalar o Tk (`python3-tk`).

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
| `python tools\varredura_ruido.py <missao.toml>` | varredura de ruído de percepção (D56) |
| `python tools\coppeliasim_smoke.py` | testa a conexão ZeroMQ; exige o CoppeliaSim aberto |
| `python tools\rodar_coppelia.py <programa.dgl> <missao.toml> --saida <pasta>` | grava um voo; exige o CoppeliaSim aberto |
| `python tools\comparar_gravacoes.py <a.jsonl> <b.jsonl>` | compara duas gravações quadro a quadro e mostra a diferença máxima por campo |
| `python tools\desenhar_zonas.py` | desenha na cena as zonas de solo da missão, só para visualização (D55) |

Os demais scripts de `tools/` (`aplicar_percepcao`, `custo_injecao`,
`custo_por_estado`, `resumo_varredura`, `trocas`) são auxiliares de análise
usados durante o desenvolvimento e não são necessários para reproduzir as
tabelas do artigo.

## Estrutura do repositório

```text
src/dressgl/          processador, contrato do hospedeiro e hospedeiro simulado
src/agroview/         hospedeiro medido AgroView-SC (ordem dos passos, render em CPU, calibração)
src/ponte_coppelia/   ponte com o CoppeliaSim, missões, gravações, ruído de percepção e experimentos
src/visualizador/     janela de reprodução de traces (tkinter) e replay 3D no CoppeliaSim (D61–D63)
tests/                testes automatizados (pytest)
examples/             programas .dgl de exemplo
examples/cenarios/    cenários do hospedeiro simulado (TOML)
examples/missoes/     missões do CoppeliaSim: zonas de solo e bateria (TOML)
cenas/                cenas do CoppeliaSim (.ttt)
modelo/               modelo do hospedeiro (agroview.toml)
results/              métricas, gravações de referência, ambiente, calibração e dependências travadas
results/rep1, rep2/   repetições de borda_agua com a cena versionada (D58, D60)
results/arquivo/      dois traces antigos do hospedeiro simulado (borda_agua, pouso_agua), mantidos como evidência (D58)
docs/decisions.md     registro numerado das decisões de projeto (D1–D64)
docs/manual.md        manual da linguagem
artigo/               fonte LaTeX do artigo final (IEEEtran), adicionada depois da tag v3.0
tools/                utilitários de ambiente, calibração, CoppeliaSim e análise
```

## Exemplos incluídos

| Arquivo | Conteúdo |
|---|---|
| `examples/safe_setdown.dgl` | política de pouso seguro (Listagem 3 do artigo) |
| `examples/baseline_sem_compensacao.dgl` | a mesma regra sem as compensações |
| `examples/multiplas_regras.dgl` | pouso seguro + `EconomiaBateria` (regra sintética) |
| `examples/erros_semanticos.dgl` | programa com seis erros semânticos |
| `examples/missoes/borda_agua.toml` | missão da gravação de referência (C4) e das repetições (D58) |
| `examples/missoes/margem_ruido.toml` | parâmetros da varredura de ruído (D56) |
| `examples/missoes/pouso_agua.toml` | missão de pouso sobre a água |
| `cenas/borda_agua.ttt` | cena das repetições `rep1`/`rep2` (D58); reproduz a referência do C4 a menos de 5,0e-8 m em `pos` (D60) |
| `cenas/agro_quadcopter.ttt` | cena com as zonas desenhadas a partir da missão (D55) |

## Documentação

- [`docs/manual.md`](docs/manual.md): manual da linguagem, do modelo do
  hospedeiro, dos cenários e do trace.
- [`docs/decisions.md`](docs/decisions.md): decisões de projeto e motivos.

## Limitações conhecidas

- A avaliação cobre um único cenário excepcional, em sete condições. Os
  outros cinco cenários da Seção III-A do artigo ficam como trabalho futuro
  (D57).
- O AgroView-SC renderiza em CPU (NumPy), não em GPU, e em resolução reduzida.
  Os tempos medidos refletem esse renderizador, não um compositor gráfico de
  produção.
- A janela (`python -m visualizador`) só reproduz traces: não executa o motor
  ao vivo nem mostra o ruído de percepção (D62).
- O relógio por carga é linear e não tem termo fixo por passo. Passos com
  custo fixo relevante (por exemplo, `CropInstancesPass`) ficam subestimados
  quando a carga cai.
- O `SuitabilityPass` foi calibrado só no AGRO. As variantes sobrepostas no
  MAP e no FPV usam o mesmo coeficiente sem medição própria. Elas respondem
  por cerca de 9 dos ≈ 14,2 ms do pior quadro com a política de pouso ativa,
  e um erro de cerca de 25 % nesse coeficiente bastaria para exceder o
  orçamento.
- A calibração mede os passos, e não o intervalo entre eles. Por isso, o modo
  `carga` tende a ficar um pouco abaixo do modo `tempo`. A calibração vale
  para a máquina em que foi feita.
- O hospedeiro simulado mantém o custo modelado da `v1.0`, com parâmetros
  calibrados à mão. Ele usa custo médio, e o AgroView-SC usa o custo do
  quadro, com os picos da decimação (D43, D46). Por isso, reduzir o `hz` de
  uma superfície baixa o custo médio no simulado, mas não o pior quadro no
  AgroView-SC.
- A bateria é modelada como linear no tempo simulado, sem relação com o
  empuxo dos motores (D51).
- `terrain.below` vem de zonas retangulares da missão, e a classificação do
  solo é perfeita, dada a posição.
- A cena tem escala reduzida (campo de 5 m). O ruído de percepção não foi
  calibrado contra um receptor real e só afeta x e y (D56).
- A ponte com o CoppeliaSim não roda em tempo real (D49). Gravações
  idênticas exigem reabrir a cena antes de cada voo (D58).
- As gravações de referência do C4 não são regraváveis byte a byte a partir
  do repositório. Com a cena versionada, `borda_agua` difere da referência
  só em `pos` (≤ 5,0e-8 m) e gera o mesmo trace. `pouso_agua` não tem cena
  versionada. Os experimentos continuam reproduzíveis porque rodam sobre
  as gravações (D52, D60).
- Pontos de junção (`WHEN`), `HIGHLIGHT` e `MARK` são verificados e compilados,
  mas não alteram nenhum dos dois hospedeiros nem são desenhados na janela (D64).
- Identificadores aceitam apenas letras ASCII; não há números negativos nem
  conversão de unidades.

## Autoras

Caroline Silva Grizante, Emilly Emanuely Ribeiro dos Santos e Marcela Lovatto.
Engenharia de Computação, Centro Universitário da Fundação Hermínio Ometto
(FHO), Araras, SP. Trabalho final da disciplina Teoria da Computação e
Compiladores.

## Licença

Ainda não definida.
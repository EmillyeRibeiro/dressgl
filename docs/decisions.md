# Registro de decisões

| # | Decisão | Motivo |
|---|---|---|
| D1 | Artigo, README e mensagens de erro em português; palavras-chave da DSL em inglês | Padrão da disciplina; herança do BDD/DRESS-ML |
| D2 | Analisadores léxico e sintático escritos à mão, sem gerador | Tabela II da Etapa 1 |
| D3 | Unidade incorporada ao literal: NUM (ws? UNIDADE)?, ws = espaço/tab | Linguagem léxica regular; viabiliza V2 |
| D4 | Comentário com `#`; enumerados em CAIXA_ALTA | Convenções léxicas; confirmada (testes de lexer e D11 dependem dela) |
| D5 | Erro léxico gera token ERRO e a varredura continua | Relatar todos os erros de uma vez |
| D6 | `referencia = IDENT ["." IDENT] \| alvo "." IDENT` | Aceitar `frame_budget`; continua LL(1) |
| D7 | AgroView-SC reimplementado (PySide6/NumPy); Listagem 1 fica como ilustração do estilo imperativo | Código antigo descartado; o baseline experimental é o da D33 |
| D8 | CoppeliaSim 4.10.0 Edu (Bullet 2.78) fornece telemetria via ZMQ (porta 23000) | Indicação do professor |
| D9 | Modelo do hospedeiro em `modelo/agroview.toml`, lido pelo compilador e pelo host | Desacoplar a linguagem da parte gráfica |
| D10 | Códigos V1–V8 conforme o artigo (II-D, P4); C1 e C2 são verificações complementares fora da numeração | Rastreabilidade entre artigo, código e testes |
| D11 | Nomes de regra/política em PascalCase; o modelo rejeita atributos que a linguagem não consegue escrever | Consequência da classificação léxica de ENUM e palavras reservadas |
| D12 | Unidades sem conversão: a unidade do literal deve ser exatamente a do modelo | Simplicidade; evita erros de 1000× entre ms e s |
| D13 | Fator de SCALE em (0, 1] | A linguagem só degrada carga; aumentar competiria com o orçamento |
| D14 | V6 e V7 decididas de forma exata por enumeração de representantes (decisao.py); V6 só vale para atributos sem composição monotônica (enumerados) | Átomos comparam uma variável com uma constante, então o espaço relevante é finito |
| D15 | V5: junção em passo injetado pela própria regra; AROUND/AFTER com SUPPRESS do mesmo passo; INJECT relativo a si mesmo ou a passo suprimido; dois INJECT na mesma âncora e fase | Interpretação concreta de "junção inválida ou ambígua" |
| D16 | V8: ASSERT só usa telemetria com `instrumento` declarado ou atributos de view; entradas do simulador (drone.battery) não são instrumentos | ASSERT é contrato sobre o efeito das ações, medido pelo hospedeiro |
| D17 | Composição entre regras ativas: mínimo para números, conjunção para booleanos, nenhuma para enumerados | Seção II-C (iii); base de P6 |
| D18 | Python >= 3.11 | tomllib na biblioteca padrão |
| D19 | Back end gera representação intermediária: cada regra vira condição + tupla de efeitos imutáveis; compilar não altera o hospedeiro, aplicar e compor efeitos é papel do motor (P6) | Testável sem GUI; mesma interface para baseline e DSL (P5) |
| D20 | `compilar_programa` só gera código sem erros: léxico/sintático interrompem antes da semântica; erro semântico interrompe antes da geração; avisos não bloqueiam | Evita diagnósticos em cascata sobre AST parcial; as garantias do artigo só valem para programas validados |
| D21 | Leituras nomeadas: telemetria pela chave do TOML (`drone.battery`, `frame_budget`); configuração aplicada como `view:SUP.attr`; leitura ausente gera `ErroExecucao` | Contrato explícito entre hospedeiro e regras |
| D22 | Composição: todas as regras ativas são aplicadas, da maior para a menor prioridade (sem prioridade = por último; empate = ordem no fonte). SET no mesmo alvo segue D17 (numérico: mínimo; booleano: conjunção); só SET enumerado com valores diferentes e INJECT/SUPPRESS do mesmo passo usam "vence a primeira na ordem", com a outra registrada como conflito. SCALE no mesmo recurso: menor fator. HIGHLIGHT/MARK: união sem repetição | O resultado não depende da ordem de ativação e é idempotente; conflitos ficam rastreáveis (P7); coerente com D14/D17 |
| D23 | SCALE resolution multiplica a escala linear da superfície (custo de pixels proporcional ao fator ao quadrado); SCALE instances multiplica o número de instâncias desenhadas | Mesma semântica que view.scale lido no ASSERT |
| D24 | Cooldown: depois de ativar ou desativar, uma regra só pode mudar de estado de novo após `cooldown` quadros; a mudança pedida antes disso fica "retida" e vai para o trace | Histerese contra oscilação (flicker) |
| D25 | O ASSERT de uma regra aplicada no quadro t é verificado com as leituras do quadro t+1, que medem o efeito do plano de t. Uma violação é registrada e não desfaz a regra | Monitoramento em execução sem realimentação escondida |
| D26 | Ponte com o CoppeliaSim: telemetria lida via ZMQ em thread separada; o motor recebe a última leitura completa e é síncrono e puro | Motor testável sem simulador |
| D27 | Custo estimado por ação fica no hospedeiro (simulado ou real), não no motor | O motor decide; quem mede é o hospedeiro |
| D28 | Hospedeiro simulado determinístico: cada cenário é um TOML em `examples/cenarios/` com trechos de entradas por quadro (constante ou rampa `{de, ate}`; trechos posteriores sobrepõem os anteriores). Ruído gaussiano opcional, com semente fixa por quadro | Experimentos reproduzíveis: o mesmo cenário gera o mesmo trace |
| D29 | Custo de quadro modelado: `base + Σ(passos executados) custo_passo × fração_instâncias + Σ(superfícies habilitadas) custo_sup × escala² × hz/hz_padrão`, com parâmetros em `[custo]` no `agroview.toml`. Passos executados = padrão − SUPPRESS + INJECT. O hospedeiro aplica o plano de t e produz as leituras de t+1 (D25, D27) | Mede o efeito das ações sem GUI; no artigo, números calibrados à mão, modelados e não medidos |
| D30 | Trace em JSON Lines (`results/trace_*.jsonl`): um `Registro` por linha, com as leituras e a condição de cada regra no quadro. Tuplas viram listas; chaves viram `"SUP.attr"` | `grep` por quadro; leitura simples com `json`/pandas (P7) |
| D31 | Métricas do trace: % de quadros acima do orçamento, pior quadro, ativações/desativações, retenções, violações de ASSERT, conflitos, atraso de ativação (médio/máx.) | Base da comparação DSL × baseline (Passo 6) |
| D32 | Configuração em vigor = padrão do atributo substituído pelo plano do quadro; ao desativar, volta ao padrão. Padrão: `valores` → maior; `enum` → primeiro; `bool` → true. `view:SUP.scale` inclui o fator de SCALE resolution | Plano recalculado a cada quadro (D19, D22); o nominal é o estado de maior qualidade |
| D33 | Baseline = a regra da Listagem 3 sem as compensações (sem `SET AGRO.hz` e sem `SCALE`), com a mesma POLICY (cooldown 10) e o mesmo GIVEN/WHEN/ASSERT (`baseline_sem_compensacao.dgl`) | Isola o efeito das compensações. Ameaça à validade: baseline construído pelos autores, não é uma implementação imperativa independente |
| D34 | Cenários extras: `listagem3_ruido` (σ = 0,5 ms, semente 42) e `oscilacao` (bateria alternando 19/17 % sobre água) | Robustez a ruído; comportamento do cooldown |
| D35 | Ablação `dsl_sem_cooldown`: mesmo fonte, `cooldown_frames = 0`, aplicada no script | Mede o custo/benefício do cooldown (oscilação × atraso) |
| D36 | `multiplas_regras.dgl`: Listagem 3 + `EconomiaBateria` (PRIORITY 50), criada para exercitar D22 (conflito em `MAP.mode`) e D17 (`AGRO.hz`, `crops`) | Regra sintética; o artigo deve dizer isso |
| D37 | `python -m dressgl.experimentos`: matriz 4 programas × 3 cenários → `results/metricas.csv`, `results/metricas.md` e `trace_<programa>__<cenario>.jsonl` | Tabela do Passo 6, que pode ser regenerada |
| D38 | `.gitignore` ignora só `results/trace_*.jsonl`; `ambiente.json`, `requirements-lock.txt`, `smoke*.txt` e `metricas.{csv,md}` ficam versionados | Os traces se regeneram com um comando. A tabela versionada é o retrato exato dos números citados no artigo |
| D39 | Cliente ZMQ do CoppeliaSim passa de dependência obrigatória para o extra `coppelia` | O núcleo (compilador, motor, simulador) usa só a biblioteca padrão; README e pyproject passam a concordar |
| D40 | `hospedeiro.Hospedeiro`: protocolo `leituras(quadro, plano) -> leituras`, já cumprido por `HospedeiroSimulado` | Contrato único para simulador, AgroView-SC e CoppeliaSim, sem mudar o comportamento de `executar` |
| D41 | As versões anteriores do AgroView-SC (`agroview_sc.py` em `Documents\FHO…\AgroView-SC`, OpenGL 3.3) estão obsoletas e não serão reaproveitadas. Corrige a D7, escrita antes de a reimplementação existir. O novo AgroView-SC fica em `src/agroview/`, com os extras `render` (NumPy) e `gui` (NumPy + PySide6); o núcleo `dressgl` não importa `agroview`, NumPy nem PySide6 | Código antigo incompatível com o motor atual; mantém a D39, garantida por `tests/test_nucleo_sem_numpy.py` |
| D42 | A renderização é feita em CPU com NumPy. Cada passo informa uma carga determinística (operações por pixel), usada nos testes, e um tempo medido com `perf_counter`, usado só na calibração e nas medições | Testes reproduzíveis que não dependem da máquina. Ameaça à validade: o tempo é de CPU, não de GPU. Aguarda confirmação do professor |
| D43 | hz no hospedeiro real é decimação, não média. Uma superfície com hz = h é desenhada inteira nos quadros em que q % round(60/h) == 0 e não é desenhada nos outros. A fase é fixa em q = 0, para ser determinística. Isso difere do D29, onde o custo é multiplicado por h/h_padrão em todo quadro | Consequência: a média pode ficar dentro do orçamento enquanto o pior_quadro_ms mostra picos. No artigo, a diferença é tratada como achado, não como erro |
| D44 | Ordem dos passos. Passos padrão na ordem de [custo].passos_padrao, menos os SUPPRESS. Cada INJECT entra BEFORE/AFTER da sua âncora, e a âncora pode ser outro passo injetado. Com várias injeções na mesma âncora, a de maior prioridade fica mais perto dela | Uma âncora ausente (suprimida) é erro do hospedeiro (ErroOrdem) |
| D45 | No B2, o HospedeiroAgroView associa os passos às superfícies assim: FPV = TerrainPass + CropInstancesPass; AGRO = SuitabilityPass (campo de aptidão colorido); MAP = SuitabilityPass com sobrepor=True quando mode = SUITABILITY e terreno quando NOMINAL. O FPV é sintético (mapa_altura com semente) até o B3 | O renderizador não fixa a associação; deixá-la no hospedeiro mantém o render.py independente da DSL |
| D46 | No hospedeiro medido, frame_budget é o custo do próprio quadro (cronômetro de quadro, V8), com os picos da decimação do D43. Não é feita média. O simulado continua usando o custo médio (hz/padrão, D29). Para comparar os dois, usam-se médias em janelas de 60 quadros | É o que o instrumento mede de fato. Ameaça à validade: o modelo médio esconde picos que podem disparar regras do tipo frame_budget > X |
| D47 | Complementa a D45: o pipeline da DSL (D44) desenha o FPV; um SuitabilityPass injetado desenha no FPV com sobrepor=True. MAP e AGRO são desenhados pelo hospedeiro fora do pipeline, conforme a D45 | A D45 não dizia onde vai um passo injetado; assim INJECT/SUPPRESS afetam a superfície principal, como no custo da D29 |
| D48 | `ms_por_carga` por nome de passo: mediana de ms/carga medida por `tools/calibrar_relogio.py` (540 quadros após 60 de aquecimento), gravada em `results/calibracao.toml`; passo sem coeficiente é `ValueError` | Ver D48 em Detalhes |
| D49 | Ponte com o CoppeliaSim síncrona, em modo stepping (`sim.setStepping`); substitui a thread da D26 | O motor continua síncrono e puro, e a física só avança quando a ponte pede: execução determinística. Tempo real fica fora do escopo |
| D50 | Um passo da física (50 ms, hz_sim = 20) a cada 3 quadros de 60 Hz; entre passos vale a última leitura (amostra e retém). O passo da cena precisa ser igual a 1/hz_sim | Casa a física com o relógio da estação sem interpolar |
| D51 | O CoppeliaSim fornece posição e tempo simulado. `terrain.below` vem de zonas retangulares da missão (a última zona vence); `drone.battery` é linear no tempo simulado | Ameaça à validade: bateria modelada, sem relação com o empuxo dos motores |
| D52 | Cada voo é gravado em `results/gravacao_<missao>.jsonl` (versionado) e pode ser repetido como `Cenario`, sem o CoppeliaSim | Os experimentos com física continuam reprodutíveis e testáveis sem o simulador |
| D53 | A gravação inclui o alvo e o solo sob o alvo (`alvo`, `solo_alvo`). `atraso_fisico_quadros` = 1º quadro com o drone na água − 1º quadro com o alvo na água | Separa o atraso da física (inércia do drone) do atraso do cooldown (`atraso_ativacao`), que parte da condição já avaliada sobre a posição real |
| D54 | `python -m ponte_coppelia.experimentos`: programas da D37 × gravações × {simulado, agroview com relógio por carga} → `results/metricas_coppelia.{csv,md}`, versionados | A gravação não depende do programa, então um voo alimenta todos os programas. Os experimentos da v1.0 não mudam |
| D55 | Zonas desenhadas por `tools/desenhar_zonas.py` a partir da missão (planos estáticos, não respondable); cena versionada em `cenas/agro_quadcopter.ttt` | Só visual: a zona que vale é a do TOML; o script evita divergência entre a cena e a missão |
| D56 | Ruído de percepção Gauss-Markov sobre gravações físicas, com parâmetros e hipótese fixados antes da execução | Ver D56 em Detalhes |
| D57 | Escopo da avaliação: um cenário excepcional (bateria em reserva sobre solo impróprio) em sete condições: operação normal, ativação com compensação, oscilação sintética, oscilação física, ruído no custo, ruído na percepção e composição de regras. Os outros cinco cenários da Seção III-A ficam como trabalho futuro | O roteiro da disciplina não fixa um número de cenários; os cinco restantes exigem telemetria que o modelo não declara |
| D58 | Gravação de referência de borda_agua: `results/gravacao_borda_agua.jsonl`. `results/rep1` e `results/rep2` são repetições a partir da cena `cenas/borda_agua.ttt` recém-aberta; `results/arquivo` guarda uma repetição sem reabrir a cena, mantida como evidência | rep1 = rep2 (mesmo hash); diferem da referência só em `pos`, no máximo 5,0e-8 m, e geram o mesmo trace. A repetição sem reabrir a cena divergiu |

## Detalhes

### D48 — Relógio por carga calibrado por passo

**Contexto.** No modo `relogio='carga'`, o `HospedeiroAgroView` convertia
carga em tempo com um único `ms_por_carga`. A calibração (540 quadros após
60 de aquecimento, CPU, NumPy; máquina em `results/ambiente.json`) mostrou
custos por unidade de carga muito diferentes (medianas): TerrainPass
≈ 50,8 ns (n = 1080, FPV e MAP), CropInstancesPass ≈ 87,8 ns (n = 540) e
SuitabilityPass ≈ 1,55 ns (n = 90). Com um coeficiente global calibrado nos
quadros comuns, o quadro com AGRO valeria ≈ 42 ms em vez de ≈ 5 ms.

**Decisão.** A carga continua sendo uma contagem estrutural (pixels ×
operações por pixel), independente da máquina. A conversão para tempo usa um
coeficiente por **nome de passo**, `ms_por_carga[passo]`: a mediana de
ms/carga gravada por `tools/calibrar_relogio.py` em `results/calibracao.toml`
e lida por `agroview.calibracao.carregar_calibracao`. A chave é o nome do
passo, e não o par (passo, superfície), porque o TerrainPass tem o mesmo custo
por unidade em FPV e MAP. Um número único continua aceito, por
compatibilidade. Um passo sem coeficiente é erro explícito (`ValueError`), sem
valor padrão.

**Alternativa rejeitada (B).** Reduzir o peso 81 do SuitabilityPass para que
a carga ficasse proporcional ao tempo. A carga passaria a depender da
implementação (vetorização, backend, máquina) e perderia o significado
estrutural.

**Consequências.** No modo carga, `frame_budget` é determinístico (dado o
arquivo de calibração) e previsto em ≈ 3,9 ms no quadro comum e ≈ 5,1 ms no
quadro com AGRO. Limitações: (i) o modelo é linear, sem termo fixo, então
passos com custo fixo relevante (CropInstancesPass) ficam subestimados quando
a carga cai; (ii) o SuitabilityPass foi calibrado só no AGRO, e as variantes
sobrepostas no MAP e no FPV (D45, D47) usam o mesmo coeficiente sem medição
própria; (iii) a calibração mede os passos, não o intervalo entre eles, que o
cronômetro de quadro (D46) inclui; (iv) a calibração vale para a máquina em
que foi feita.

### D56 — Ruído de percepção sobre gravações físicas

**Contexto.** Na C4 (D53–D55), `retencoes = 0` em todas as gravações e `dsl` = `dsl_sem_cooldown`.
A dinâmica do veículo filtra excursões curtas: em borda_agua, 1 das 4 excursões do alvo na água
(0,55 s) não chegou ao drone, e o menor intervalo entre trocas de `terrain.below` foi de 60 quadros (1,0 s).
O cooldown não chegou a ser exercitado.

**Decisão.** Simular erro na posição *percebida* sem alterar a física. Cada eixo (x, y) recebe um processo
Gauss-Markov de 1ª ordem com desvio estacionário `erro_pos_m` e constante de tempo `tau_s`, atualizado a
`hz_sensor` e mantido entre amostras nos quadros a 60 Hz. `terrain.below` é recalculado com as zonas da
missão a partir da posição percebida. A gravação guarda `pos_real` e `terrain.below_real`. O ruído depende
só de (semente, índice do quadro), então todos os programas recebem a mesma sequência e a comparação é pareada.

**Parâmetros fixados antes de rodar.** Base: borda_agua. `erro_pos_m` ∈ {0; 0,02; 0,05; 0,10} m;
`tau_s` = 0,5 s; `hz_sensor` = 10 Hz; sementes 1–10; programas `dsl` e `dsl_sem_cooldown`.
Hipótese: com erro > 0, `ativacoes(dsl_sem_cooldown) > ativacoes(dsl)` e `retencoes(dsl) > 0` na maioria
das sementes. Com erro = 0, os resultados devem ser idênticos aos de borda_agua na C4 (verificação de sanidade).
Os parâmetros não serão ajustados depois de ver os resultados; qualquer mudança vira uma nova decisão.

**Limitações.** Cena em escala reduzida (campo de 5 m). Erros não calibrados contra um receptor específico.
Ruído só em x e y. A classificação do solo é perfeita, dada a posição.

**Resultado.** Com erro = 0, as 10 sementes reproduziram a C4 (6 trocas, 3 ativações, 0 retenções), e a verificação de sanidade passou.
Pareando as sementes, `dsl_sem_cooldown` ativou mais que `dsl` em 3/10 (σ = 0,02 m), 6/10 (0,05 m) e 7/10 (0,10 m),
sem nenhuma semente em sentido contrário (teste do sinal unilateral: p = 0,125; 0,016; 0,008). A diferença máxima foi de
3 ativações. `retencoes(dsl) > 0` em 30/30 sementes com ruído (faixas 4–24, 4–29, 13–38).
A hipótese se confirma em σ = 0,05 e 0,10 m e falha em σ = 0,02 m na primeira parte (3/10 não é maioria).
Os parâmetros não foram alterados depois dos resultados.
| D59 | `numpy` entra no extra `dev` (o pacote continua sem dependências obrigatórias; o compilador e o simulador usam só a biblioteca padrão). O teste de regressão do `metricas_coppelia.csv` (~1 min) recebe o marcador `lento`, sai do `pytest -q` padrão e é pulado se faltar `numpy`. `--strict-markers` ativado | Um clone novo com `pip install -e ".[dev]"` falhou por falta de `numpy`, que só estava no `.venv` local. Rodar `python -m pytest -q -m lento` antes de commitar mudanças em `results/`, `src/ponte_coppelia` ou `src/agroview` |
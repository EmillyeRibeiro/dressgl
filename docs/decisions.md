# Registro de decisões

| # | Decisão | Motivo |
|---|---|---|
| D1 | Artigo, README e mensagens de erro em português; palavras-chave da DSL em inglês | Padrão da disciplina; herança do BDD/DRESS-ML |
| D2 | Analisadores léxico e sintático escritos à mão, sem gerador | Tabela II da Etapa 1 |
| D3 | Unidade incorporada ao literal: NUM (ws? UNIDADE)?, ws = espaço/tab | Linguagem léxica regular; viabiliza V2 |
| D4 | Comentário com `#`; enumerados em CAIXA_ALTA | Convenções léxicas; confirmada (testes de lexer e D11 dependem dela) |
| D5 | Erro léxico gera token ERRO e a varredura continua | Relatar todos os erros de uma vez |
| D6 | `referencia = IDENT ["." IDENT] \| alvo "." IDENT` | Aceitar `frame_budget`; continua LL(1) |
| D7 | AgroView-SC reimplementado (PySide6/NumPy); Listagem 1 vira baseline | Código antigo descartado |
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
+| D22 | Composição: todas as regras ativas são aplicadas, da maior para a menor prioridade (sem prioridade = por último; empate = ordem no fonte). SET no mesmo alvo segue D17 (numérico: mínimo; booleano: conjunção); só SET enumerado com valores diferentes e INJECT/SUPPRESS do mesmo passo usam "vence a primeira na ordem", com a outra registrada como conflito. SCALE no mesmo recurso: menor fator. HIGHLIGHT/MARK: união sem repetição | O resultado não depende da ordem de ativação e é idempotente; conflitos ficam rastreáveis (P7); coerente com D14/D17 |
| D23 | SCALE resolution multiplica a escala linear da superfície (custo de pixels proporcional ao fator ao quadrado); SCALE instances multiplica o número de instâncias desenhadas | Mesma semântica que view.scale lido no ASSERT |
| D24 | Cooldown: depois de ativar ou desativar, uma regra só pode mudar de estado de novo após `cooldown` quadros; a mudança pedida antes disso fica "retida" e vai para o trace | Histerese contra oscilação (flicker) |
| D25 | O ASSERT de uma regra aplicada no quadro t é verificado com as leituras do quadro t+1, que medem o efeito do plano de t. Uma violação é registrada e não desfaz a regra | Monitoramento em execução sem realimentação escondida |
| D26 | Ponte com o CoppeliaSim: telemetria lida via ZMQ em thread separada; o motor recebe a última leitura completa e é síncrono e puro | Motor testável sem simulador |
| D27 | Custo estimado por ação fica no hospedeiro (simulado ou real), não no motor | O motor decide; quem mede é o hospedeiro |
| D28 | Hospedeiro simulado determinístico: cada cenário é um TOML em `examples/cenarios/` com trechos de entradas por quadro (constante ou rampa `{de, ate}`; trechos posteriores sobrepõem os anteriores). Ruído gaussiano opcional, com semente fixa por quadro | Experimentos reproduzíveis: o mesmo cenário gera o mesmo trace |
| D29 | Custo de quadro modelado: `base + Σ(passos executados) custo_passo × fração_instâncias + Σ(superfícies habilitadas) custo_sup × escala² × hz/hz_padrão`, com parâmetros em `[custo]` no `agroview.toml`. Passos executados = padrão − SUPPRESS + INJECT. O hospedeiro aplica o plano de t e produz as leituras de t+1 (D25, D27) | Mede o efeito das ações sem GUI; no artigo, números calibrados à mão, modelados e não medidos |
| D30 | Trace em JSON Lines (`results/trace_<cenario>.jsonl`): um `Registro` por linha, com as leituras e a condição de cada regra no quadro. Tuplas viram listas; chaves viram `"SUP.attr"` | `grep` por quadro; leitura simples com `json`/pandas (P7) |
| D31 | Métricas do trace: % de quadros acima do orçamento, pior quadro, ativações/desativações, retenções, violações de ASSERT, conflitos, atraso de ativação (médio/máx.) | Base da comparação DSL × baseline (Passo 6) |
| D32 | Configuração em vigor = padrão do atributo substituído pelo plano do quadro; ao desativar, volta ao padrão. Padrão: `valores` → maior; `enum` → primeiro; `bool` → true. `view:SUP.scale` inclui o fator de SCALE resolution | Plano recalculado a cada quadro (D19, D22); o nominal é o estado de maior qualidade |
| D33 | Baseline = a regra da Listagem 3 sem as compensações (sem `SET AGRO.hz` e sem `SCALE`), com o mesmo GIVEN/WHEN/ASSERT (`baseline_sem_compensacao.dgl`) | Isola o efeito das compensações. Ameaça à validade: baseline construído pelos autores, não é uma implementação imperativa independente |
| D34 | Cenários extras: `listagem3_ruido` (σ = 0,5 ms, semente 42) e `oscilacao` (bateria alternando 19/17 % sobre água) | Robustez a ruído; comportamento do cooldown |
| D35 | Ablação `dsl_sem_cooldown`: mesmo fonte, `cooldown_frames = 0`, aplicada no script | Mede o custo/benefício do cooldown (oscilação × atraso) |
| D36 | `multiplas_regras.dgl`: Listagem 3 + `EconomiaBateria` (PRIORITY 50), criada para exercitar D22 (conflito em `MAP.mode`) e D17 (`AGRO.hz`, `crops`) | Regra sintética; o artigo deve dizer isso |
| D37 | `python -m dressgl.experimentos`: matriz 4 programas × 3 cenários → `results/metricas.csv`, `results/metricas.md` e `trace_<programa>__<cenario>.jsonl` | Tabela do Passo 6, que pode ser regenerada |
| D38 | `.gitignore` ignora só `results/trace_*.jsonl`; `ambiente.json`, `requirements-lock.txt`, `smoke*.txt` e `metricas.{csv,md}` ficam versionados | Os traces se regeneram com um comando. A tabela versionada é o retrato exato dos números citados no artigo |
# Manual da linguagem DRESS-GL

Versão do processador: 0.1.0. Este manual descreve o que o código atual aceita
e faz. As decisões de projeto citadas como Dn estão em
[`decisions.md`](decisions.md).

## 1. Visão geral

Um programa DRESS-GL é um arquivo de texto `.dgl`, em UTF-8 (o BOM é
aceito), com no máximo uma `POLICY` e qualquer número de `RULE`s, em qualquer
ordem.

- A `POLICY` define o orçamento de quadro e o `cooldown`.
- Cada `RULE` diz **quando** agir (`GIVEN`), **onde** no grafo de
  renderização (`WHEN`), **o que** fazer (`THEN`) e **qual garantia** deve
  valer depois (`ASSERT`).

A linguagem não tem laços, recursão, funções, variáveis nem aritmética. Isso é
deliberado: todo programa termina, e o trabalho por quadro é limitado pelo
tamanho do programa.

Os nomes que um programa pode usar (superfícies, passos, telemetria) não são
declarados no `.dgl`. Eles vêm do **modelo do hospedeiro**,
`modelo/agroview.toml` (Seção 9).

## 2. Léxico

### 2.1 Espaços e comentários

Espaços, tabulações e quebras de linha separam *tokens*. `#` inicia um
comentário que vai até o fim da linha.

### 2.2 Palavras

Uma palavra começa por letra ASCII ou `_` e continua com letras, dígitos ou
`_`. Ela é classificada nesta ordem:

1. **Palavra reservada** (maiúsculas e minúsculas importam):
   `POLICY RULE PRIORITY GIVEN WHEN THEN ASSERT END AND OR NOT IN BEFORE AFTER
   AROUND SET SCALE BY INJECT SUPPRESS HIGHLIGHT WITHIN MARK STALE ARGMAX ARGMIN
   view pass instances resolution budget reserve cooldown`
2. **Booleano:** `true`, `false`.
3. **Enumerado:** começa por maiúscula e só contém maiúsculas, dígitos e `_`.
   Exemplos: `WATER`, `STANDING_CROP`, `P`.
4. **Identificador:** qualquer outra palavra. Exemplos: `drone`,
   `SafeSetdownAssist`.

Consequências práticas:

- Nomes de regra e de política devem ser identificadores. Use **PascalCase**
  (`PerdaGps`). `GPS_LOSS` ou `P` são enumerados e geram erro sintático.
- Letras acentuadas não são aceitas: `bateria_mínima` gera erro léxico no `í`.
- Uma palavra reservada não pode ser nome de atributo. Por exemplo,
  `view "FPV".resolution` é erro sintático.

### 2.3 Números e unidades

Um número é uma sequência de dígitos com parte decimal opcional (`16.67`).
Não há sinal: `-5` gera erro léxico no `-`. `.5` e `5.` não são números
válidos; escreva `0.5` e `5`.

Uma unidade pode vir colada ao número ou depois de espaços ou tabulações, e
passa a fazer parte do literal:

| Unidade | Significado |
|---|---|
| `ms` | milissegundos |
| `Hz` | hertz |
| `%` | porcentagem |
| `m` | metros |
| `m/s` | metros por segundo |
| `frames` | quadros |

`10 frames`, `10frames` e `10	frames` são o mesmo literal. Em `10 mode`, porém,
`mode` não é unidade: o resultado é o número 10 seguido do identificador
`mode`.

### 2.4 Cadeias

Uma cadeia vai entre aspas duplas, na mesma linha, sem sequências de escape:
`"TerrainPass"`.

### 2.5 Operadores e pontuação

Operadores: `<  <=  >  >=  ==  !=  =`. Pontuação: `;  ,  .  {  }  (  )`.

### 2.6 Erros léxicos

Um caractere desconhecido ou uma cadeia sem fechamento gera um diagnóstico
`linha:coluna: erro léxico: ...`. A varredura continua, para que todos os
erros apareçam de uma vez.

## 3. Política (`POLICY`)

```text
POLICY AgroViewSC {
  budget   = 16.67 ms;     # obrigatório; > 0
  reserve  =  2.00 ms;     # opcional; < budget
  cooldown =    10 frames; # opcional; inteiro
}
```

| Parâmetro | Unidade | Regras |
|---|---|---|
| `budget` | `ms` | obrigatório; positivo |
| `reserve` | `ms` | menor que `budget` |
| `cooldown` | `frames` | inteiro; sem `cooldown`, vale 0 |

Só pode haver uma `POLICY`, e nenhum parâmetro pode se repetir (C2). Um
programa sem `POLICY` compila, com `cooldown` igual a 0.

## 4. Regras (`RULE`)

```text
RULE Nome [PRIORITY n]
  GIVEN  condição
  WHEN   fase pass "Passo"
  THEN   ação; ação; ...
  [ASSERT condição]
END
```

- **Nome:** identificador único no programa (C2).
- **`PRIORITY`:** inteiro sem unidade. Uma prioridade maior vence; uma regra
  sem prioridade é aplicada por último.
- **`GIVEN`:** condição avaliada a cada quadro (Seção 5).
- **`WHEN`:** ponto de junção. A fase é `BEFORE`, `AFTER` ou `AROUND`, e o
  passo precisa existir no modelo.
- **`THEN`:** uma ou mais ações, **cada uma terminada por `;`** (Seção 6).
- **`ASSERT`:** contrato opcional (Seção 7).

## 5. Condições

### 5.1 Átomos

Todo átomo compara uma referência com uma constante. A referência fica sempre
à esquerda, e não há comparação entre duas referências:

```text
drone.battery < 18 %
terrain.below IN { WATER, STANDING_CROP }
view "MAP".mode == SUITABILITY
```

### 5.2 Referências

| Forma | Consulta | Exemplo |
|---|---|---|
| `nome` ou `objeto.campo` | telemetria do modelo | `frame_budget`, `drone.battery` |
| `view "SUP".atributo` | atributo de superfície (configuração em vigor) | `view "FPV".scale` |
| `pass "P".atributo` | rejeitado (V1): o modelo não declara atributos de passo | — |

### 5.3 Conectivos e precedência

`NOT` > `AND` > `OR`, com associação à esquerda. Parênteses mudam o
agrupamento. `NOT` se aplica a um único átomo ou a uma expressão entre
parênteses; `NOT NOT x` não é aceito, escreva `NOT (NOT x)`.

```text
GIVEN drone.battery < 10 % OR drone.battery > 90 % AND terrain.below == WATER
# lido como: battery < 10 % OR (battery > 90 % AND below == WATER)
```

### 5.4 Regras de tipo

| Domínio no modelo | Operadores | Literal aceito |
|---|---|---|
| numérico | todos | número **com a unidade exata do modelo** (V2), dentro de `min`/`max` (V3) |
| enumerado | `==`, `!=`, `IN` | valor do enumerado (V3) |
| booleano | `==`, `!=` | `true` ou `false` |
| campo escalar | nenhum | só pode aparecer em `HIGHLIGHT` (V3) |

Não há conversão de unidades: um atributo em `ms` não aceita um literal em
`s` nem sem unidade. A lista de `valores` de um atributo restringe o que um
`SET` pode atribuir, mas não o que uma comparação pode usar.

### 5.5 Satisfatibilidade

Um `GIVEN` que nunca pode ser verdadeiro no domínio do modelo é rejeitado
(V7). Exemplo: `drone.battery < 10 % AND drone.battery > 20 %`. Se houver
combinações demais para decidir (mais de 100 000), o compilador emite apenas
um aviso.

## 6. Ações

| Ação | Forma | Regras |
|---|---|---|
| Atribuir | `SET view "SUP".atributo = literal;` | atributo existente (V1); tipo, unidade e valor do modelo (V2, V3); não desativar superfície `CRITICA` (V4) |
| Escalar instâncias | `SCALE instances "nome" BY fator;` | instâncias declaradas no modelo (V1) |
| Escalar resolução | `SCALE resolution "SUP" BY fator;` | superfície existente (V1) |
| Injetar passo | `INJECT pass "P" BEFORE "Ancora";` ou `AFTER` | passos existentes (V1) |
| Suprimir passo | `SUPPRESS pass "P";` | passo existente (V1) |
| Destacar extremo | `HIGHLIGHT ARGMAX campo [WITHIN raio m];` ou `ARGMIN` | campo escalar (V3); raio em `m` (V2) e diferente de zero (V3) |
| Marcar obsoleto | `MARK view "SUP" STALE;` ou `MARK pass "P" STALE;` | alvo existente (V1) |

Regras do fator de `SCALE`: é adimensional (V2) e fica no intervalo (0, 1]
(V3). A linguagem só reduz carga.

`SET pass ...` é rejeitado (V1). `SCALE resolution` multiplica a escala linear
da superfície; o custo de pixels cai com o quadrado do fator (D23).

### 6.1 Pontos de junção inválidos (V5)

O compilador rejeita, dentro de uma mesma regra:

- `WHEN` sobre um passo que a própria regra injeta;
- `WHEN AROUND` ou `WHEN AFTER` sobre um passo que a própria regra suprime
  (use `BEFORE`);
- `INJECT` de um passo relativo a ele mesmo;
- `INJECT` com âncora num passo que a própria regra suprime;
- dois `INJECT` na mesma fase e âncora, porque a ordem entre eles ficaria
  indefinida.

### 6.2 Conflitos de escrita (V6)

São rejeitados:

- dois `SET` com valores diferentes no mesmo atributo, dentro de uma regra;
- duas regras de **mesma prioridade**, que podem estar ativas ao mesmo tempo,
  escrevendo valores diferentes num atributo **enumerado**.

Atributos numéricos e booleanos não geram V6, porque se compõem pelo mínimo e
pela conjunção (Seção 8). Para resolver um V6, dê prioridades diferentes às
regras ou torne as condições mutuamente exclusivas.

## 7. Contratos (`ASSERT`)

O `ASSERT` descreve o efeito esperado das ações:

```text
ASSERT frame_budget <= 16.67 ms AND view "FPV".scale >= 0.75
```

- Ele pode usar atributos de `view` e telemetria **medida pelo hospedeiro**,
  isto é, com `instrumento` declarado no modelo, como `frame_budget`. Usar uma
  entrada sem instrumento, como `drone.battery`, é erro V8.
- Um `SET` da própria regra que contradiz o `ASSERT` é rejeitado (C1). Isso só
  é verificado para termos ligados por `AND` no nível externo.
- **Em execução:** o `ASSERT` de uma regra aplicada no quadro *t* é avaliado
  com as leituras do quadro *t+1*, que medem o efeito do plano de *t*. Uma
  violação é registrada no trace e não desativa a regra (D25).

## 8. Semântica de execução

A cada quadro, o motor:

1. verifica os `ASSERT`s das regras aplicadas no quadro anterior;
2. avalia o `GIVEN` de todas as regras;
3. ativa ou desativa regras, respeitando o `cooldown`. Depois de mudar de
   estado, uma regra só pode mudar de novo após `cooldown` quadros; uma mudança
   pedida antes disso fica **retida** e vai para o trace (D24);
4. compõe os efeitos das regras ativas num plano.

As regras são percorridas em ordem de prioridade decrescente; as sem
prioridade vêm por último, e empates são decididos pela linha no fonte. A
composição no mesmo alvo segue esta tabela:

| Efeito | Composição |
|---|---|
| `SET` numérico | mínimo |
| `SET` booleano | conjunção |
| `SET` enumerado | vence a primeira na ordem; conflito registrado |
| `SCALE` | menor fator |
| `INJECT`/`SUPPRESS` do mesmo passo | vence a primeira na ordem; conflito registrado |
| `HIGHLIGHT`, `MARK` | união sem repetição |

Um atributo que nenhuma regra ativa escreve volta ao **padrão**: o maior valor
de `valores`, o primeiro valor de `enum` ou `true` (D32).

O plano é recalculado a cada quadro. Se faltar uma leitura de que uma condição
depende, o motor lança `ErroExecucao` e não altera seu estado.

## 9. Modelo do hospedeiro (`modelo/agroview.toml`)

```toml
[superficies.FPV]
criticidade = "CRITICA"                        # CRITICA, ALTA, MEDIA ou BAIXA
atributos.enabled = { tipo = "bool" }
atributos.scale   = { valores = [0.5, 0.75, 1.0] }
atributos.hz      = { unidade = "Hz", valores = [15, 30, 60] }

[passos]
nomes = ["TerrainPass", "SuitabilityPass", "CropInstancesPass"]

[instancias]
crops = { passo = "CropInstancesPass" }        # o passo precisa existir

[telemetria]
"drone.battery"       = { unidade = "%", min = 0, max = 100 }
"terrain.below"       = { enum = ["WATER", "STANDING_CROP", "BARE_SOIL"] }
"terrain.suitability" = { campo_escalar = true }
frame_budget          = { unidade = "ms", instrumento = "cronometro_quadro" }

[custo]                                        # usado só pelo simulador
base_ms       = 2.0
passos_padrao = ["TerrainPass", "CropInstancesPass"]
passos        = { TerrainPass = 3.0, SuitabilityPass = 3.0, CropInstancesPass = 4.0 }
superficies   = { FPV = 3.0, MAP = 1.0, AGRO = 2.0 }
```

### 9.1 Domínios

| Domínio | Forma | Observação |
|---|---|---|
| booleano | `{ tipo = "bool" }` | |
| enumerado | `{ enum = [...] }` | valores em CAIXA_ALTA |
| numérico | `{ unidade = "...", valores = [...], min = ..., max = ... }` | todos os campos são opcionais; a unidade deve ser uma da Seção 2.3 |
| campo escalar | `{ campo_escalar = true }` | |

Qualquer domínio pode declarar `instrumento = "nome"` (V8).

### 9.2 Validação ao carregar

O modelo é validado quando é carregado:

- nomes de atributo e partes das chaves de telemetria precisam ser
  identificadores DRESS-GL: minúsculas e nenhuma palavra reservada;
- uma chave de telemetria tem no máximo um ponto;
- os valores de `criticidade` e de `unidade` precisam ser conhecidos.

### 9.3 Exigências do simulador

- todo passo tem custo em `[custo].passos`;
- `passos_padrao` é um subconjunto de `[passos]`;
- todo instrumento se chama `cronometro_quadro`;
- todo atributo de superfície tem `valores`, `enum` ou `tipo = "bool"`, para
  ter um padrão.

O custo de quadro modelado (D29) é:

```text
custo = base_ms
      + Σ (passos executados) custo_passo × fração_de_instâncias
      + Σ (superfícies habilitadas) custo_superfície × escala² × hz / hz_padrão
```

Passos executados = padrão − suprimidos + injetados.

## 10. Cenários (`examples/cenarios/*.toml`)

```toml
nome     = "listagem3"   # opcional (padrão: nome do arquivo)
quadros  = 300           # obrigatório
semente  = 42            # opcional (padrão 0)
ruido_ms = 0.0           # desvio do ruído gaussiano no custo (padrão 0)

[[trechos]]
inicio = 0
fim    = 299
"drone.battery" = { de = 40.0, ate = 10.0 }   # rampa linear de 'inicio' a 'fim'

[[trechos]]
inicio = 180
fim    = 259
"terrain.below" = "WATER"                     # constante; sobrepõe trechos anteriores
```

Regras:

- Todo quadro precisa ter valor para todas as **entradas**: as chaves de
  telemetria que não são instrumento nem campo escalar.
- Os valores são validados contra `enum`, `min` e `max`, e os trechos precisam
  caber em `0 .. quadros-1`.
- Instrumentos, como `frame_budget`, não podem aparecer no cenário: quem os
  mede é o hospedeiro.

Com o mesmo cenário e a mesma semente, o trace é sempre idêntico.

## 11. Trace (`results/trace_*.jsonl`)

O trace tem uma linha JSON por quadro, com os campos:

| Campo | Conteúdo |
|---|---|
| `quadro` | número do quadro |
| `ativas` | regras ativas, em ordem de prioridade |
| `ativadas`, `desativadas` | mudanças de estado no quadro |
| `retidas` | mudanças adiadas pelo `cooldown` |
| `conflitos` | lista de `{alvo, vencedora, perdedora}` |
| `violacoes` | lista de `{regra, quadro}`; `quadro` é o quadro cujo plano violou o `ASSERT` |
| `plano` | `sets`, `escalas`, `injecoes`, `supressoes`, `destaques`, `marcas` |
| `condicoes` | valor do `GIVEN` de cada regra |
| `leituras` | telemetria e configuração em vigor (`view:SUP.attr`) |

As métricas do simulador e dos experimentos (D31) são calculadas a partir do
trace: % de quadros acima do orçamento, pior quadro, ativações, desativações,
retenções, violações, conflitos e atraso de ativação.

## 12. Referência de diagnósticos

Formato: `linha:coluna: <nível> <fase>: mensagem`.

| Código | Significado |
|---|---|
| erro léxico | caractere inesperado; cadeia não terminada |
| erro sintático | *token* inesperado; `PRIORITY` não inteira ou com unidade |
| V1 | referência indefinida |
| V2 | unidade incompatível |
| V3 | valor fora do domínio |
| V4 | superfície `CRITICA` desativada |
| V5 | ponto de junção inválido ou ambíguo |
| V6 | conflito de escrita |
| V7 | regra inalcançável (ou aviso, se indecidível) |
| V8 | `ASSERT` sem instrumento |
| C1 | `SET` contradiz o `ASSERT` da própria regra |
| C2 | `POLICY` duplicada, parâmetro repetido, `POLICY` sem `budget`, regra duplicada |

Após um erro sintático, a análise recomeça no próximo `POLICY` ou `RULE`, de
modo que um `END` esquecido produz um único erro.

## 13. Receitas

**Economizar com bateria baixa, sem conflitar com regras de prioridade maior:**

```text
RULE EconomiaBateria PRIORITY 50
  GIVEN drone.battery < 25 %
  WHEN  AROUND pass "TerrainPass"
  THEN  SET view "AGRO".hz = 1 Hz;
        SCALE instances "crops" BY 0.5;
END
```

**Suprimir um passo antes que ele execute** (o único uso de `SUPPRESS` do
próprio passo de junção aceito por V5):

```text
RULE SemCulturas
  GIVEN terrain.below == WATER
  WHEN  BEFORE pass "CropInstancesPass"
  THEN  SUPPRESS pass "CropInstancesPass";
END
```

## 14. Limitações conhecidas

- Identificadores só em ASCII; não há números negativos, escapes em cadeias
  nem conversão de unidades.
- Atributos de passo não existem no modelo, então `pass "P".x` é sempre V1.
- O hospedeiro simulado ignora a ordem dos passos (pontos de junção e âncoras
  de `INJECT`), `HIGHLIGHT` e `MARK`. Esses efeitos são verificados e
  compilados, mas ainda não têm efeito em execução.
- V4 só protege contra a desativação de superfícies críticas, não contra
  reduções de escala ou de frequência.
- `python -m dressgl.simulador` não formata erros de compilação; use antes
  `dressgl.semantica`.
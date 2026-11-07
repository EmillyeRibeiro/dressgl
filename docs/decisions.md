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

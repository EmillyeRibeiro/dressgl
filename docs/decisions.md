# Registro de decisões

| # | Decisão | Motivo |
|---|---|---|
| D1 | Artigo, README e mensagens de erro em português; palavras-chave da DSL em inglês | Padrão da disciplina; herança do BDD/DRESS-ML |
| D2 | Analisadores léxico e sintático escritos à mão, sem gerador | Tabela II da Etapa 1 |
| D3 | Unidade incorporada ao literal: NUM (ws? UNIDADE)?, ws = espaço/tab | Linguagem léxica regular; viabiliza V2 |
| D4 | Comentário com `#`; enumerados em CAIXA_ALTA | Convenções léxicas (aguardando confirmação) |
| D5 | Erro léxico gera token ERRO e a varredura continua | Relatar todos os erros de uma vez |
| D6 | `referencia = IDENT ["." IDENT] \| alvo "." IDENT` | Aceitar `frame_budget`; continua LL(1) |
| D7 | AgroView-SC reimplementado (PySide6/NumPy); Listagem 1 vira baseline | Código antigo descartado |
| D8 | CoppeliaSim 4.10.0 Edu (Bullet 2.78) fornece telemetria via ZMQ (porta 23000) | Indicação do professor |
| D9 | Modelo do hospedeiro em `modelo/agroview.toml`, lido pelo compilador e pelo host | Desacoplar a linguagem da parte gráfica |
| D10 | Códigos V1–V8 conforme semantica.py (numeração provisória até conferir com o artigo) | Rastreabilidade entre artigo, código e testes |
| D11 | Nomes de regra/política em PascalCase; o modelo rejeita atributos que a linguagem não consegue escrever | Consequência da classificação léxica de ENUM e palavras reservadas |
| D12 | Unidades sem conversão: a unidade do literal deve ser exatamente a do modelo | Simplicidade; evita erros de 1000× entre ms e s |
| D13 | Fator de SCALE em (0, 1] | A linguagem só degrada carga; aumentar competiria com o orçamento |
| D14 | V5 só analisa termos ligados por AND; V6 é aviso | Decidir OR/NOT ou a sobreposição de GIVEN exigiria resolver satisfatibilidade |
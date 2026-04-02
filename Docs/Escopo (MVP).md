Documento de Visão e Escopo (MVP)

Projeto: Sistema de Gestão Financeira Pessoal Base Zero - "Finance Flow"
Stack Tecnológica: Python, Django, SQLite, HTML/CSS (Tailwind/Bootstrap), PWA (Progressive Web App)


1. Visão Geral do Produto

Um sistema financeiro pessoal feito sob medida, focado na metodologia de Orçamento Base Zero (OBZ) aliada ao rigor de um Plano de Contas contábil. O diferencial do sistema é a flexibilidade de ciclos temporais (não amarrados a meses civis), o macro-planejamento estratégico baseado em dados históricos e a injeção inteligente de despesas fixas e futuras. O objetivo é garantir controle absoluto de cada centavo, alocação consciente de recursos e rastreabilidade total do patrimônio e investimentos.


2. Escopo Funcional (Funcionalidades do MVP)

2.1. Gestão de Ciclos Dinâmicos (O Motor Base Zero)

Abertura de Ciclo: Criação de um novo ciclo definindo data_inicio e data_fim (semanal, quinzenal, mensal, etc.).

Projeção e Acompanhamento: Ao iniciar o ciclo, o usuário é direcionado para um painel que consolida as entradas, saídas, investimentos e transferências previstas para o período. O grande diferencial desta tela é a comparação em tempo real com o Orçamento do Mês: o sistema soma automaticamente o que já foi realizado em ciclos anteriores (dentro do mesmo mês) com a projeção do ciclo atual, confrontando esse total com o teto/chão do orçamento mensal estabelecido. O usuário não é obrigado a alocar 100% da receita de antemão; ele utiliza este painel de forma fluida para projetar e ajustar seus números, acompanhando claramente a margem disponível antes de estourar a meta mensal.

Ciclos Híbridos (Transição de Mês): Quando um ciclo se inicia em um mês e termina em outro (ex: 28 de março a 4 de abril), o painel renderiza blocos de acompanhamento distintos. As transações consumirão estritamente o orçamento do seu respectivo mês de competência (baseado na data de vencimento).

Fechamento e Reconciliação: Ao encerrar o ciclo, o sistema exige:

Se houver saldo positivo: Destinar o valor (ex: enviar para um "Cofre" ou rolar para o próximo ciclo).

Se houver saldo negativo: Registrar o resgate de uma conta de reserva para cobrir o rombo.

Rollover de Pendências: Despesas não pagas até o fim do ciclo não travam o fechamento. Elas podem ter sua data reagendada (empurradas para o futuro), sendo capturadas automaticamente pelo próximo ciclo que englobar a nova data.

Congelamento: Após zerado e validado, o ciclo é marcado como "Fechado" e vira histórico imutável.

2.2. Estrutura Contábil (Plano de Contas)

Hierarquia de Níveis: Substituição do modelo simples de "categorias" por uma estrutura em árvore (ex: 1. Receitas -> 1.1. Ativas -> 1.1.1. Salário | 2. Despesas -> 2.1. Moradia -> 2.1.1. Aluguel | 3. Investimentos -> 3.1. Pessoal | 4. Transferências).

Natureza das Contas: Classificação clara entre Receitas, Despesas, Investimentos, Transferências. Nota: Lançamentos com natureza de "Transferência" entre contas próprias não afetam o consumo do orçamento mensal nem os indicadores de gastos.

Base para DRE: Estrutura desenhada para permitir a geração futura de um Demonstrativo de Resultados do Exercício (DRE) Pessoal.

2.3. Automação e Agendamentos

Contas Fixas (Recorrentes): Cadastro de despesas/receitas atreladas a um dia_vencimento. Suporta Valores Exatos (ex: assinatura de software, mensalidade) e Valores Estimados (ex: conta de energia ou água, onde o sistema injeta a estimativa no ciclo e o usuário ajusta para o valor real exato apenas no ato do pagamento).

Lançamentos Futuros (Pontuais/Parcelados): Cadastro de transações com uma data_vencimento exata e finita (ex: 15/10/2026).

Gatilho de Injeção: Ao abrir um ciclo, uma rotina Python verifica quais Contas Fixas e Lançamentos Futuros caem dentro do intervalo de datas do ciclo atual e insere-os automaticamente como pendentes.

2.4. Controle de Contas e Cartões de Crédito

Espelho de Saldos: Cadastro de contas correntes, carteiras e corretoras.

Reconciliação Bancária & Importação (OFX/CSV): Recurso para importar extratos bancários. O sistema cruza os dados do arquivo com os lançamentos manuais já existentes para marcação automática (checkbox de efetivação), garantindo que o saldo do sistema bata exatamente com o banco de forma ágil.

Análise Individual de Faturas: Acompanhamento em tempo real dos gastos alocados em cada cartão. O usuário tem total flexibilidade: pode registrar uma compra de cartão no ciclo atual (se desejar adiantar o pagamento) ou cadastrá-la nos Lançamentos Futuros (para que o valor afete o orçamento apenas no mês de vencimento da fatura).

Visão Consolidada de Faturas: Um painel que unifica todas as faturas abertas de diferentes cartões, permitindo visualizar o montante total da dívida de crédito e o seu impacto no orçamento.

2.5. Módulo de Investimentos

Gestão de Ativos e Rendimentos: Cadastro de ordens de compra, venda e o registro contínuo de rendimentos/dividendos recebidos.

Isolamento de Patrimônio: O "universo" de investimentos é estritamente separado do fluxo de caixa diário. Rendimentos e proventos caem automaticamente no saldo da carteira para reinvestimento, sem poluir a tabela de movimentações e o ciclo do orçamento, a menos que o usuário acione explicitamente o resgate (toggle) desse valor para sua conta pessoal.

Posição Atual e Relatórios: Visualização detalhada dos valores e quantidades atuais em carteira, filtrável por período.

Suporte à Decisão: Base de dados preparada para rodar algoritmos em Python que analisem a rentabilidade e sugiram rebalanceamento.

2.6. Macro-Planejamento Estratégico e Análise

Orçamento Sazonal (Baseado em Dados): Painel de planejamento para definir limites de gastos e metas de investimento mês a mês (e não limites fixos anuais). O sistema utiliza inteligência de dados para sugerir valores baseando-se na média de gastos históricos do mesmo período.

Cofres (Metas Financeiras): Envelopes virtuais com barras de progresso, alimentados pelo macro-planejamento mensal e pelos excedentes de fechamentos de ciclo.

Simulador de Impacto: Ferramenta que projeta o impacto de uma nova dívida/parcelamento nos orçamentos dos próximos meses.

Termômetro do Ciclo (Burn Rate): Indicador visual que cruza o tempo decorrido do ciclo atual com a verba gasta nas contas (ignorando transferências).

2.7. Dashboard e Lançamentos Avançados

Interface Minimalista: Formulário de lançamento rápido para os gastos do dia a dia.

Rateio de Transações (Transação Pai/Filho): Permite que uma única saída no extrato bancário (Transação Pai) seja dividida em múltiplas categorias contábeis (Transações Filhas). O banco concilia o valor total (Pai), enquanto o orçamento debita apenas as frações detalhadas (Filhas).

Uso de Tags (Projetos): Possibilidade de adicionar #tags transversais aos lançamentos (ex: #viagem_bahia), permitindo rastrear despesas de um mesmo contexto independentemente de suas categorias no Plano de Contas.

Anexos de Comprovantes: Opção de anexar arquivos (PDF/Imagens) diretamente no registro da transação (ex: notas fiscais, garantias).

Visão do Ciclo: Tabela central exibindo as colunas vitais (Planejado/Teto, Realizado e Disponível), agrupadas segundo a hierarquia do Plano de Contas com a opção de expandir e retrair níveis.

Lançamentos Extra-Ciclo (Receitas Extraordinárias): Funcionalidade para registrar valores inesperados à parte do ciclo atual, permitindo definir o seu destino imediato (ex: transferir para investimentos) sem alterar a projeção do ciclo em andamento.



4. Arquitetura e Modelagem de Dados Base (Dicionário)

4.1. Estrutura Base e Cadastros

Tabela PlanoConta (Estrutura Contábil): A hierarquia financeira (NOME, TIPO_NATUREZA, CONTA_PAI_ID).

Tabela ContaBancaria: (NOME, TIPO, SALDO_INICIAL, LIMITE_CREDITO, DIA_VENCIMENTO, DIA_FECHAMENTO).

Tabela Destinos (Tags): (NOME, ID_PLANOCONTA, COR_HEXADECIMAL).

4.2. Motor de Ciclos e Planejamento

Tabela Ciclo: (DATA_INICIO, DATA_FIM, STATUS, SALDO_INICIAL_PROJETADO, SALDO_FINAL_REALIZADO).

Tabela MacroOrcamento: (MES_ANO, PLANO_CONTA_ID, VALOR_TETO).

4.3. Automação e Agendamentos

Tabela TransacaoRecorrente (Contas Fixas): Regras de injeção contínua.

Campos: DESCRICAO, TIPO (Receita, Despesa, Transferência), PLANO_CONTA_ID, CONTA_BANCARIA_ID, DESTINO_TAGS, FORMATO_PAGAMENTO, DIA_VENCIMENTO, VALOR_BASE, TIPO_VALOR (Exato ou Estimado), STATUS_ATIVA (Boolean).

Campos para Transferências: CONTA_DESTINO_ID (Opcional), COFRE_ID (Opcional).

Tabela LancamentoFuturo: Transações pontuais ou parceladas aguardando a data.

Campos: DESCRICAO, TIPO (Receita, Despesa, Transferência), PLANO_CONTA_ID, CONTA_BANCARIA_ID, DESTINO_TAGS, FORMATO_PAGAMENTO, COMPROVANTE (Arquivo/URL), DATA_VENCIMENTO, VALOR, PARCELA_ATUAL, TOTAL_PARCELAS. (Nota: Ao abrir um ciclo, o sistema lê esta tabela e gera uma cópia na tabela Movimentacao, alterando o status desta para "Injetado").

Campos para Transferências: CONTA_DESTINO_ID (Opcional), COFRE_ID (Opcional).

4.4. Tabela Principal: Movimentacao (Livro-Razão)

Centraliza todo o histórico. Usa o campo STATUS para separar o que é "rascunho do ciclo" do que é "histórico imutável".

Identificação & Datas: TIPO, VALOR,FORMATO_PAGAMENTO (PIX, Cartão, Boleto, etc.), DESCRICAO, COMPROVANTE(Arquivo/URL - Relação ManyToMany), DATA_PAGAMENTO, DATA_VENCIMENTO, DATA_REGISTRO (Auditoria).

Relacionamentos: PLANO_CONTAS_ID, CONTA_BANCARIA_ID, CICLO_ID(FK Opcional), LANCAMENTO_PAI_ID (Split), LANCAMENTO_PAR_ID (Transferências), COFRE_ID, CONTA_DESTINO_ID.

Inteligência e Trava de Segurança: STATUS (Pendente, Efetivado, Reagendado, Validado/Congelado). Nota: Movimentações com status "Validado" são bloqueadas para edição em nível de banco de dados.

4.5. Módulo de Investimentos

Tabela Ativo: Cadastro dos papéis (TICKER, NOME, TIPO, SETOR).

Tabela Ordem: Registro de compras e vendas (ATIVO_ID, DATA_OPERACAO, TIPO_ORDEM, QUANTIDADE, PRECO_UNITARIO, TAXAS, TOTAL).

Tabela Rendimento: Dividendos e juros (ATIVO_ID, DATA_PAGAMENTO, VALOR_TOTAL, MES_ANO_REFERENCIA).


4.6. Metas Financeiras

Tabela Cofre: (NOME, VALOR_META, DATA_ALVO, SALDO_ATUAL, STATUS).


5. Fundamentos de Interface e UI/UX (Frontend)

O sistema adotará uma identidade visual moderna, minimalista e focada na imersão dos dados, inspirada no design de plataformas financeiras de vanguarda.

Fontes de inspiração: https://lp.pierre.finance/?r=0

https://www.framer.com/?utm_source=landbook&utm_medium=paid&dub_id=Gs09TGcQrdrGVTLq

5.1. Identidade Visual e Tematização

Dark Mode Nativo: Fundo escuro para reduzir fadiga visual e criar contraste dramático.

Paleta de Destaques (Neon/Vibrant): Cores vivas para dados financeiros e CTAs (Verde vibrante, roxo elétrico, vermelho luminoso para alertas).

5.2. Padrão Arquitetural Visual

Bento Box Layout: Organização em blocos/cards em vez de listas contínuas.

Bordas e Volumes: Cantos arredondados (border-radius alto).

Glassmorphism: Cards com fundo levemente translúcido e desfoque (backdrop-filter: blur).

5.3. Experiência Desktop (PWA)

Comportamento Nativo (Standalone): O aplicativo rodará em janela própria, sem a interface do navegador, idêntico a um software nativo (Notion/Spotify).


6. Arquitetura de Telas e Navegação (Templates)

A navegação será feita por uma Sidebar lateral, garantindo a clara separação entre a "operação em andamento" e o "histórico já validado", conforme a demanda de segurança dos dados.

6.1. Dashboard Principal (Home)

A "sala de comando". Focada em resumo rápido e acesso ágil ao ciclo vigente.

Componentes (Bento Box):

Saldo total consolidado (Visão de Caixa).

Widget do Ciclo Ativo (Status, dias restantes, Termômetro de Burn Rate colorido, Saldo Atual e Saldo final projetado).

Gráfico Donut/Mini-barra das 3 categorias que mais consumiram orçamento no mês.

Widget de Atalho Rápido para "Nova Transação" e "Transação Extra-Ciclo".

6.2. Cockpit do Ciclo Ativo (Operacional)

Tela dedicada exclusivamente às movimentações que estão em operação no momento.

Lista de Transações Ativas: Exibe apenas movimentações do ciclo vigente com status Pendente ou Efetivado (não congeladas).

Comparativo de Orçamento: Árvore do Plano de Contas cruzando o "Teto do Mês" com o "Previsto no Ciclo".

Fechamento: Botão para "Encerrar Ciclo", que altera o status de todas essas movimentações ativas para Validado/Congelado e as envia visualmente para o Livro-Razão.

6.2.1. Conciliação Bancária (Operacional)

Focalizada para caso haja alguma divergência de valores do saldo no sistema com o saldo do banco, então o usuário poderá importar o extrato do banco para o sistema comparar os dois e informar as divergências.

Upload/Reconciliação: Importação de OFX/CSV.

6.3. Livro-Razão / Histórico Geral (Auditoria)

A visão clássica, contendo a base de dados definitiva.

Interface: Tabela listando prioritariamente os registros com status Validado/Congelado de ciclos passados, garantindo que o histórico não se misture com a bagunça do ciclo operacional.

Filtros Avançados: Por Período, Conta, Tag, etc.

Funcionalidades Ocultas (Hover/Click): Ao clicar numa linha, expande-se o painel lateral (Drawer) exibindo a opção de Rateio (Split) e upload de Anexos (Comprovantes) - únicas operações permitidas para movimentações com status “congelado“.

6.4. Contas, Saldos e Faturas de Cartão

Visão gerencial de onde o dinheiro está fisicamente e do fluxo de crédito.

Cards de Contas e Cofres: Painel listando o saldo atual de cada conta corrente, corretora e o saldo acumulado em cada envelope de Meta (Cofre).

Gestão de Cartões de Crédito: Área dedicada para visualizar os limites, datas de fechamento e as faturas abertas e futuras. Permite projetar o impacto das faturas dos próximos meses.

6.5. Macro-Planejamento Sazonal

Grid no formato planilha (Plano de Contas vs. Meses do Ano) para definir os "Tetos Mensais" baseados na média histórica.

6.6. Central de Investimentos

Aba de Patrimônio (Gráficos), Aba de Rendimentos (com toggle de resgate para o orçamento) e Cadastro de Ativos.

6.7. Cadastros Base e Configurações

Gerenciamento da Árvore de Contas, Regras de Automação (Contas Fixas) e Destinos (Tags).
3. Roteiro Ágil de Desenvolvimento

Fase 1: Concepção e Backlog (Concluída)

[x] Definição das regras de negócio (Ciclos, Injeção, Base Zero, Plano de Contas).

[x] Delimitação do escopo do Produto Mínimo Viável (MVP).

[x] Inclusão de recursos avançados de mercado (Rateio Pai/Filho, OFX, Tags, Anexos).

[x] Criação deste documento base, com regras de negócio blindadas contra falhas de operação.

Fase 2: Arquitetura e Modelagem de Dados (Em Andamento)

[x] Definição do Dicionário de Dados Base (Entidades Principais).

[x] Mapeamento da Arquitetura de Telas (Views).

[ ] Setup inicial do projeto Django e ambiente virtual Python.

[ ] Escrita dos models.py refletindo as regras de negócio.

Fase 3: Sprints de Construção

Sprint 1 (Fundação): Criação dos Models, migrações para o SQLite e configuração do Django Admin para inserção manual de dados.

Sprint 2 (Inteligência): Desenvolvimento do algoritmo de abertura/fechamento de ciclos, injeção automática e cálculo de ciclos híbridos.

Sprint 3 (Interface e Execução): Construção das Views e Templates (HTML) para o Dashboard, Lançamentos (com Rateio e Anexos) e Termômetro. Configuração do PWA.

Sprint 4 (Planejamento e Extras): Desenvolvimento do Macro-Planejamento (orçamento sazonal), Simulador de Impacto e Módulo de Investimentos.

Fase 4: Validação e Testes

[ ] Testes unitários das lógicas de injeção de datas, rateios e hierarquia de contas.

[ ] Simulação de um ciclo completo (incluindo transição de mês) com cenários de rollover, sobra e falta de saldo.

[ ] Operação em paralelo (Homologação) com a planilha em Excel.
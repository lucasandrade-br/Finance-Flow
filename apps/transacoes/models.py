from django.db import models
from apps.core.models import ModeloBase


# ---------------------------------------------------------------------------
# Choices compartilhados entre TransacaoRecorrente, LancamentoFuturo e Movimentacao
# ---------------------------------------------------------------------------

class TipoTransacao(models.TextChoices):
    RECEITA = 'Receita', 'Receita'
    DESPESA = 'Despesa', 'Despesa'
    INVESTIMENTO = 'Investimento', 'Investimento'
    TRANSFERENCIA = 'Transferencia', 'Transferência'
    TRANSFERENCIA_ENTRADA = 'TransfEntrada', 'Transferência - Entrada'
    TRANSFERENCIA_SAIDA = 'TransfSaida', 'Transferência - Saída'


class FormatoPagamento(models.TextChoices):
    PIX = 'PIX', 'PIX'
    CARTAO = 'Cartao', 'Cartão'
    BOLETO = 'Boleto', 'Boleto'
    DINHEIRO = 'Dinheiro', 'Dinheiro'
    DEBITO = 'Debito', 'Débito'
    TED = 'TED', 'TED'
    DOC = 'DOC', 'DOC'


class Frequencia(models.TextChoices):
    FIXA = 'Fixa', 'Fixa'
    VARIAVEL = 'Variavel', 'Variável'
    ANUAL = 'Anual', 'Anual'
    UNICA = 'Unica', 'Única/Ocasional'


# ---------------------------------------------------------------------------
# Transação Recorrente (Contas Fixas)
# ---------------------------------------------------------------------------

class TransacaoRecorrente(ModeloBase):
    class TipoValor(models.TextChoices):
        EXATO = 'Exato', 'Exato'
        ESTIMADO = 'Estimado', 'Estimado'

    descricao = models.CharField(max_length=255, blank=True)
    tipo = models.CharField(max_length=15, choices=TipoTransacao.choices)
    plano_conta = models.ForeignKey(
        'contas.PlanoConta',
        on_delete=models.PROTECT,
        related_name='transacoes_recorrentes',
    )
    conta_bancaria = models.ForeignKey(
        'contas.ContaBancaria',
        on_delete=models.PROTECT,
        related_name='transacoes_recorrentes',
    )
    tags = models.ManyToManyField('contas.Tag', blank=True, related_name='transacoes_recorrentes')
    formato_pagamento = models.CharField(max_length=10, choices=FormatoPagamento.choices)
    dia_vencimento = models.PositiveSmallIntegerField()
    valor_base = models.DecimalField(max_digits=12, decimal_places=2)
    tipo_valor = models.CharField(max_length=10, choices=TipoValor.choices, default=TipoValor.EXATO)
    frequencia = models.CharField(max_length=10, choices=Frequencia.choices, default=Frequencia.FIXA, editable=False)
    status_ativa = models.BooleanField(default=True)
    # Campos opcionais para Transferências
    conta_destino = models.ForeignKey(
        'contas.ContaBancaria',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transacoes_recorrentes_destino',
    )
    cofre = models.ForeignKey(
        'orcamento.Cofre',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transacoes_recorrentes',
    )

    class Meta:
        verbose_name = 'Transação Recorrente'
        verbose_name_plural = 'Transações Recorrentes'

    def __str__(self):
        return f'{self.descricao} (dia {self.dia_vencimento} | R$ {self.valor_base})'


# ---------------------------------------------------------------------------
# Lançamento Futuro (pontuais / parcelados)
# ---------------------------------------------------------------------------

class LancamentoFuturo(ModeloBase):
    class Status(models.TextChoices):
        PENDENTE = 'Pendente', 'Pendente'
        INJETADO = 'Injetado', 'Injetado'
        CANCELADO = 'Cancelado', 'Cancelado'

    descricao = models.CharField(max_length=255, blank=True)
    tipo = models.CharField(max_length=15, choices=TipoTransacao.choices)
    plano_conta = models.ForeignKey(
        'contas.PlanoConta',
        on_delete=models.PROTECT,
        related_name='lancamentos_futuros',
    )
    conta_bancaria = models.ForeignKey(
        'contas.ContaBancaria',
        on_delete=models.PROTECT,
        related_name='lancamentos_futuros',
    )
    tags = models.ManyToManyField('contas.Tag', blank=True, related_name='lancamentos_futuros')
    formato_pagamento = models.CharField(max_length=10, choices=FormatoPagamento.choices)
    frequencia = models.CharField(max_length=10, choices=Frequencia.choices, default=Frequencia.VARIAVEL)
    comprovante = models.FileField(upload_to='comprovantes/futuros/', null=True, blank=True)
    data_vencimento = models.DateField()
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    parcela_atual = models.PositiveIntegerField(null=True, blank=True)
    total_parcelas = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDENTE)
    lancamento_pai = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='parcelas_futuras',
    )
    lancamento_par = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='futuro_inverso',
    )
    # Campos opcionais para Transferências
    conta_destino = models.ForeignKey(
        'contas.ContaBancaria',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lancamentos_futuros_destino',
    )
    cofre = models.ForeignKey(
        'orcamento.Cofre',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lancamentos_futuros',
    )

    class Meta:
        verbose_name = 'Lançamento Futuro'
        verbose_name_plural = 'Lançamentos Futuros'
        ordering = ['data_vencimento']

    def __str__(self):
        parcela = f' ({self.parcela_atual}/{self.total_parcelas})' if self.total_parcelas else ''
        return f'{self.descricao}{parcela} | {self.data_vencimento}'


# ---------------------------------------------------------------------------
# Movimentação — Livro-Razão (tabela principal)
# ---------------------------------------------------------------------------

class Movimentacao(ModeloBase):
    class Status(models.TextChoices):
        PENDENTE = 'Pendente', 'Pendente'
        EFETIVADO = 'Efetivado', 'Efetivado'
        REAGENDADO = 'Reagendado', 'Reagendado'
        VALIDADO = 'Validado', 'Validado/Congelado'

    tipo = models.CharField(max_length=15, choices=TipoTransacao.choices)
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    formato_pagamento = models.CharField(max_length=10, choices=FormatoPagamento.choices)
    frequencia = models.CharField(max_length=10, choices=Frequencia.choices, default=Frequencia.VARIAVEL)
    descricao = models.CharField(max_length=255, blank=True)
    comprovante = models.FileField(upload_to='comprovantes/movimentacoes/', null=True, blank=True)
    data_pagamento = models.DateField(null=True, blank=True)
    data_vencimento = models.DateField()
    parcela_atual = models.PositiveIntegerField(null=True, blank=True)
    total_parcelas = models.PositiveIntegerField(null=True, blank=True)
    # data_registro de auditoria é coberto por created_at (herdado de ModeloBase)
    plano_conta = models.ForeignKey(
        'contas.PlanoConta',
        on_delete=models.PROTECT,
        related_name='movimentacoes',
    )
    conta_bancaria = models.ForeignKey(
        'contas.ContaBancaria',
        on_delete=models.PROTECT,
        related_name='movimentacoes',
    )
    conta_destino = models.ForeignKey(
        'contas.ContaBancaria',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimentacoes_destino',
    )
    ciclo = models.ForeignKey(
        'orcamento.Ciclo',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimentacoes',
    )
    # Auto-referência para Rateio (Split)
    lancamento_pai = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='rateios',
    )
    # Auto-referência para par de Transferência
    lancamento_par = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transferencia_inversa',
    )
    cofre = models.ForeignKey(
        'orcamento.Cofre',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimentacoes',
    )
    tags = models.ManyToManyField('contas.Tag', blank=True, related_name='movimentacoes')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDENTE)

    class Meta:
        verbose_name = 'Movimentação'
        verbose_name_plural = 'Movimentações'
        ordering = ['-data_vencimento', '-created_at']

    def __str__(self):
        return f'[{self.get_tipo_display()}] {self.descricao} | R$ {self.valor} ({self.get_status_display()})'


class MovimentacaoExcluida(ModeloBase):
    original_movimentacao_id = models.PositiveIntegerField(db_index=True)
    tipo = models.CharField(max_length=15, choices=TipoTransacao.choices)
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    formato_pagamento = models.CharField(max_length=10, choices=FormatoPagamento.choices)
    frequencia = models.CharField(max_length=10, choices=Frequencia.choices, default=Frequencia.VARIAVEL)
    descricao = models.CharField(max_length=255, blank=True)
    comprovante_path = models.CharField(max_length=255, blank=True)
    data_pagamento = models.DateField(null=True, blank=True)
    data_vencimento = models.DateField(null=True, blank=True)
    parcela_atual = models.PositiveIntegerField(null=True, blank=True)
    total_parcelas = models.PositiveIntegerField(null=True, blank=True)
    plano_conta = models.ForeignKey(
        'contas.PlanoConta',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimentacoes_excluidas',
    )
    conta_bancaria = models.ForeignKey(
        'contas.ContaBancaria',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimentacoes_excluidas_origem',
    )
    conta_destino = models.ForeignKey(
        'contas.ContaBancaria',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimentacoes_excluidas_destino',
    )
    ciclo = models.ForeignKey(
        'orcamento.Ciclo',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimentacoes_excluidas',
    )
    cofre = models.ForeignKey(
        'orcamento.Cofre',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimentacoes_excluidas',
    )
    status = models.CharField(max_length=10, choices=Movimentacao.Status.choices, default=Movimentacao.Status.PENDENTE)
    tags_snapshot = models.JSONField(default=list, blank=True)
    excluida_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Movimentação Excluída'
        verbose_name_plural = 'Movimentações Excluídas'
        ordering = ['-excluida_em', '-created_at']

    def __str__(self):
        return f'[EXCLUÍDA] {self.descricao or "Sem descrição"} | R$ {self.valor}'


class AliasImportacao(ModeloBase):
    class Entidade(models.TextChoices):
        TAG = 'Tag', 'Tag'
        PLANO_CONTA = 'PlanoConta', 'Plano de Conta'
        CONTA_BANCARIA = 'ContaBancaria', 'Conta Bancária'

    entidade = models.CharField(max_length=20, choices=Entidade.choices)
    valor_externo = models.CharField(max_length=180)
    tag = models.ForeignKey(
        'contas.Tag',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='aliases_importacao',
    )
    plano_conta = models.ForeignKey(
        'contas.PlanoConta',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='aliases_importacao',
    )
    conta_bancaria = models.ForeignKey(
        'contas.ContaBancaria',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='aliases_importacao',
    )
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Alias de Importação'
        verbose_name_plural = 'Aliases de Importação'
        ordering = ['entidade', 'valor_externo']
        unique_together = [('entidade', 'valor_externo')]

    def __str__(self):
        return f'{self.entidade}: {self.valor_externo}'

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


class FormatoPagamento(models.TextChoices):
    PIX = 'PIX', 'PIX'
    CARTAO = 'Cartao', 'Cartão'
    BOLETO = 'Boleto', 'Boleto'
    DINHEIRO = 'Dinheiro', 'Dinheiro'
    DEBITO = 'Debito', 'Débito'
    TED = 'TED', 'TED'
    DOC = 'DOC', 'DOC'


# ---------------------------------------------------------------------------
# Transação Recorrente (Contas Fixas)
# ---------------------------------------------------------------------------

class TransacaoRecorrente(ModeloBase):
    class TipoValor(models.TextChoices):
        EXATO = 'Exato', 'Exato'
        ESTIMADO = 'Estimado', 'Estimado'

    descricao = models.CharField(max_length=255)
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

    descricao = models.CharField(max_length=255)
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
    comprovante = models.FileField(upload_to='comprovantes/futuros/', null=True, blank=True)
    data_vencimento = models.DateField()
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    parcela_atual = models.PositiveIntegerField(null=True, blank=True)
    total_parcelas = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDENTE)
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
    descricao = models.CharField(max_length=255)
    comprovante = models.FileField(upload_to='comprovantes/movimentacoes/', null=True, blank=True)
    data_pagamento = models.DateField(null=True, blank=True)
    data_vencimento = models.DateField()
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

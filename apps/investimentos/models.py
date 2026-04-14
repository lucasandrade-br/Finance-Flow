from django.db import models
from decimal import Decimal
from apps.core.models import ModeloBase


class Ativo(ModeloBase):
    class Tipo(models.TextChoices):
        ACAO = 'Acao', 'Ação'
        FII = 'FII', 'Fundo Imobiliário'
        RENDA_FIXA = 'RendaFixa', 'Renda Fixa'
        CRIPTO = 'Cripto', 'Criptomoeda'

    nome = models.CharField(max_length=150)
    ticker = models.CharField(max_length=20, null=True, blank=True, unique=True)
    setor = models.CharField(max_length=80, blank=True, default='')
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    quantidade_atual = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    preco_medio = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    percentual_alvo = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        verbose_name = 'Ativo'
        verbose_name_plural = 'Ativos'

    def __str__(self):
        return f'{self.ticker or self.nome} ({self.get_tipo_display()})'


class Ordem(ModeloBase):
    class TipoOrdem(models.TextChoices):
        COMPRA = 'Compra', 'Compra'
        VENDA = 'Venda', 'Venda'

    ativo = models.ForeignKey(Ativo, on_delete=models.CASCADE, related_name='ordens')
    tipo = models.CharField(max_length=6, choices=TipoOrdem.choices)
    quantidade = models.DecimalField(max_digits=18, decimal_places=8)
    preco = models.DecimalField(max_digits=18, decimal_places=8)
    taxas = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    data = models.DateField()
    resgatar_para_orcamento = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Ordem'
        verbose_name_plural = 'Ordens'
        ordering = ['-data']

    @property
    def total(self):
        """Valor total da ordem: (quantidade × preço) + taxas."""
        return (self.quantidade * self.preco) + self.taxas

    def __str__(self):
        return f'{self.get_tipo_display()} {self.quantidade} x {self.ativo} @ R$ {self.preco}'

    @classmethod
    def total_compras(cls):
        total = Decimal('0.00')
        for ordem in cls.objects.filter(tipo=cls.TipoOrdem.COMPRA):
            total += ordem.total
        return total.quantize(Decimal('0.01'))


class Rendimento(ModeloBase):
    ativo = models.ForeignKey(Ativo, on_delete=models.CASCADE, related_name='rendimentos')
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    data = models.DateField()
    descricao = models.CharField(max_length=255, null=True, blank=True)
    resgatar_para_orcamento = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Rendimento'
        verbose_name_plural = 'Rendimentos'
        ordering = ['-data']

    def __str__(self):
        return f'{self.ativo} | R$ {self.valor} em {self.data}'


class MetaFinanceira(ModeloBase):
    class Status(models.TextChoices):
        RASCUNHO = 'Rascunho', 'Rascunho'
        ATIVA = 'Ativa', 'Ativa'
        CONCLUIDA = 'Concluida', 'Concluída'
        CANCELADA = 'Cancelada', 'Cancelada'

    nome = models.CharField(max_length=180)
    conta_bancaria = models.ForeignKey(
        'contas.ContaBancaria',
        on_delete=models.CASCADE,
        related_name='metas_financeiras',
    )
    valor_alvo = models.DecimalField(max_digits=12, decimal_places=2)
    data_inicio = models.DateField()
    data_fim = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ATIVA)

    class Meta:
        verbose_name = 'Meta Financeira'
        verbose_name_plural = 'Metas Financeiras'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.nome} ({self.conta_bancaria})'


class MetaParcelaMensal(ModeloBase):
    meta = models.ForeignKey(
        MetaFinanceira,
        on_delete=models.CASCADE,
        related_name='parcelas_mensais',
    )
    competencia = models.DateField(help_text='Use o primeiro dia do mês como referência da competência.')
    valor_planejado = models.DecimalField(max_digits=12, decimal_places=2)
    ordem_mes = models.PositiveIntegerField(default=1)
    observacao = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = 'Parcela Mensal da Meta'
        verbose_name_plural = 'Parcelas Mensais das Metas'
        ordering = ['meta_id', 'competencia', 'ordem_mes']
        constraints = [
            models.UniqueConstraint(fields=['meta', 'competencia'], name='uniq_meta_competencia')
        ]

    def __str__(self):
        return f'{self.meta.nome} - {self.competencia:%m/%Y}'


class AportePatrimonial(ModeloBase):
    data = models.DateTimeField(auto_now_add=True)
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    descricao = models.CharField(max_length=255, default='Aporte via Orçamento')
    id_transacao_origem = models.IntegerField(null=True, blank=True)

    class Meta:
        verbose_name = 'Aporte Patrimonial'
        verbose_name_plural = 'Aportes Patrimoniais'
        ordering = ['-data', '-created_at']

    def __str__(self):
        return f'{self.descricao} | R$ {self.valor} em {self.data:%d/%m/%Y %H:%M}'

    @classmethod
    def saldo_disponivel(cls):
        total_aportes = Decimal('0.00')
        for aporte in cls.objects.all():
            total_aportes += Decimal(aporte.valor or 0)

        total_compras = Ordem.total_compras()
        saldo = total_aportes - total_compras
        return saldo.quantize(Decimal('0.01'))

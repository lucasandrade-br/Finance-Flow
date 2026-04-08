from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator
from apps.core.models import ModeloBase


class Ciclo(ModeloBase):
    class Status(models.TextChoices):
        PLANEJAMENTO = 'Planejamento', 'Planejamento'
        ABERTO = 'Aberto', 'Aberto'
        FECHADO = 'Fechado', 'Fechado'

    data_inicio = models.DateField()
    data_fim = models.DateField()
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.PLANEJAMENTO,
    )
    saldo_inicial_projetado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    saldo_final_realizado = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = 'Ciclo'
        verbose_name_plural = 'Ciclos'
        ordering = ['-data_inicio']

    def __str__(self):
        return f'Ciclo {self.data_inicio} → {self.data_fim} [{self.get_status_display()}]'


class MacroOrcamento(ModeloBase):
    ano = models.IntegerField()
    mes = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    plano_conta = models.ForeignKey(
        'contas.PlanoConta',
        on_delete=models.CASCADE,
        related_name='macro_orcamentos',
    )
    valor_teto = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = 'Macro-Orçamento'
        verbose_name_plural = 'Macro-Orçamentos'
        unique_together = [('ano', 'mes', 'plano_conta')]

    def __str__(self):
        return f'{self.plano_conta} | {self.mes:02d}/{self.ano} -> R$ {self.valor_teto}'


class Cofre(ModeloBase):
    class Status(models.TextChoices):
        ANDAMENTO = 'Andamento', 'Em Andamento'
        CONCLUIDA = 'Concluida', 'Concluída'
        PAUSADA = 'Pausada', 'Pausada'

    nome = models.CharField(max_length=150)
    valor_meta = models.DecimalField(max_digits=12, decimal_places=2)
    data_alvo = models.DateField(null=True, blank=True)
    saldo_atual = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ANDAMENTO)

    class Meta:
        verbose_name = 'Cofre'
        verbose_name_plural = 'Cofres'

    def __str__(self):
        return f'{self.nome} (R$ {self.saldo_atual} / R$ {self.valor_meta})'


class MovimentacaoOrcamento(ModeloBase):
    class Tipo(models.TextChoices):
        RECEITA = 'Receita', 'Receita'
        DESPESA = 'Despesa', 'Despesa'
        INVESTIMENTO = 'Investimento', 'Investimento'
        TRANSFERENCIA = 'Transferencia', 'Transferência'

    class Frequencia(models.TextChoices):
        MENSAL = 'Mensal', 'Mensal'
        ANUAL = 'Anual', 'Anual'

    tipo = models.CharField(max_length=15, choices=Tipo.choices)
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    tags = models.ManyToManyField('contas.Tag', blank=True, related_name='movimentacoes_orcamento')
    plano_conta = models.ForeignKey(
        'contas.PlanoConta',
        on_delete=models.PROTECT,
        related_name='movimentacoes_orcamento',
    )
    descricao = models.CharField(max_length=255, blank=True)
    frequencia = models.CharField(max_length=10, choices=Frequencia.choices, default=Frequencia.MENSAL)
    conta_bancaria = models.ForeignKey(
        'contas.ContaBancaria',
        on_delete=models.PROTECT,
        related_name='movimentacoes_orcamento',
    )
    dia_referencia = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(31)],
    )
    mes_referencia = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )
    status_ativa = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Movimentação de Orçamento'
        verbose_name_plural = 'Movimentações de Orçamento'
        ordering = ['tipo', 'plano_conta__codigo', 'descricao']

    def __str__(self):
        return f'[{self.get_tipo_display()}] {self.plano_conta} -> R$ {self.valor}'

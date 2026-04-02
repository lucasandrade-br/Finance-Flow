from django.db import models
from django.core.validators import RegexValidator
from apps.core.models import ModeloBase


class PlanoConta(ModeloBase):
    class TipoNatureza(models.TextChoices):
        RECEITA = 'Receita', 'Receita'
        DESPESA = 'Despesa', 'Despesa'
        INVESTIMENTO = 'Investimento', 'Investimento'
        TRANSFERENCIA = 'Transferencia', 'Transferência'

    codigo = models.CharField(
        max_length=40,
        unique=True,
        db_index=True,
        validators=[
            RegexValidator(
                regex=r'^\d+(\.\d+)*$',
                message='Use formato hierárquico numérico, como 1, 1.1 ou 1.1.1.',
            )
        ],
    )
    nome = models.CharField(max_length=150)
    tipo_natureza = models.CharField(max_length=15, choices=TipoNatureza.choices)
    conta_pai = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subcontas',
    )

    class Meta:
        verbose_name = 'Plano de Conta'
        verbose_name_plural = 'Plano de Contas'

    def __str__(self):
        if self.conta_pai_id:
            return f'{self.codigo} - {self.conta_pai} > {self.nome}'
        return f'{self.codigo} - {self.nome}'


class ContaBancaria(ModeloBase):
    class Tipo(models.TextChoices):
        CONTA_CORRENTE = 'ContaCorrente', 'Conta Corrente'
        POUPANCA = 'Poupanca', 'Poupança'
        CARTEIRA = 'Carteira', 'Carteira'
        CORRETORA = 'Corretora', 'Corretora'
        CARTAO_CREDITO = 'CartaoCredito', 'Cartão de Crédito'

    nome = models.CharField(max_length=150)
    tipo = models.CharField(max_length=15, choices=Tipo.choices)
    saldo_inicial = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    limite_credito = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    dia_vencimento = models.PositiveSmallIntegerField(null=True, blank=True)
    dia_fechamento = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = 'Conta Bancária'
        verbose_name_plural = 'Contas Bancárias'

    def __str__(self):
        return f'{self.nome} ({self.get_tipo_display()})'


class Tag(ModeloBase):
    nome = models.CharField(max_length=100)
    plano_conta = models.ForeignKey(
        PlanoConta,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tags',
    )
    cor_hexadecimal = models.CharField(max_length=7, null=True, blank=True)

    class Meta:
        verbose_name = 'Tag'
        verbose_name_plural = 'Tags'

    def __str__(self):
        return self.nome

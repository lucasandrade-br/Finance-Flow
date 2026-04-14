from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.contas.models import ContaBancaria, PlanoConta
from apps.investimentos.models import Ativo
from apps.orcamento.models import Ciclo
from apps.transacoes.models import FormatoPagamento, Frequencia, Movimentacao, TipoTransacao


def _to_decimal(value, default=Decimal('0.00')):
    try:
        return Decimal(str(value or '')).quantize(Decimal('0.01'))
    except (InvalidOperation, TypeError, ValueError):
        return default


@transaction.atomic
def processar_ordem(ordem):
    ativo = Ativo.objects.select_for_update().get(pk=ordem.ativo_id)
    quantidade_ordem = Decimal(ordem.quantidade or 0)
    preco_ordem = Decimal(ordem.preco or 0)
    quantidade_atual = Decimal(ativo.quantidade_atual or 0)
    preco_medio_atual = Decimal(ativo.preco_medio or 0)

    if ordem.tipo == ordem.TipoOrdem.COMPRA:
        novo_total_investido = (quantidade_atual * preco_medio_atual) + (quantidade_ordem * preco_ordem)
        nova_quantidade = quantidade_atual + quantidade_ordem
        if nova_quantidade <= 0:
            ativo.quantidade_atual = Decimal('0')
            ativo.preco_medio = Decimal('0')
        else:
            ativo.quantidade_atual = nova_quantidade
            ativo.preco_medio = (novo_total_investido / nova_quantidade).quantize(Decimal('0.00000001'))

    elif ordem.tipo == ordem.TipoOrdem.VENDA:
        if quantidade_ordem > quantidade_atual:
            raise ValueError('Quantidade de venda maior do que a posição atual do ativo.')

        nova_quantidade = quantidade_atual - quantidade_ordem
        ativo.quantidade_atual = nova_quantidade
        if nova_quantidade <= 0:
            ativo.preco_medio = Decimal('0')

    ativo.save(update_fields=['quantidade_atual', 'preco_medio', 'updated_at'])
    return ativo


@transaction.atomic
def processar_rendimento(rendimento):
    if not rendimento.resgatar_para_orcamento:
        return None

    ciclo_ativo = Ciclo.objects.filter(status=Ciclo.Status.ABERTO).order_by('-data_inicio').first()
    if not ciclo_ativo:
        raise ValueError('Não existe ciclo ativo para receber o resgate do rendimento.')

    plano_receita = PlanoConta.objects.filter(tipo_natureza=PlanoConta.TipoNatureza.RECEITA).order_by('codigo', 'id').first()
    if not plano_receita:
        raise ValueError('Nenhum Plano de Conta de Receita foi encontrado para registrar o resgate.')

    conta_destino = ContaBancaria.objects.order_by('nome', 'id').first()
    if not conta_destino:
        raise ValueError('Nenhuma Conta Bancária foi encontrada para registrar o resgate.')

    ticker = rendimento.ativo.ticker or rendimento.ativo.nome
    descricao = f'Resgate Rendimento {ticker}'

    movimentacao = Movimentacao.objects.create(
        tipo=TipoTransacao.RECEITA,
        valor=_to_decimal(rendimento.valor),
        descricao=descricao,
        data_pagamento=rendimento.data,
        data_vencimento=rendimento.data,
        plano_conta_id=plano_receita.id,
        conta_bancaria_id=conta_destino.id,
        ciclo_id=ciclo_ativo.id,
        status=Movimentacao.Status.PENDENTE,
        formato_pagamento=FormatoPagamento.PIX,
        frequencia=Frequencia.VARIAVEL,
    )
    return movimentacao


@transaction.atomic
def recalcular_posicao_ativo(ativo_id):
    ativo = Ativo.objects.select_for_update().get(pk=ativo_id)
    ordens = ativo.ordens.all().order_by('data', 'created_at', 'id')

    quantidade_atual = Decimal('0')
    preco_medio = Decimal('0')

    for ordem in ordens:
        quantidade_ordem = Decimal(ordem.quantidade or 0)
        preco_ordem = Decimal(ordem.preco or 0)

        if ordem.tipo == ordem.TipoOrdem.COMPRA:
            novo_total_investido = (quantidade_atual * preco_medio) + (quantidade_ordem * preco_ordem)
            quantidade_atual += quantidade_ordem
            if quantidade_atual > 0:
                preco_medio = (novo_total_investido / quantidade_atual).quantize(Decimal('0.00000001'))
        elif ordem.tipo == ordem.TipoOrdem.VENDA:
            if quantidade_ordem > quantidade_atual:
                raise ValueError('Histórico de ordens inconsistente: venda maior que a posição acumulada.')
            quantidade_atual -= quantidade_ordem
            if quantidade_atual <= 0:
                quantidade_atual = Decimal('0')
                preco_medio = Decimal('0')

    ativo.quantidade_atual = quantidade_atual
    ativo.preco_medio = preco_medio
    ativo.save(update_fields=['quantidade_atual', 'preco_medio', 'updated_at'])
    return ativo


def calcular_rebalanceamento(valor_aporte):
    aporte = _to_decimal(valor_aporte)
    ativos = list(
        Ativo.objects.filter(Q(quantidade_atual__gt=0) | Q(percentual_alvo__gt=0)).order_by('ticker', 'nome')
    )

    linhas = []
    patrimonio_total = Decimal('0.00')
    for ativo in ativos:
        valor_atual = (Decimal(ativo.quantidade_atual or 0) * Decimal(ativo.preco_medio or 0)).quantize(Decimal('0.01'))
        patrimonio_total += valor_atual
        linhas.append({'ativo': ativo, 'valor_atual': valor_atual})

    patrimonio_base = patrimonio_total + aporte
    recomendacoes = []

    for linha in linhas:
        ativo = linha['ativo']
        valor_atual = linha['valor_atual']
        percentual_alvo = Decimal(ativo.percentual_alvo or 0)
        preco_base = Decimal(ativo.preco_medio or 0)

        valor_ideal = (patrimonio_base * (percentual_alvo / Decimal('100'))).quantize(Decimal('0.01'))
        diferenca = (valor_ideal - valor_atual).quantize(Decimal('0.01'))

        if diferenca <= 0:
            continue

        if preco_base > 0:
            quantidade_comprar = (diferenca / preco_base).quantize(Decimal('0.00000001'))
        else:
            quantidade_comprar = Decimal('0.00000000')

        recomendacoes.append(
            {
                'ativo': ativo,
                'valor_atual': valor_atual,
                'valor_ideal': valor_ideal,
                'diferenca': diferenca,
                'quantidade_comprar': quantidade_comprar,
            }
        )

    return {
        'patrimonio_total': patrimonio_total.quantize(Decimal('0.01')),
        'aporte': aporte,
        'patrimonio_com_aporte': patrimonio_base.quantize(Decimal('0.01')),
        'recomendacoes': recomendacoes,
        'gerado_em': timezone.localtime(),
    }

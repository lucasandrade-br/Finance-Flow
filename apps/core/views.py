from decimal import Decimal

from django.db.models import Q, Sum
from django.shortcuts import render
from django.utils import timezone

from apps.contas.models import ContaBancaria
from apps.orcamento.models import Ciclo
from apps.transacoes.models import Movimentacao


def home(request):
    hoje = timezone.now().date()

    # ------------------------------------------------------------------
    # Ciclo Ativo
    # ------------------------------------------------------------------
    ciclo_ativo = Ciclo.objects.filter(status='Aberto').first()
    dias_restantes = 0
    progresso_burn_rate = 0

    if ciclo_ativo:
        dias_restantes = max((ciclo_ativo.data_fim - hoje).days, 0)

        if ciclo_ativo.saldo_inicial_projetado:
            despesas_ciclo = (
                Movimentacao.objects
                .filter(
                    ciclo=ciclo_ativo,
                    tipo='Despesa',
                    status__in=['Efetivado', 'Validado'],
                )
                .aggregate(total=Sum('valor'))['total']
            ) or Decimal('0')

            progresso_burn_rate = min(
                int(despesas_ciclo / ciclo_ativo.saldo_inicial_projetado * 100),
                100,
            )

    # ------------------------------------------------------------------
    # Últimas Movimentações (top 5)
    # ------------------------------------------------------------------
    ultimas_transacoes = (
        Movimentacao.objects
        .select_related('plano_conta', 'conta_bancaria')
        .order_by('-data_pagamento', '-created_at')[:5]
    )

    # ------------------------------------------------------------------
    # Saldo Total Consolidado
    # ------------------------------------------------------------------
    saldo_inicial_total = (
        ContaBancaria.objects.aggregate(total=Sum('saldo_inicial'))['total']
        or Decimal('0')
    )

    totais_efetivados = Movimentacao.objects.filter(
        status__in=['Efetivado', 'Validado'],
    ).aggregate(
        receitas=Sum('valor', filter=Q(tipo='Receita')),
        despesas=Sum('valor', filter=Q(tipo='Despesa')),
    )

    receitas_efetivadas = totais_efetivados['receitas'] or Decimal('0')
    despesas_efetivadas = totais_efetivados['despesas'] or Decimal('0')
    saldo_total = saldo_inicial_total + receitas_efetivadas - despesas_efetivadas

    # ------------------------------------------------------------------
    # Resumo do Mês Corrente
    # ------------------------------------------------------------------
    totais_mes = Movimentacao.objects.filter(
        status__in=['Efetivado', 'Validado'],
        data_pagamento__month=hoje.month,
        data_pagamento__year=hoje.year,
    ).aggregate(
        receitas=Sum('valor', filter=Q(tipo='Receita')),
        despesas=Sum('valor', filter=Q(tipo='Despesa')),
    )

    receitas_mes = totais_mes['receitas'] or Decimal('0')
    despesas_mes = totais_mes['despesas'] or Decimal('0')
    margem_mes = receitas_mes - despesas_mes

    context = {
        'saldo_total': saldo_total,
        'receitas_mes': receitas_mes,
        'despesas_mes': despesas_mes,
        'margem_mes': margem_mes,
        'ciclo_ativo': ciclo_ativo,
        'dias_restantes': dias_restantes,
        'progresso_burn_rate': progresso_burn_rate,
        'ultimas_transacoes': ultimas_transacoes,
    }

    return render(request, 'core/dashboard.html', context)

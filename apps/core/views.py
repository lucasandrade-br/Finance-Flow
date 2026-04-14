from datetime import date
from decimal import Decimal

from django.db.models import F, Q, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.contas.models import ContaBancaria
from apps.orcamento.models import Ciclo
from apps.transacoes.models import LancamentoFuturo, Movimentacao


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _add_months(value: date, months: int) -> date:
    month = value.month - 1 + months
    year = value.year + month // 12
    month = month % 12 + 1
    return value.replace(year=year, month=month, day=1)


def _build_month_series(start: date, end: date) -> list[date]:
    cursor = _month_start(start)
    limit = _month_start(end)
    series = []
    while cursor <= limit:
        series.append(cursor)
        cursor = _add_months(cursor, 1)
    return series


def home(request):
    hoje = timezone.now().date()
    inicio_mes_atual = hoje.replace(day=1)
    mes_base = inicio_mes_atual.month - 2
    ano_base = inicio_mes_atual.year
    while mes_base <= 0:
        mes_base += 12
        ano_base -= 1
    inicio_janela_3_meses = inicio_mes_atual.replace(year=ano_base, month=mes_base)

    # ------------------------------------------------------------------
    # Ciclo Ativo
    # ------------------------------------------------------------------
    ciclo_ativo = Ciclo.objects.filter(status='Aberto').first()
    dias_restantes = 0
    progresso_burn_rate = 0

    if ciclo_ativo:
        dias_restantes = max((ciclo_ativo.data_fim - hoje).days, 0)

        totais_ciclo = (
            Movimentacao.objects
            .filter(
                ciclo=ciclo_ativo,
                status__in=['Efetivado', 'Validado', 'Pendente'],
            )
            .aggregate(
                entradas=Sum('valor', filter=Q(tipo='Receita')),
                despesas=Sum('valor', filter=Q(tipo__in=['Despesa', 'Investimento'])),
            )
        )
        entradas_ciclo = totais_ciclo['entradas'] or Decimal('0')
        despesas_ciclo = totais_ciclo['despesas'] or Decimal('0')

        if entradas_ciclo > 0:
            progresso_burn_rate = min(
                int(despesas_ciclo / entradas_ciclo * 100),
                100,
            )

    # ------------------------------------------------------------------
    # Planos de Conta (Despesa/Investimento) do Mês + Média 3M
    # ------------------------------------------------------------------
    planos_mes_qs = (
        Movimentacao.objects
        .filter(
            status__in=['Efetivado', 'Validado'],
            data_pagamento__month=hoje.month,
            data_pagamento__year=hoje.year,
            plano_conta__tipo_natureza__in=['Despesa', 'Investimento'],
        )
        .values(
            'plano_conta_id',
            'plano_conta__codigo',
            'plano_conta__nome',
            'plano_conta__tipo_natureza',
        )
        .annotate(total_mes=Coalesce(Sum('valor'), Decimal('0.00')))
        .order_by('plano_conta__codigo')
    )
    plano_ids_mes = [item['plano_conta_id'] for item in planos_mes_qs]

    medias_planos_3_meses_map = {}
    if plano_ids_mes:
        medias_planos_3_meses_qs = (
            Movimentacao.objects.annotate(data_referencia=Coalesce('data_pagamento', 'data_vencimento'))
            .filter(
                status__in=['Efetivado', 'Validado'],
                plano_conta_id__in=plano_ids_mes,
                data_referencia__gte=inicio_janela_3_meses,
                data_referencia__lte=hoje,
            )
            .values('plano_conta_id')
            .annotate(total_3_meses=Coalesce(Sum('valor'), Decimal('0.00')))
        )
        medias_planos_3_meses_map = {
            item['plano_conta_id']: (item['total_3_meses'] / Decimal('3.00'))
            for item in medias_planos_3_meses_qs
        }

    planos_resumo_mes = [
        {
            'codigo': item['plano_conta__codigo'],
            'nome': item['plano_conta__nome'],
            'tipo_natureza': item['plano_conta__tipo_natureza'],
            'total_mes': item['total_mes'],
            'media_3_meses': medias_planos_3_meses_map.get(item['plano_conta_id'], Decimal('0.00')),
        }
        for item in planos_mes_qs
    ]

    # ------------------------------------------------------------------
    # Resumo do Mês Corrente
    # ------------------------------------------------------------------
    totais_mes = Movimentacao.objects.filter(
        status__in=['Pendente','Efetivado', 'Validado'],
        data_pagamento__month=hoje.month,
        data_pagamento__year=hoje.year,
    ).aggregate(
        receitas=Sum('valor', filter=Q(tipo='Receita')),
        despesas=Sum('valor', filter=Q(tipo='Despesa')),
        investimentos=Sum('valor', filter=Q(tipo='Investimento')),
        transferencias_entrada=Sum('valor', filter=Q(tipo='TransfEntrada')),
        transferencias_saida=Sum('valor', filter=Q(tipo='TransfSaida')),
    )

    receitas_mes = totais_mes['receitas'] or Decimal('0')
    despesas_mes = totais_mes['despesas'] or Decimal('0')
    investimentos_mes = totais_mes['investimentos'] or Decimal('0')
    transferencias_entrada_mes = totais_mes['transferencias_entrada'] or Decimal('0')
    transferencias_saida_mes = totais_mes['transferencias_saida'] or Decimal('0')
    margem_mes = receitas_mes - (despesas_mes + investimentos_mes)
    saldo_mes = receitas_mes - (despesas_mes + investimentos_mes + transferencias_saida_mes)

    totais_3_meses = Movimentacao.objects.annotate(
        data_referencia=Coalesce('data_pagamento', 'data_vencimento')
    ).filter(
        status__in=['Efetivado', 'Validado'],
        data_referencia__gte=inicio_janela_3_meses,
        data_referencia__lte=hoje,
    ).aggregate(
        receitas=Sum('valor', filter=Q(tipo='Receita')),
        despesas=Sum('valor', filter=Q(tipo='Despesa')),
        investimentos=Sum('valor', filter=Q(tipo='Investimento')),
        transferencias_saida=Sum('valor', filter=Q(tipo='TransfSaida')),
    )

    media_receitas_3_meses = (totais_3_meses['receitas'] or Decimal('0')) / Decimal('3.00')
    media_despesas_3_meses = (totais_3_meses['despesas'] or Decimal('0')) / Decimal('3.00')
    media_investimentos_3_meses = (totais_3_meses['investimentos'] or Decimal('0')) / Decimal('3.00')
    media_transferencias_saida_3_meses = (totais_3_meses['transferencias_saida'] or Decimal('0')) / Decimal('3.00')
    context = {
        'receitas_mes': receitas_mes,
        'despesas_mes': despesas_mes,
        'investimentos_mes': investimentos_mes,
        'transferencias_entrada_mes': transferencias_entrada_mes,
        'transferencias_saida_mes': transferencias_saida_mes,
        'saldo_mes': saldo_mes,
        'media_receitas_3_meses': media_receitas_3_meses,
        'media_despesas_3_meses': media_despesas_3_meses,
        'media_investimentos_3_meses': media_investimentos_3_meses,
        'media_transferencias_saida_3_meses': media_transferencias_saida_3_meses,
        'margem_mes': margem_mes,
        'ciclo_ativo': ciclo_ativo,
        'dias_restantes': dias_restantes,
        'progresso_burn_rate': progresso_burn_rate,
        'planos_resumo_mes': planos_resumo_mes,
    }

    return render(request, 'core/dashboard.html', context)


def dashboard_analitico(request):
    hoje = timezone.localdate()
    inicio_padrao = _add_months(_month_start(hoje), -5)
    fim_padrao = hoje

    data_inicio = parse_date(request.GET.get('data_inicio') or '') or inicio_padrao
    data_fim = parse_date(request.GET.get('data_fim') or '') or fim_padrao
    if data_inicio > data_fim:
        data_inicio, data_fim = data_fim, data_inicio

    conta_bancaria_raw = (request.GET.get('conta_bancaria_id') or '').strip()
    tipo = (request.GET.get('tipo') or '').strip()
    status = (request.GET.get('status') or '').strip()

    contas_bancarias = ContaBancaria.objects.all().order_by('nome')
    tipos_disponiveis = [choice[0] for choice in Movimentacao._meta.get_field('tipo').choices]
    status_disponiveis = [choice[0] for choice in Movimentacao._meta.get_field('status').choices]

    movimentacoes_periodo = (
        Movimentacao.objects
        .annotate(data_referencia=Coalesce('data_pagamento', 'data_vencimento'))
        .filter(data_referencia__gte=data_inicio, data_referencia__lte=data_fim)
    )

    filtro_conta_id = None
    if conta_bancaria_raw.isdigit():
        filtro_conta_id = int(conta_bancaria_raw)
        movimentacoes_periodo = movimentacoes_periodo.filter(conta_bancaria_id=filtro_conta_id)

    if status in status_disponiveis:
        movimentacoes_periodo = movimentacoes_periodo.filter(status=status)

    movimentacoes_base = movimentacoes_periodo

    if tipo in tipos_disponiveis:
        movimentacoes_base = movimentacoes_base.filter(tipo=tipo)

    totais = movimentacoes_base.aggregate(
        receitas=Sum('valor', filter=Q(tipo='Receita')),
        despesas=Sum('valor', filter=Q(tipo='Despesa')),
        investimentos=Sum('valor', filter=Q(tipo='Investimento')),
        transferencias_saida=Sum('valor', filter=Q(tipo='TransfSaida')),
    )

    receitas = totais['receitas'] or Decimal('0.00')
    despesas = totais['despesas'] or Decimal('0.00')
    investimentos = totais['investimentos'] or Decimal('0.00')
    transferencias_saida = totais['transferencias_saida'] or Decimal('0.00')
    saldo_liquido = receitas - despesas - investimentos

    meses = _build_month_series(data_inicio, data_fim)
    tendencia_qs = (
        movimentacoes_base
        .annotate(mes=TruncMonth('data_referencia'))
        .values('mes')
        .annotate(
            receitas=Sum('valor', filter=Q(tipo='Receita')),
            despesas=Sum('valor', filter=Q(tipo='Despesa')),
            investimentos=Sum('valor', filter=Q(tipo='Investimento')),
        )
        .order_by('mes')
    )

    tendencia_map = {}
    for item in tendencia_qs:
        mes = item['mes']
        mes_key = mes.date() if hasattr(mes, 'date') else mes
        tendencia_map[mes_key] = {
            'receitas': item['receitas'] or Decimal('0.00'),
            'despesas': item['despesas'] or Decimal('0.00'),
            'investimentos': item['investimentos'] or Decimal('0.00'),
        }

    tendencia_mensal = []
    max_total_periodo = Decimal('0.00')
    for mes in meses:
        valores = tendencia_map.get(
            mes,
            {'receitas': Decimal('0.00'), 'despesas': Decimal('0.00'), 'investimentos': Decimal('0.00')},
        )
        total_mes = valores['receitas'] + valores['despesas'] + valores['investimentos']
        if total_mes > max_total_periodo:
            max_total_periodo = total_mes
        tendencia_mensal.append(
            {
                'label': mes.strftime('%m/%Y'),
                'receitas': valores['receitas'],
                'despesas': valores['despesas'],
                'investimentos': valores['investimentos'],
                'total': total_mes,
            }
        )

    for item in tendencia_mensal:
        total = item['total']
        if max_total_periodo > 0:
            item['escala'] = max(6, int((total / max_total_periodo) * 100))
        else:
            item['escala'] = 0

        if total > 0:
            item['receitas_share'] = int((item['receitas'] / total) * 100)
            item['despesas_share'] = int((item['despesas'] / total) * 100)
            item['investimentos_share'] = max(0, 100 - item['receitas_share'] - item['despesas_share'])
        else:
            item['receitas_share'] = 0
            item['despesas_share'] = 0
            item['investimentos_share'] = 0

    tendencia_labels = [item['label'] for item in tendencia_mensal]
    tendencia_receitas = [float(item['receitas']) for item in tendencia_mensal]
    tendencia_despesas = [float(item['despesas']) for item in tendencia_mensal]
    tendencia_investimentos = [float(item['investimentos']) for item in tendencia_mensal]

    despesas_frequencia_qs = (
        movimentacoes_periodo
        .filter(tipo='Despesa', frequencia__in=['Variavel', 'Fixa'])
        .annotate(mes=TruncMonth('data_referencia'))
        .values('mes')
        .annotate(
            variavel=Sum('valor', filter=Q(frequencia='Variavel')),
            fixa=Sum('valor', filter=Q(frequencia='Fixa')),
        )
        .order_by('mes')
    )
    despesas_frequencia_map = {}
    for item in despesas_frequencia_qs:
        mes = item['mes']
        mes_key = mes.date() if hasattr(mes, 'date') else mes
        despesas_frequencia_map[mes_key] = {
            'variavel': item['variavel'] or Decimal('0.00'),
            'fixa': item['fixa'] or Decimal('0.00'),
        }

    despesas_recorrentes_variavel = []
    despesas_recorrentes_fixa = []
    for mes in meses:
        valores = despesas_frequencia_map.get(mes, {'variavel': Decimal('0.00'), 'fixa': Decimal('0.00')})
        despesas_recorrentes_variavel.append(float(valores['variavel']))
        despesas_recorrentes_fixa.append(float(valores['fixa']))

    despesas_ocasionais_qs = (
        movimentacoes_periodo
        .filter(tipo='Despesa', frequencia__in=['Anual', 'Unica'])
        .annotate(mes=TruncMonth('data_referencia'))
        .values('mes')
        .annotate(
            anual=Sum('valor', filter=Q(frequencia='Anual')),
            unica=Sum('valor', filter=Q(frequencia='Unica')),
        )
        .order_by('mes')
    )
    despesas_ocasionais_map = {}
    for item in despesas_ocasionais_qs:
        mes = item['mes']
        mes_key = mes.date() if hasattr(mes, 'date') else mes
        despesas_ocasionais_map[mes_key] = {
            'anual': item['anual'] or Decimal('0.00'),
            'unica': item['unica'] or Decimal('0.00'),
        }

    despesas_ocasionais_anual = []
    despesas_ocasionais_unica = []
    for mes in meses:
        valores = despesas_ocasionais_map.get(mes, {'anual': Decimal('0.00'), 'unica': Decimal('0.00')})
        despesas_ocasionais_anual.append(float(valores['anual']))
        despesas_ocasionais_unica.append(float(valores['unica']))

    futuros_pendentes_qs = LancamentoFuturo.objects.filter(status=LancamentoFuturo.Status.PENDENTE)

    futuros_pendentes_agrupados = (
        futuros_pendentes_qs
        .annotate(mes=TruncMonth('data_vencimento'))
        .values('mes')
        .annotate(total=Sum('valor'))
        .order_by('mes')
    )
    futuros_pendentes_labels = [
        (item['mes'].date() if hasattr(item['mes'], 'date') else item['mes']).strftime('%m/%Y')
        for item in futuros_pendentes_agrupados
    ]
    futuros_pendentes_totais = [
        float(item['total'] or Decimal('0.00'))
        for item in futuros_pendentes_agrupados
    ]

    investimentos_por_plano_qs = (
        movimentacoes_periodo
        .filter(tipo='Investimento')
        .values('plano_conta__codigo', 'plano_conta__nome')
        .annotate(total=Sum('valor'))
        .order_by('-total')[:10]
    )
    investimentos_por_plano = [
        {
            'label': f"{item['plano_conta__codigo']} - {item['plano_conta__nome']}",
            'valor': float(item['total'] or Decimal('0.00')),
        }
        for item in investimentos_por_plano_qs
    ]

    top_planos_qs = (
        movimentacoes_base
        .filter(tipo__in=['Despesa', 'Investimento'])
        .values('plano_conta__codigo', 'plano_conta__nome')
        .annotate(total=Sum('valor'))
        .order_by('-total')[:8]
    )
    top_planos_total = sum((item['total'] or Decimal('0.00')) for item in top_planos_qs)
    top_planos = []
    for item in top_planos_qs:
        valor = item['total'] or Decimal('0.00')
        percentual = float((valor / top_planos_total) * Decimal('100')) if top_planos_total > 0 else 0.0
        top_planos.append(
            {
                'codigo': item['plano_conta__codigo'],
                'nome': item['plano_conta__nome'],
                'total': valor,
                'percentual': percentual,
            }
        )

    top_despesas_qs = (
        movimentacoes_base
        .filter(tipo='Despesa')
        .values('plano_conta__codigo', 'plano_conta__nome')
        .annotate(total=Sum('valor'))
        .order_by('-total')[:6]
    )
    total_despesas_top = sum((item['total'] or Decimal('0.00')) for item in top_despesas_qs)
    top_despesas = []
    for item in top_despesas_qs:
        valor = item['total'] or Decimal('0.00')
        percentual = float((valor / total_despesas_top) * Decimal('100')) if total_despesas_top > 0 else 0.0
        top_despesas.append(
            {
                'codigo': item['plano_conta__codigo'],
                'nome': item['plano_conta__nome'],
                'total': valor,
                'percentual': percentual,
            }
        )

    top_investimentos_qs = (
        movimentacoes_base
        .filter(tipo='Investimento')
        .values('plano_conta__codigo', 'plano_conta__nome')
        .annotate(total=Sum('valor'))
        .order_by('-total')[:6]
    )
    total_investimentos_top = sum((item['total'] or Decimal('0.00')) for item in top_investimentos_qs)
    top_investimentos = []
    for item in top_investimentos_qs:
        valor = item['total'] or Decimal('0.00')
        percentual = float((valor / total_investimentos_top) * Decimal('100')) if total_investimentos_top > 0 else 0.0
        top_investimentos.append(
            {
                'codigo': item['plano_conta__codigo'],
                'nome': item['plano_conta__nome'],
                'total': valor,
                'percentual': percentual,
            }
        )

    movimentacoes_operacionais = movimentacoes_periodo

    pendentes_vencidos = movimentacoes_operacionais.filter(
        status=Movimentacao.Status.PENDENTE,
        data_vencimento__lt=hoje,
    ).count()

    efetivadas = movimentacoes_operacionais.filter(
        status__in=[Movimentacao.Status.EFETIVADO, Movimentacao.Status.VALIDADO],
        data_pagamento__isnull=False,
        data_vencimento__isnull=False,
    )
    total_efetivadas = efetivadas.count()
    efetivadas_no_prazo = efetivadas.filter(data_pagamento__lte=F('data_vencimento')).count()
    percentual_no_prazo = int((efetivadas_no_prazo / total_efetivadas) * 100) if total_efetivadas else 0

    ciclo_ativo = Ciclo.objects.filter(status=Ciclo.Status.ABERTO).first()
    burn_rate_periodo = 0
    if ciclo_ativo:
        totais_ciclo = (
            Movimentacao.objects
            .filter(
                ciclo=ciclo_ativo,
                status__in=[Movimentacao.Status.PENDENTE, Movimentacao.Status.EFETIVADO, Movimentacao.Status.VALIDADO],
                data_vencimento__gte=data_inicio,
                data_vencimento__lte=data_fim,
            )
            .aggregate(
                entradas=Sum('valor', filter=Q(tipo='Receita')),
                consumo=Sum('valor', filter=Q(tipo__in=['Despesa', 'Investimento'])),
            )
        )
        entradas_ciclo = totais_ciclo['entradas'] or Decimal('0.00')
        consumo_ciclo = totais_ciclo['consumo'] or Decimal('0.00')
        if entradas_ciclo > 0:
            burn_rate_periodo = min(int((consumo_ciclo / entradas_ciclo) * 100), 100)

    inicio_janela_media = _add_months(_month_start(data_fim), -3)
    base_media = (
        Movimentacao.objects
        .annotate(data_referencia=Coalesce('data_pagamento', 'data_vencimento'))
        .filter(data_referencia__gte=inicio_janela_media, data_referencia__lte=data_fim)
    )
    if filtro_conta_id is not None:
        base_media = base_media.filter(conta_bancaria_id=filtro_conta_id)

    media_qs = base_media.aggregate(
        despesas=Sum('valor', filter=Q(tipo='Despesa')),
        investimentos=Sum('valor', filter=Q(tipo='Investimento')),
    )
    media_consumo_3m = ((media_qs['despesas'] or Decimal('0.00')) + (media_qs['investimentos'] or Decimal('0.00'))) / Decimal('3.00')

    consumo_mes_qs = (
        Movimentacao.objects
        .annotate(data_referencia=Coalesce('data_pagamento', 'data_vencimento'))
        .filter(
            data_referencia__month=data_fim.month,
            data_referencia__year=data_fim.year,
        )
    )
    if filtro_conta_id is not None:
        consumo_mes_qs = consumo_mes_qs.filter(conta_bancaria_id=filtro_conta_id)

    consumo_mes = consumo_mes_qs.aggregate(
        despesas=Sum('valor', filter=Q(tipo='Despesa')),
        investimentos=Sum('valor', filter=Q(tipo='Investimento')),
    )
    consumo_mes_atual = (consumo_mes['despesas'] or Decimal('0.00')) + (consumo_mes['investimentos'] or Decimal('0.00'))

    alertas = []
    if pendentes_vencidos > 0:
        alertas.append(
            {
                'titulo': 'Pendencias vencidas em aberto',
                'descricao': f'{pendentes_vencidos} movimentacao(oes) pendente(s) com vencimento anterior a hoje.',
                'nivel': 'alto',
            }
        )

    if media_consumo_3m > 0 and consumo_mes_atual > media_consumo_3m * Decimal('1.15'):
        excesso = ((consumo_mes_atual - media_consumo_3m) / media_consumo_3m) * Decimal('100')
        alertas.append(
            {
                'titulo': 'Consumo acima da media recente',
                'descricao': f'O consumo de despesas+investimentos no mes esta {int(excesso)}% acima da media movel de 3 meses.',
                'nivel': 'medio',
            }
        )

    if top_planos and top_planos[0]['percentual'] >= 45:
        principal = top_planos[0]
        alertas.append(
            {
                'titulo': 'Alta concentracao por categoria',
                'descricao': f"{principal['codigo']} - {principal['nome']} concentra {principal['percentual']:.1f}% do consumo do periodo.",
                'nivel': 'medio',
            }
        )

    if total_efetivadas >= 5 and percentual_no_prazo < 70:
        alertas.append(
            {
                'titulo': 'Baixa efetivacao no prazo',
                'descricao': f'Apenas {percentual_no_prazo}% das movimentacoes efetivadas foram pagas ate o vencimento.',
                'nivel': 'alto',
            }
        )

    context = {
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'contas_bancarias': contas_bancarias,
        'tipos_disponiveis': tipos_disponiveis,
        'status_disponiveis': status_disponiveis,
        'filtro_conta_bancaria_id': filtro_conta_id,
        'filtro_tipo': tipo,
        'filtro_status': status,
        'receitas': receitas,
        'despesas': despesas,
        'investimentos': investimentos,
        'transferencias_saida': transferencias_saida,
        'saldo_liquido': saldo_liquido,
        'burn_rate_periodo': burn_rate_periodo,
        'pendentes_vencidos': pendentes_vencidos,
        'percentual_no_prazo': percentual_no_prazo,
        'total_efetivadas': total_efetivadas,
        'tendencia_mensal': tendencia_mensal,
        'chart_tendencia': {
            'labels': tendencia_labels,
            'receitas': tendencia_receitas,
            'despesas': tendencia_despesas,
            'investimentos': tendencia_investimentos,
        },
        'chart_despesas_recorrentes': {
            'labels': tendencia_labels,
            'variavel': despesas_recorrentes_variavel,
            'fixa': despesas_recorrentes_fixa,
        },
        'chart_despesas_ocasionais': {
            'labels': tendencia_labels,
            'anual': despesas_ocasionais_anual,
            'unica': despesas_ocasionais_unica,
        },
        'chart_futuros_pendentes': {
            'labels': futuros_pendentes_labels,
            'totais': futuros_pendentes_totais,
        },
        'chart_investimentos_plano': investimentos_por_plano,
        'top_despesas': top_despesas,
        'top_investimentos': top_investimentos,
        'alertas': alertas,
    }

    return render(request, 'core/dashboard_analitico.html', context)

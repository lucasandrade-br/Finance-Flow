from calendar import monthrange
from datetime import date

from django.db import transaction
from django.utils.dateparse import parse_date

from apps.transacoes.models import LancamentoFuturo, Movimentacao, TransacaoRecorrente


def _coerce_to_date(value):
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        parsed = parse_date(value)
        if parsed:
            return parsed
    raise ValueError('Data inválida para cálculo de vencimento do ciclo.')


def _data_vencimento_do_ciclo(ciclo, dia_vencimento):
    data_inicio = _coerce_to_date(ciclo.data_inicio)
    ano = data_inicio.year
    mes = data_inicio.month
    ultimo_dia = monthrange(ano, mes)[1]
    dia = max(1, min(int(dia_vencimento), ultimo_dia))
    return date(ano, mes, dia)


def injetar_movimentacoes_no_ciclo(ciclo):
    with transaction.atomic():
        recorrentes_ativas = TransacaoRecorrente.objects.filter(status_ativa=True).prefetch_related('tags')

        for recorrente in recorrentes_ativas:
            data_vencimento = _data_vencimento_do_ciclo(ciclo, recorrente.dia_vencimento)

            ja_existe = Movimentacao.objects.filter(
                ciclo=ciclo,
                descricao=recorrente.descricao,
                valor=recorrente.valor_base,
                plano_conta=recorrente.plano_conta,
                conta_bancaria=recorrente.conta_bancaria,
                data_vencimento=data_vencimento,
            ).exists()
            if ja_existe:
                continue

            mov = Movimentacao.objects.create(
                tipo=recorrente.tipo,
                valor=recorrente.valor_base,
                formato_pagamento=recorrente.formato_pagamento,
                frequencia=recorrente.frequencia,
                descricao=recorrente.descricao,
                data_vencimento=data_vencimento,
                plano_conta=recorrente.plano_conta,
                conta_bancaria=recorrente.conta_bancaria,
                ciclo=ciclo,
                cofre=recorrente.cofre,
            )
            mov.tags.set(recorrente.tags.all())

        futuros = LancamentoFuturo.objects.filter(
            data_vencimento__range=(ciclo.data_inicio, ciclo.data_fim),
            status=LancamentoFuturo.Status.PENDENTE,
        ).prefetch_related('tags')

        for futuro in futuros:
            ja_existe = Movimentacao.objects.filter(
                ciclo=ciclo,
                descricao=futuro.descricao,
                valor=futuro.valor,
                plano_conta=futuro.plano_conta,
                conta_bancaria=futuro.conta_bancaria,
                data_vencimento=futuro.data_vencimento,
            ).exists()
            if ja_existe:
                futuro.status = LancamentoFuturo.Status.INJETADO
                futuro.save(update_fields=['status', 'updated_at'])
                continue

            mov = Movimentacao.objects.create(
                tipo=futuro.tipo,
                valor=futuro.valor,
                formato_pagamento=futuro.formato_pagamento,
                frequencia=futuro.frequencia,
                descricao=futuro.descricao,
                comprovante=futuro.comprovante,
                data_vencimento=futuro.data_vencimento,
                parcela_atual=futuro.parcela_atual,
                total_parcelas=futuro.total_parcelas,
                plano_conta=futuro.plano_conta,
                conta_bancaria=futuro.conta_bancaria,
                ciclo=ciclo,
                cofre=futuro.cofre,
            )
            mov.tags.set(futuro.tags.all())

            futuro.status = LancamentoFuturo.Status.INJETADO
            futuro.save(update_fields=['status', 'updated_at'])

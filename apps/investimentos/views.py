from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Case, DecimalField, F, Sum, Value, When
from django.db.models.functions import Coalesce, ExtractMonth, ExtractYear
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.contas.models import ContaBancaria
from apps.investimentos.models import MetaFinanceira, MetaParcelaMensal
from apps.transacoes.models import Movimentacao, TipoTransacao


STATUS_CONSOLIDADO = [Movimentacao.Status.EFETIVADO, Movimentacao.Status.VALIDADO]


def _month_start(dt):
	return dt.replace(day=1)


def _add_month(dt):
	if dt.month == 12:
		return dt.replace(year=dt.year + 1, month=1, day=1)
	return dt.replace(month=dt.month + 1, day=1)


def _iter_months(start_date, end_date):
	current = _month_start(start_date)
	end = _month_start(end_date)
	while current <= end:
		yield current
		current = _add_month(current)


def _to_decimal(value, default=Decimal('0')):
	try:
		return Decimal(str(value or '')).quantize(Decimal('0.01'))
	except (InvalidOperation, TypeError, ValueError):
		return default


def _distribuir_valor_mensal(valor_alvo, quantidade):
	if quantidade <= 0:
		return []
	total_centavos = int((valor_alvo * 100).to_integral_value())
	base = total_centavos // quantidade
	resto = total_centavos % quantidade
	valores = []
	for idx in range(quantidade):
		centavos = base + (1 if idx < resto else 0)
		valores.append((Decimal(centavos) / Decimal('100')).quantize(Decimal('0.01')))
	return valores


def _regerar_parcelas_mensais(meta):
	competencias = list(_iter_months(meta.data_inicio, meta.data_fim))
	if not competencias:
		return False

	valores = _distribuir_valor_mensal(meta.valor_alvo, len(competencias))
	parcelas = []
	for idx, competencia in enumerate(competencias, start=1):
		parcelas.append(
			MetaParcelaMensal(
				meta=meta,
				competencia=competencia,
				valor_planejado=valores[idx - 1],
				ordem_mes=idx,
			)
		)

	meta.parcelas_mensais.all().delete()
	MetaParcelaMensal.objects.bulk_create(parcelas)
	return True


def _saldo_atual_por_contas(conta_ids):
	if not conta_ids:
		return {}

	agregados = (
		Movimentacao.objects.filter(conta_bancaria_id__in=conta_ids, status__in=STATUS_CONSOLIDADO)
		.values('conta_bancaria_id')
		.annotate(
			total_creditos=Coalesce(
				Sum(
					Case(
						When(tipo__in=[TipoTransacao.RECEITA, TipoTransacao.TRANSFERENCIA_ENTRADA], then=F('valor')),
						default=Value(0),
						output_field=DecimalField(max_digits=14, decimal_places=2),
					)
				),
				Value(Decimal('0.00')),
			),
			total_debitos=Coalesce(
				Sum(
					Case(
						When(
							tipo__in=[
								TipoTransacao.DESPESA,
								TipoTransacao.INVESTIMENTO,
								TipoTransacao.TRANSFERENCIA_SAIDA,
							],
							then=F('valor'),
						),
						default=Value(0),
						output_field=DecimalField(max_digits=14, decimal_places=2),
					)
				),
				Value(Decimal('0.00')),
			),
		)
	)

	mapa = {conta_id: Decimal('0.00') for conta_id in conta_ids}
	for item in agregados:
		conta_id = item['conta_bancaria_id']
		mapa[conta_id] = (item['total_creditos'] - item['total_debitos']).quantize(Decimal('0.01'))
	return mapa


def _realizado_mensal_meta(meta):
	base = (
		Movimentacao.objects.filter(
			conta_bancaria_id=meta.conta_bancaria_id,
			tipo=TipoTransacao.TRANSFERENCIA_ENTRADA,
			status__in=STATUS_CONSOLIDADO,
		)
		.annotate(data_referencia=Coalesce('data_pagamento', 'data_vencimento'))
		.filter(data_referencia__range=(meta.data_inicio, meta.data_fim))
		.annotate(ano=ExtractYear('data_referencia'), mes=ExtractMonth('data_referencia'))
		.values('ano', 'mes')
		.annotate(total=Coalesce(Sum('valor'), Value(Decimal('0.00'))))
	)
	resultado = {}
	for item in base:
		competencia = date(item['ano'], item['mes'], 1)
		resultado[competencia] = item['total'].quantize(Decimal('0.01'))
	return resultado


@require_http_methods(["GET"])
def lista_metas(request):
	metas = list(MetaFinanceira.objects.select_related('conta_bancaria').order_by('-created_at'))
	conta_ids = [m.conta_bancaria_id for m in metas]
	saldo_movimentos_map = _saldo_atual_por_contas(conta_ids)

	for meta in metas:
		saldo_mov = saldo_movimentos_map.get(meta.conta_bancaria_id, Decimal('0.00'))
		saldo_atual = (meta.conta_bancaria.saldo_inicial + saldo_mov).quantize(Decimal('0.01'))
		meta.saldo_atual = saldo_atual

		realizado_total = sum(_realizado_mensal_meta(meta).values(), Decimal('0.00')).quantize(Decimal('0.01'))
		percentual = Decimal('0.00')
		if meta.valor_alvo and meta.valor_alvo > 0:
			percentual = ((realizado_total / meta.valor_alvo) * Decimal('100')).quantize(Decimal('0.01'))
		meta.realizado_total = realizado_total
		meta.percentual_alcancado = percentual

	context = {
		'metas': metas,
	}
	return render(request, 'investimentos/metas/lista.html', context)


@require_http_methods(["GET", "POST"])
def nova_meta(request):
	contas = ContaBancaria.objects.order_by('nome')
	erro_formulario = None

	if request.method == 'POST':
		nome = (request.POST.get('nome') or '').strip()
		conta_id = request.POST.get('conta_bancaria_id')
		valor_alvo = _to_decimal(request.POST.get('valor_alvo'))
		data_inicio_raw = request.POST.get('data_inicio')
		data_fim_raw = request.POST.get('data_fim')

		try:
			data_inicio = date.fromisoformat(data_inicio_raw)
			data_fim = date.fromisoformat(data_fim_raw)
		except (TypeError, ValueError):
			data_inicio = None
			data_fim = None

		if not nome:
			erro_formulario = 'Informe um nome para a meta.'
		elif not conta_id:
			erro_formulario = 'Selecione uma conta bancária.'
		elif valor_alvo <= 0:
			erro_formulario = 'O valor alvo deve ser maior que zero.'
		elif not data_inicio or not data_fim:
			erro_formulario = 'Informe um período válido para a meta.'
		elif data_fim < data_inicio:
			erro_formulario = 'A data final deve ser igual ou posterior à data inicial.'
		else:
			competencias = list(_iter_months(data_inicio, data_fim))
			if not competencias:
				erro_formulario = 'Não foi possível gerar competências mensais para o período informado.'
			else:
				with transaction.atomic():
					meta = MetaFinanceira.objects.create(
						nome=nome,
						conta_bancaria_id=conta_id,
						valor_alvo=valor_alvo,
						data_inicio=data_inicio,
						data_fim=data_fim,
						status=MetaFinanceira.Status.ATIVA,
					)
					_regerar_parcelas_mensais(meta)
				return redirect('investimentos:roteiro_meta', meta_id=meta.id)

	context = {
		'contas': contas,
		'erro_formulario': erro_formulario,
		'hoje': date.today(),
	}
	return render(request, 'investimentos/metas/nova.html', context)


@require_http_methods(["GET", "POST"])
def roteiro_meta(request, meta_id):
	meta = get_object_or_404(MetaFinanceira.objects.select_related('conta_bancaria'), pk=meta_id)
	parcelas = list(meta.parcelas_mensais.order_by('competencia'))
	erro_formulario = None

	if request.method == 'POST':
		soma = Decimal('0.00')
		for parcela in parcelas:
			valor = _to_decimal(request.POST.get(f'valor_planejado_{parcela.id}'))
			if valor < 0:
				erro_formulario = 'Os valores mensais não podem ser negativos.'
				break
			parcela.valor_planejado = valor
			soma += valor

		acao = request.POST.get('acao') or 'rascunho'
		if not erro_formulario and acao == 'ativar' and soma.quantize(Decimal('0.01')) != meta.valor_alvo.quantize(Decimal('0.01')):
			erro_formulario = 'A soma das parcelas deve ser igual ao valor alvo para ativar a meta.'

		if not erro_formulario:
			MetaParcelaMensal.objects.bulk_update(parcelas, ['valor_planejado', 'updated_at'])
			if acao == 'ativar':
				meta.status = MetaFinanceira.Status.ATIVA
			else:
				meta.status = MetaFinanceira.Status.RASCUNHO
			meta.save(update_fields=['status', 'updated_at'])
			return redirect('investimentos:roteiro_meta', meta_id=meta.id)

	realizado_map = _realizado_mensal_meta(meta)
	linhas = []
	total_planejado = Decimal('0.00')
	total_realizado = Decimal('0.00')
	for parcela in parcelas:
		realizado = realizado_map.get(parcela.competencia, Decimal('0.00'))
		total_planejado += parcela.valor_planejado
		total_realizado += realizado
		linhas.append({
			'parcela': parcela,
			'realizado': realizado,
			'diferenca': (realizado - parcela.valor_planejado).quantize(Decimal('0.01')),
		})

	context = {
		'meta': meta,
		'linhas': linhas,
		'total_planejado': total_planejado.quantize(Decimal('0.01')),
		'total_realizado': total_realizado.quantize(Decimal('0.01')),
		'contas': ContaBancaria.objects.order_by('nome'),
		'erro_formulario': erro_formulario,
	}
	return render(request, 'investimentos/metas/roteiro.html', context)


@require_http_methods(["POST"])
def editar_meta(request, meta_id):
	meta = get_object_or_404(MetaFinanceira, pk=meta_id)

	nome = (request.POST.get('nome') or '').strip()
	conta_id = request.POST.get('conta_bancaria_id')
	valor_alvo = _to_decimal(request.POST.get('valor_alvo'))
	data_inicio_raw = request.POST.get('data_inicio')
	data_fim_raw = request.POST.get('data_fim')

	try:
		data_inicio = date.fromisoformat(data_inicio_raw)
		data_fim = date.fromisoformat(data_fim_raw)
	except (TypeError, ValueError):
		return redirect('investimentos:roteiro_meta', meta_id=meta.id)

	if not nome or not conta_id or valor_alvo <= 0 or data_fim < data_inicio:
		return redirect('investimentos:roteiro_meta', meta_id=meta.id)

	with transaction.atomic():
		meta.nome = nome
		meta.conta_bancaria_id = conta_id
		meta.valor_alvo = valor_alvo
		meta.data_inicio = data_inicio
		meta.data_fim = data_fim
		meta.save(update_fields=['nome', 'conta_bancaria', 'valor_alvo', 'data_inicio', 'data_fim', 'updated_at'])

		if not _regerar_parcelas_mensais(meta):
			return redirect('investimentos:roteiro_meta', meta_id=meta.id)

	return redirect('investimentos:roteiro_meta', meta_id=meta.id)


@require_http_methods(["POST"])
def excluir_meta(request, meta_id):
	meta = get_object_or_404(MetaFinanceira, pk=meta_id)
	meta.delete()
	return redirect('investimentos:lista_metas')


@require_http_methods(["GET"])
def painel_meta(request, meta_id):
	meta = get_object_or_404(MetaFinanceira.objects.select_related('conta_bancaria'), pk=meta_id)
	parcelas = list(meta.parcelas_mensais.order_by('competencia'))
	realizado_map = _realizado_mensal_meta(meta)

	labels = []
	planejado_series = []
	realizado_series = []
	acumulado_planejado_series = []
	acumulado_realizado_series = []

	acumulado_planejado = Decimal('0.00')
	acumulado_realizado = Decimal('0.00')
	for parcela in parcelas:
		realizado = realizado_map.get(parcela.competencia, Decimal('0.00'))
		acumulado_planejado += parcela.valor_planejado
		acumulado_realizado += realizado

		labels.append(parcela.competencia.strftime('%m/%Y'))
		planejado_series.append(float(parcela.valor_planejado))
		realizado_series.append(float(realizado))
		acumulado_planejado_series.append(float(acumulado_planejado))
		acumulado_realizado_series.append(float(acumulado_realizado))

	percentual = Decimal('0.00')
	if meta.valor_alvo > 0:
		percentual = ((acumulado_realizado / meta.valor_alvo) * Decimal('100')).quantize(Decimal('0.01'))

	context = {
		'meta': meta,
		'valor_realizado': acumulado_realizado.quantize(Decimal('0.01')),
		'valor_faltante': (meta.valor_alvo - acumulado_realizado).quantize(Decimal('0.01')),
		'percentual_alcancado': percentual,
		'labels': labels,
		'planejado_series': planejado_series,
		'realizado_series': realizado_series,
		'acumulado_planejado_series': acumulado_planejado_series,
		'acumulado_realizado_series': acumulado_realizado_series,
	}
	return render(request, 'investimentos/metas/painel.html', context)

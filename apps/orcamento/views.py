from calendar import monthrange
from datetime import date, timedelta

from django.db.models import Q, Sum
from django.db.models.functions import Coalesce, ExtractMonth, ExtractYear
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.dateparse import parse_date
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from decimal import Decimal

from apps.contas.models import ContaBancaria, PlanoConta, Tag
from apps.orcamento.models import Ciclo, MacroOrcamento, MovimentacaoOrcamento
from apps.orcamento.services import injetar_movimentacoes_no_ciclo
from apps.transacoes.models import FormatoPagamento, Frequencia, LancamentoFuturo, Movimentacao


MESES_ANO = [
	(1, 'JAN'),
	(2, 'FEV'),
	(3, 'MAR'),
	(4, 'ABR'),
	(5, 'MAI'),
	(6, 'JUN'),
	(7, 'JUL'),
	(8, 'AGO'),
	(9, 'SET'),
	(10, 'OUT'),
	(11, 'NOV'),
	(12, 'DEZ'),
]


def formatar_moeda_br(valor):
	"""Formata Decimal para padrao BRL simples: 1.234,56."""
	valor = Decimal(valor or 0)
	texto = f'{valor:,.2f}'
	return texto.replace(',', 'X').replace('.', ',').replace('X', '.')


def simulacao_capital(request, ano=None):
	ano_param = ano or request.GET.get('ano')
	try:
		ano_selecionado = int(ano_param) if ano_param is not None else timezone.localdate().year
	except (TypeError, ValueError):
		ano_selecionado = timezone.localdate().year

	saldo_inicial_raw = (request.GET.get('saldo_inicial') or '0').strip()
	try:
		saldo_inicial = Decimal(saldo_inicial_raw.replace(',', '.'))
	except Exception:
		saldo_inicial = Decimal('0.00')

	planejamento_qs = (
		MacroOrcamento.objects.filter(ano=ano_selecionado)
		.select_related('plano_conta')
	)

	entradas_planejadas_mes = {mes: Decimal('0.00') for mes, _ in MESES_ANO}
	saidas_planejadas_mes = {mes: Decimal('0.00') for mes, _ in MESES_ANO}
	for item in planejamento_qs:
		if item.plano_conta.tipo_natureza == 'Receita':
			entradas_planejadas_mes[item.mes] += item.valor_teto
		else:
			saidas_planejadas_mes[item.mes] += item.valor_teto

	movimentacoes_orcamento = MovimentacaoOrcamento.objects.filter(status_ativa=True)
	entradas_obrigatorias_mes = {mes: Decimal('0.00') for mes, _ in MESES_ANO}
	saidas_obrigatorias_mes = {mes: Decimal('0.00') for mes, _ in MESES_ANO}
	for registro in movimentacoes_orcamento:
		if registro.frequencia == MovimentacaoOrcamento.Frequencia.ANUAL:
			if not registro.mes_referencia:
				continue
			meses_aplicacao = [registro.mes_referencia]
		else:
			meses_aplicacao = [mes for mes, _ in MESES_ANO]

		for mes in meses_aplicacao:
			if registro.tipo == MovimentacaoOrcamento.Tipo.RECEITA:
				entradas_obrigatorias_mes[mes] += registro.valor
			else:
				saidas_obrigatorias_mes[mes] += registro.valor

	entradas_realizadas_mes = {mes: Decimal('0.00') for mes, _ in MESES_ANO}
	saidas_realizadas_mes = {mes: Decimal('0.00') for mes, _ in MESES_ANO}
	movimentacoes_realizadas = (
		Movimentacao.objects.annotate(data_referencia=Coalesce('data_pagamento', 'data_vencimento'))
		.filter(
			data_referencia__year=ano_selecionado,
			status__in=[Movimentacao.Status.EFETIVADO, Movimentacao.Status.VALIDADO],
		)
	)
	for movimento in movimentacoes_realizadas:
		mes_referencia = movimento.data_referencia.month if movimento.data_referencia else None
		if not mes_referencia:
			continue

		if movimento.tipo == 'Receita':
			entradas_realizadas_mes[mes_referencia] += movimento.valor
		elif movimento.tipo in ('Despesa', 'Investimento'):
			saidas_realizadas_mes[mes_referencia] += movimento.valor

	simulacao_mensal = []
	saldo_acumulado = saldo_inicial
	saldo_acumulado_realizado = saldo_inicial
	mes_atual = timezone.localdate().month
	for mes, mes_label in MESES_ANO:
		entrada_planejada = entradas_planejadas_mes[mes]
		saida_planejada = saidas_planejadas_mes[mes]
		saida_obrigatoria = saidas_obrigatorias_mes[mes]
		entrada_realizada = entradas_realizadas_mes[mes]
		saida_realizada = saidas_realizadas_mes[mes]
		folga_saida = saida_planejada - saida_obrigatoria
		variacao_mes = entrada_planejada - saida_obrigatoria
		variacao_mes_realizado = entrada_realizada - saida_realizada
		saldo_acumulado += variacao_mes
		saldo_acumulado_realizado += variacao_mes_realizado

		simulacao_mensal.append(
			{
				'mes': mes,
				'mes_label': mes_label,
				'entrada_planejada': entrada_planejada,
				'saida_planejada': saida_planejada,
				'saida_obrigatoria': saida_obrigatoria,
				'entrada_realizada': entrada_realizada,
				'saida_realizada': saida_realizada,
				'folga_saida': folga_saida,
				'saldo_acumulado': saldo_acumulado,
				'saldo_acumulado_realizado': saldo_acumulado_realizado,
			}
		)

	saldo_atual_projetado = next(
		(item['saldo_acumulado'] for item in simulacao_mensal if item['mes'] == mes_atual),
		saldo_inicial,
	)

	resumo = {
		'total_entradas_planejadas': sum((item['entrada_planejada'] for item in simulacao_mensal), Decimal('0.00')),
		'total_saidas_planejadas': sum((item['saida_planejada'] for item in simulacao_mensal), Decimal('0.00')),
		'total_saidas_obrigatorias': sum((item['saida_obrigatoria'] for item in simulacao_mensal), Decimal('0.00')),
		'total_entradas_realizadas': sum((item['entrada_realizada'] for item in simulacao_mensal), Decimal('0.00')),
		'total_saidas_realizadas': sum((item['saida_realizada'] for item in simulacao_mensal), Decimal('0.00')),
		'saldo_final_realizado': saldo_acumulado_realizado,
		'saldo_final_ano': saldo_acumulado,
		'saldo_atual_projetado': saldo_atual_projetado,
	}

	chart_labels = [item['mes_label'] for item in simulacao_mensal]
	chart_entradas = [float(item['entrada_planejada']) for item in simulacao_mensal]
	chart_saidas = [float(item['saida_obrigatoria']) for item in simulacao_mensal]
	chart_saldo = [float(item['saldo_acumulado']) for item in simulacao_mensal]
	chart_entradas_realizadas = [float(item['entrada_realizada']) for item in simulacao_mensal]
	chart_saidas_realizadas = [float(item['saida_realizada']) for item in simulacao_mensal]
	chart_saldo_realizado = [float(item['saldo_acumulado_realizado']) for item in simulacao_mensal]

	return render(
		request,
		'orcamento/simulacao_capital.html',
		{
			'ano_selecionado': ano_selecionado,
			'ano_anterior_link': ano_selecionado - 1,
			'ano_proximo_link': ano_selecionado + 1,
			'saldo_inicial': saldo_inicial,
			'simulacao_mensal': simulacao_mensal,
			'resumo': resumo,
			'chart_labels': chart_labels,
			'chart_entradas': chart_entradas,
			'chart_saidas': chart_saidas,
			'chart_saldo': chart_saldo,
			'chart_entradas_realizadas': chart_entradas_realizadas,
			'chart_saidas_realizadas': chart_saidas_realizadas,
			'chart_saldo_realizado': chart_saldo_realizado,
		},
	)


def _dados_form_mov_orcamento():
	return {
		'contas': ContaBancaria.objects.all().order_by('nome'),
		'plano_contas': PlanoConta.objects.all().order_by('codigo', 'nome'),
		'tags': Tag.objects.all().order_by('nome'),
		'hoje': timezone.localdate(),
		'form_data': {},
		'form_data_enviado': False,
		'selected_tags_data': [],
	}


def _serializar_tags_selecionadas(tag_ids):
	tag_ids = [str(tag_id) for tag_id in (tag_ids or []) if str(tag_id)]
	if not tag_ids:
		return []
	tags = Tag.objects.filter(id__in=tag_ids).values('id', 'nome', 'plano_conta_id')
	return [
		{
			'id': str(item['id']),
			'text': item['nome'],
			'plano_conta_id': item['plano_conta_id'],
		}
		for item in tags
	]


def _form_data_mov_orcamento_from_post(request):
	return {
		'tipo': request.POST.get('tipo'),
		'valor': request.POST.get('valor'),
		'plano_conta_id': request.POST.get('plano_conta_id'),
		'conta_bancaria_id': request.POST.get('conta_bancaria_id'),
		'descricao': (request.POST.get('descricao') or '').strip(),
		'frequencia': request.POST.get('frequencia', MovimentacaoOrcamento.Frequencia.MENSAL),
		'dia_referencia': request.POST.get('dia_referencia') or '',
		'mes_referencia': request.POST.get('mes_referencia') or '',
		'status_ativa': bool(request.POST.get('status_ativa')),
		'tag_ids': request.POST.getlist('tags'),
	}


def _form_data_mov_orcamento_from_registro(registro):
	return {
		'tipo': registro.tipo,
		'valor': str(registro.valor),
		'plano_conta_id': str(registro.plano_conta_id) if registro.plano_conta_id else '',
		'conta_bancaria_id': str(registro.conta_bancaria_id) if registro.conta_bancaria_id else '',
		'descricao': registro.descricao or '',
		'frequencia': registro.frequencia,
		'dia_referencia': str(registro.dia_referencia) if registro.dia_referencia else '',
		'mes_referencia': str(registro.mes_referencia) if registro.mes_referencia else '',
		'status_ativa': bool(registro.status_ativa),
		'tag_ids': [str(tag_id) for tag_id in registro.tags.values_list('id', flat=True)],
	}


def _parse_decimal_ptbr(value):
	texto = (value or '').strip()
	if not texto:
		return None


def _sugerir_data_vencimento_orcamento(registro, ano_atual):
	if (
		registro.frequencia == MovimentacaoOrcamento.Frequencia.ANUAL
		and registro.mes_referencia
		and registro.dia_referencia
	):
		dia_maximo = monthrange(ano_atual, registro.mes_referencia)[1]
		dia = min(registro.dia_referencia, dia_maximo)
		return date(ano_atual, registro.mes_referencia, dia)
	return timezone.localdate()
	if ',' in texto and '.' in texto:
		texto = texto.replace('.', '').replace(',', '.')
	elif ',' in texto:
		texto = texto.replace(',', '.')
	try:
		return Decimal(texto)
	except Exception:
		return None


def _salvar_movimentacao_orcamento(request, registro=None):
	tipo = request.POST.get('tipo')
	valor = _parse_decimal_ptbr(request.POST.get('valor'))
	plano_conta_id = request.POST.get('plano_conta_id')
	conta_bancaria_id = request.POST.get('conta_bancaria_id')
	descricao = (request.POST.get('descricao') or '').strip()
	frequencia = request.POST.get('frequencia', MovimentacaoOrcamento.Frequencia.MENSAL)
	dia_referencia = request.POST.get('dia_referencia') or None
	mes_referencia = request.POST.get('mes_referencia') or None
	status_ativa = bool(request.POST.get('status_ativa'))
	tag_ids = request.POST.getlist('tags')

	if valor is None:
		return None, 'Informe um valor válido para a movimentação.'
	if not tipo or not plano_conta_id or not conta_bancaria_id:
		return None, 'Preencha os campos obrigatórios: tipo, plano de conta e conta bancária.'

	if frequencia == MovimentacaoOrcamento.Frequencia.ANUAL:
		if not dia_referencia or not mes_referencia:
			return None, 'Para frequência anual, informe obrigatoriamente dia e mês.'
	else:
		dia_referencia = None
		mes_referencia = None

	if registro is None:
		registro = MovimentacaoOrcamento.objects.create(
			tipo=tipo,
			valor=valor,
			plano_conta_id=plano_conta_id,
			conta_bancaria_id=conta_bancaria_id,
			descricao=descricao,
			frequencia=frequencia,
			dia_referencia=dia_referencia,
			mes_referencia=mes_referencia,
			status_ativa=status_ativa,
		)
	else:
		registro.tipo = tipo
		registro.valor = valor
		registro.plano_conta_id = plano_conta_id
		registro.conta_bancaria_id = conta_bancaria_id
		registro.descricao = descricao
		registro.frequencia = frequencia
		registro.dia_referencia = dia_referencia
		registro.mes_referencia = mes_referencia
		registro.status_ativa = status_ativa
		registro.save()

	registro.tags.set(tag_ids)
	return registro, None


def lista_movimentacoes_orcamento(request):
	tipo = (request.GET.get('tipo') or '').strip()
	frequencia = (request.GET.get('frequencia') or '').strip()
	mes_referencia = (request.GET.get('mes_referencia') or '').strip()
	query = (request.GET.get('q') or '').strip()

	registros = MovimentacaoOrcamento.objects.select_related(
		'plano_conta',
		'conta_bancaria',
	).prefetch_related('tags').order_by('tipo', 'plano_conta__codigo', 'descricao')

	if tipo:
		registros = registros.filter(tipo=tipo)
	if frequencia:
		registros = registros.filter(frequencia=frequencia)
	if mes_referencia:
		try:
			mes_referencia_int = int(mes_referencia)
			if 1 <= mes_referencia_int <= 12:
				# Regra solicitada: filtro por mes referencia retorna apenas registros anuais daquele mes.
				registros = registros.filter(
					frequencia=MovimentacaoOrcamento.Frequencia.ANUAL,
					mes_referencia=mes_referencia_int,
				)
				frequencia = MovimentacaoOrcamento.Frequencia.ANUAL
			else:
				mes_referencia = ''
		except (TypeError, ValueError):
			mes_referencia = ''
	if query:
		registros = registros.filter(Q(descricao__icontains=query) | Q(plano_conta__nome__icontains=query) | Q(plano_conta__codigo__icontains=query))

	registros = list(registros)
	ano_atual = timezone.localdate().year
	for item in registros:
		data_sugerida = _sugerir_data_vencimento_orcamento(item, ano_atual)
		item.data_sugerida_vencimento = data_sugerida.strftime('%Y-%m-%d')
		item.frequencia_futuro_sugerida = (
			Frequencia.ANUAL
			if item.frequencia == MovimentacaoOrcamento.Frequencia.ANUAL
			else Frequencia.VARIAVEL
		)

	return render(
		request,
		'orcamento/movimentacoes/lista.html',
		{
			'registros': registros,
			'tipo': tipo,
			'frequencia': frequencia,
			'mes_referencia': mes_referencia,
			'query': query,
			'tipos_transacao': MovimentacaoOrcamento.Tipo.choices,
			'frequencias': MovimentacaoOrcamento.Frequencia.choices,
			'meses_ano': MESES_ANO,
			'formatos_pagamento': FormatoPagamento.choices,
		},
	)


@require_http_methods(["POST"])
def lancar_movimentacao_orcamento_futuro(request, registro_id):
	registro = get_object_or_404(MovimentacaoOrcamento, pk=registro_id)
	next_url = request.POST.get('next') or request.GET.get('next')
	if next_url and not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
		next_url = None

	data_vencimento = parse_date(request.POST.get('data_vencimento') or '')
	formato_pagamento = (request.POST.get('formato_pagamento') or '').strip()
	if formato_pagamento not in {item[0] for item in FormatoPagamento.choices}:
		formato_pagamento = FormatoPagamento.PIX

	if not data_vencimento:
		data_vencimento = _sugerir_data_vencimento_orcamento(registro, timezone.localdate().year)

	frequencia_futuro = (
		Frequencia.ANUAL
		if registro.frequencia == MovimentacaoOrcamento.Frequencia.ANUAL
		else Frequencia.VARIAVEL
	)

	futuro = LancamentoFuturo.objects.create(
		descricao=registro.descricao,
		tipo=registro.tipo,
		plano_conta_id=registro.plano_conta_id,
		conta_bancaria_id=registro.conta_bancaria_id,
		formato_pagamento=formato_pagamento,
		frequencia=frequencia_futuro,
		data_vencimento=data_vencimento,
		valor=registro.valor,
		status=LancamentoFuturo.Status.PENDENTE,
	)
	futuro.tags.set(registro.tags.all())

	return redirect(next_url or 'orcamento:lista_movimentacoes_orcamento')


@require_http_methods(["GET", "POST"])
def nova_movimentacao_orcamento(request):
	context = _dados_form_mov_orcamento()
	form_data = {}
	selected_tags_data = []
	form_data_enviado = False
	if request.method == 'POST':
		form_data = _form_data_mov_orcamento_from_post(request)
		selected_tags_data = _serializar_tags_selecionadas(form_data.get('tag_ids'))
		form_data_enviado = True
		registro, erro = _salvar_movimentacao_orcamento(request)
		if not erro:
			return redirect('orcamento:lista_movimentacoes_orcamento')
		context['erro_formulario'] = erro

	context.update(
		{
			'form_action': reverse('orcamento:nova_movimentacao_orcamento'),
			'cancel_url': reverse('orcamento:lista_movimentacoes_orcamento'),
			'titulo_form_orcamento': 'Nova Movimentação de Orçamento',
			'subtitulo_form_orcamento': 'Cadastre entradas e saídas base para simulação anual de capital.',
			'registro': None,
			'form_data': form_data,
			'form_data_enviado': form_data_enviado,
			'selected_tags_data': selected_tags_data,
		}
	)
	return render(request, 'orcamento/movimentacoes/form.html', context)


@require_http_methods(["GET", "POST"])
def editar_movimentacao_orcamento(request, registro_id):
	registro = get_object_or_404(MovimentacaoOrcamento, pk=registro_id)
	context = _dados_form_mov_orcamento()
	form_data = _form_data_mov_orcamento_from_registro(registro)
	selected_tags_data = _serializar_tags_selecionadas(form_data.get('tag_ids'))
	form_data_enviado = False

	if request.method == 'POST':
		form_data = _form_data_mov_orcamento_from_post(request)
		selected_tags_data = _serializar_tags_selecionadas(form_data.get('tag_ids'))
		form_data_enviado = True
		registro_salvo, erro = _salvar_movimentacao_orcamento(request, registro=registro)
		if not erro:
			return redirect('orcamento:lista_movimentacoes_orcamento')
		context['erro_formulario'] = erro
		context['registro'] = registro_salvo or registro
	else:
		context['registro'] = registro

	context.update(
		{
			'form_action': reverse('orcamento:editar_movimentacao_orcamento', args=[registro.id]),
			'cancel_url': reverse('orcamento:lista_movimentacoes_orcamento'),
			'titulo_form_orcamento': 'Editar Movimentação de Orçamento',
			'subtitulo_form_orcamento': 'Atualize os parâmetros para a simulação anual de capital.',
			'form_data': form_data,
			'form_data_enviado': form_data_enviado,
			'selected_tags_data': selected_tags_data,
		}
	)
	return render(request, 'orcamento/movimentacoes/form.html', context)


@require_http_methods(["POST"])
def excluir_movimentacao_orcamento(request, registro_id):
	registro = get_object_or_404(MovimentacaoOrcamento, pk=registro_id)
	registro.delete()
	return redirect('orcamento:lista_movimentacoes_orcamento')


def matriz_planejamento(request, ano=None):
	ano_param = ano or request.GET.get('ano')
	try:
		ano_selecionado = int(ano_param) if ano_param is not None else 2026
	except (TypeError, ValueError):
		ano_selecionado = 2026

	ano_anterior = ano_selecionado - 1
	tipos_disponiveis = [valor for valor, _ in PlanoConta.TipoNatureza.choices]
	filtro_tipo = request.GET.get('tipo') if request.method == 'GET' else request.POST.get('tipo')
	if filtro_tipo not in tipos_disponiveis:
		filtro_tipo = 'Todos'

	plano_contas_qs = PlanoConta.objects.all()
	if filtro_tipo != 'Todos':
		plano_contas_qs = plano_contas_qs.filter(tipo_natureza=filtro_tipo)
	plano_contas = list(plano_contas_qs.order_by('codigo', 'nome'))
	plano_ids = [plano.id for plano in plano_contas]
	plano_por_id = {plano.id: plano for plano in plano_contas}
	children_by_parent = {}
	for plano in plano_contas:
		children_by_parent.setdefault(plano.conta_pai_id, []).append(plano)
	parent_ids = {plano.conta_pai_id for plano in plano_contas if plano.conta_pai_id in plano_ids}

	def depth(plano):
		nivel = 0
		cursor = plano
		while cursor.conta_pai_id in plano_ids:
			pai = plano_por_id.get(cursor.conta_pai_id)
			if not pai:
				break
			nivel += 1
			cursor = pai
			if cursor.id == plano.id:
				break
		return nivel

	if request.method == 'POST':
		for plano in plano_contas:
			if plano.id in parent_ids:
				# Categorias pai sao apenas agregadas (somatorio), sem persistencia direta.
				continue
			for mes, _ in MESES_ANO:
				campo = f'valor_{plano.id}_{mes}'
				valor_raw = (request.POST.get(campo) or '').strip()

				existente = MacroOrcamento.objects.filter(
					ano=ano_selecionado,
					mes=mes,
					plano_conta=plano,
				).first()

				if not valor_raw:
					if existente:
						existente.delete()
					continue

				if ',' in valor_raw and '.' in valor_raw:
					# Ex.: 1.234,56 -> 1234.56
					valor_normalizado = valor_raw.replace('.', '').replace(',', '.')
				elif ',' in valor_raw:
					# Ex.: 1234,56 -> 1234.56
					valor_normalizado = valor_raw.replace(',', '.')
				else:
					# Ex.: 1234.56 (padrao de input number)
					valor_normalizado = valor_raw
				try:
					valor_decimal = Decimal(valor_normalizado)
				except Exception:
					continue

				if existente:
					existente.valor_teto = valor_decimal
					existente.save(update_fields=['valor_teto', 'updated_at'])
				else:
					MacroOrcamento.objects.create(
						ano=ano_selecionado,
						mes=mes,
						plano_conta=plano,
						valor_teto=valor_decimal,
					)

		# Higieniza registros antigos em categorias pai para garantir persistencia so em folhas.
		MacroOrcamento.objects.filter(
			ano=ano_selecionado,
			plano_conta_id__in=parent_ids,
			plano_conta__in=plano_contas,
		).delete()

		query_tipo = f'&tipo={filtro_tipo}' if filtro_tipo != 'Todos' else ''
		return redirect(f"{reverse('orcamento:matriz_planejamento')}?ano={ano_selecionado}{query_tipo}")

	planejamentos = MacroOrcamento.objects.filter(ano=ano_selecionado, plano_conta__in=plano_contas)
	planejado_por_categoria_mes = {
		(item.plano_conta_id, item.mes): item.valor_teto
		for item in planejamentos
	}

	real_ano_passado_qs = (
		Movimentacao.objects.annotate(
			data_referencia=Coalesce('data_pagamento', 'data_vencimento'),
			ano_referencia=ExtractYear(Coalesce('data_pagamento', 'data_vencimento')),
			mes_referencia=ExtractMonth(Coalesce('data_pagamento', 'data_vencimento')),
		)
		.filter(
			ano_referencia=ano_anterior,
			status__in=[Movimentacao.Status.EFETIVADO, Movimentacao.Status.VALIDADO],
			plano_conta__in=plano_contas,
		)
		.values('plano_conta_id', 'mes_referencia')
		.annotate(total=Coalesce(Sum('valor'), Decimal('0.00')))
	)
	real_por_categoria_mes = {
		(item['plano_conta_id'], item['mes_referencia']): item['total']
		for item in real_ano_passado_qs
	}

	planejado_total_cache = {}
	real_total_cache = {}

	def planejado_total(plano_id, mes):
		chave = (plano_id, mes)
		if chave in planejado_total_cache:
			return planejado_total_cache[chave]

		if plano_id in parent_ids:
			total = sum(
				(planejado_total(filho.id, mes) for filho in children_by_parent.get(plano_id, [])),
				Decimal('0.00'),
			)
		else:
			total = planejado_por_categoria_mes.get(chave, Decimal('0.00'))

		planejado_total_cache[chave] = total
		return total

	def real_total(plano_id, mes):
		chave = (plano_id, mes)
		if chave in real_total_cache:
			return real_total_cache[chave]

		if plano_id in parent_ids:
			total = sum(
				(real_total(filho.id, mes) for filho in children_by_parent.get(plano_id, [])),
				Decimal('0.00'),
			)
		else:
			total = real_por_categoria_mes.get(chave, Decimal('0.00'))

		real_total_cache[chave] = total
		return total

	matriz = []
	for plano in plano_contas:
		is_parent = plano.id in parent_ids
		linha_meses = []
		total_anual = Decimal('0.00')
		for mes, mes_label in MESES_ANO:
			chave_mes = (plano.id, mes)
			valor_planejado = planejado_total(plano.id, mes)
			valor_real = real_total(plano.id, mes)
			total_anual += valor_planejado
			linha_meses.append(
				{
					'mes': mes,
					'mes_label': mes_label,
					'valor_planejado': valor_planejado,
					'tem_valor_planejado': (chave_mes in planejado_por_categoria_mes) if not is_parent else True,
					'input_livre': not is_parent,
					'valor_real_ano_passado': valor_real,
					'valor_real_ano_passado_fmt': formatar_moeda_br(valor_real),
				}
			)

		matriz.append(
			{
				'plano_conta': plano,
				'is_parent': is_parent,
				'nivel': depth(plano),
				'meses': linha_meses,
				'total_anual': total_anual,
			}
		)

	return render(
		request,
		'orcamento/matriz_planejamento.html',
		{
			'ano_selecionado': ano_selecionado,
			'ano_anterior': ano_anterior,
			'ano_anterior_link': ano_selecionado - 1,
			'ano_proximo_link': ano_selecionado + 1,
			'meses_ano': MESES_ANO,
			'filtro_tipo': filtro_tipo,
			'tipos_disponiveis': tipos_disponiveis,
			'matriz': matriz,
		},
	)


def cockpit_ciclo(request):
	ciclo_ativo = Ciclo.objects.filter(status='Aberto').first()

	if not ciclo_ativo:
		return render(
			request,
			'orcamento/cockpit_ciclo.html',
			{
				'ciclo_ativo': None,
				'categorias_consumo': [],
				'hoje': timezone.localdate(),
			},
		)

	ano_ciclo = ciclo_ativo.data_inicio.year
	mes_ciclo = ciclo_ativo.data_inicio.month
	macro_orcamento_mes = MacroOrcamento.objects.filter(
		plano_conta__tipo_natureza='Despesa',
		ano=ano_ciclo,
		mes=mes_ciclo,
	)
	teto_por_plano = {
		item.plano_conta_id: item.valor_teto
		for item in macro_orcamento_mes
	}

	categorias_consumo = list(
		PlanoConta.objects.filter(tipo_natureza='Despesa')
		.annotate(
			total_gasto=Coalesce(
				Sum('movimentacoes__valor', filter=Q(movimentacoes__ciclo_id=ciclo_ativo.id)),
				Decimal('0.00'),
			)
		)
		.filter(total_gasto__gt=Decimal('0.00'))
	)

	hoje = timezone.localdate()
	inicio_mes_atual = hoje.replace(day=1)
	mes_base = inicio_mes_atual.month - 2
	ano_base = inicio_mes_atual.year
	while mes_base <= 0:
		mes_base += 12
		ano_base -= 1
	inicio_janela_3_meses = inicio_mes_atual.replace(year=ano_base, month=mes_base)

	medias_3_meses = {}
	if categorias_consumo:
		categoria_ids = [categoria.id for categoria in categorias_consumo]
		medias_3_meses_qs = (
			Movimentacao.objects.annotate(data_referencia=Coalesce('data_pagamento', 'data_vencimento'))
			.filter(
				plano_conta_id__in=categoria_ids,
				tipo='Despesa',
				status__in=[Movimentacao.Status.EFETIVADO, Movimentacao.Status.VALIDADO],
				data_referencia__gte=inicio_janela_3_meses,
				data_referencia__lte=hoje,
			)
			.values('plano_conta_id')
			.annotate(total=Coalesce(Sum('valor'), Decimal('0.00')))
		)
		medias_3_meses = {
			item['plano_conta_id']: (item['total'] / Decimal('3.00'))
			for item in medias_3_meses_qs
		}

	for categoria in categorias_consumo:
		categoria.teto_categoria = teto_por_plano.get(categoria.id)
		categoria.tem_teto_categoria = categoria.id in teto_por_plano
		categoria.margem_categoria = (
			categoria.teto_categoria - categoria.total_gasto
			if categoria.tem_teto_categoria
			else None
		)
		categoria.media_gastos_3_meses = medias_3_meses.get(categoria.id, Decimal('0.00'))

	data_alerta_pendente = hoje + timedelta(days=3)
	dias_restantes = max((ciclo_ativo.data_fim - hoje).days, 0)
	visao_tabela = request.GET.get('visao', 'pendentes')
	if visao_tabela not in {'categorias', 'movimentacoes', 'pendentes'}:
		visao_tabela = 'pendentes'

	movimentacoes_ciclo = Movimentacao.objects.filter(ciclo_id=ciclo_ativo.id).select_related(
		'plano_conta',
		'conta_bancaria',
	).order_by('-data_vencimento', '-created_at')

	totais_ciclo = movimentacoes_ciclo.aggregate(
		total_entradas=Sum('valor', filter=Q(tipo='Receita')),
		total_despesas=Sum('valor', filter=Q(tipo='Despesa')),
		total_investimentos=Sum('valor', filter=Q(tipo='Investimento')),
		total_transferencias=Sum('valor', filter=Q(tipo__in=['Transferencia', 'TransfEntrada'])),
		total_transferencias_saida=Sum('valor', filter=Q(tipo='TransfSaida')),
	)
	total_entradas = totais_ciclo['total_entradas'] or 0
	total_despesas = totais_ciclo['total_despesas'] or 0
	total_investimentos = totais_ciclo['total_investimentos'] or 0
	total_transferencias = totais_ciclo['total_transferencias'] or 0
	total_transferencias_saida = totais_ciclo['total_transferencias_saida'] or 0

	movimentacoes_realizadas = movimentacoes_ciclo.annotate(
		data_referencia=Coalesce('data_pagamento', 'data_vencimento')
	).filter(
		Q(status__in=[Movimentacao.Status.EFETIVADO, Movimentacao.Status.VALIDADO])
		| Q(data_pagamento__isnull=False, data_pagamento__lte=hoje),
		data_referencia__lte=hoje,
	)
	movimentacoes_pendentes = movimentacoes_ciclo.filter(status=Movimentacao.Status.PENDENTE)
	movimentacoes_tabela = (
		movimentacoes_pendentes if visao_tabela == 'pendentes' else movimentacoes_ciclo
	)
	totais_realizados = movimentacoes_realizadas.aggregate(
		total_entradas=Sum('valor', filter=Q(tipo='Receita')),
		total_despesas=Sum('valor', filter=Q(tipo='Despesa')),
		total_investimentos=Sum('valor', filter=Q(tipo='Investimento')),
		total_transferencias_saida=Sum('valor', filter=Q(tipo='TransfSaida')),
		total_transferencias=Sum('valor', filter=Q(tipo__in=['Transferencia', 'TransfEntrada', 'TransfSaida'])),
	)
	total_entradas_realizadas = totais_realizados['total_entradas'] or 0
	total_despesas_realizadas = totais_realizados['total_despesas'] or 0
	total_investimentos_realizados = totais_realizados['total_investimentos'] or 0
	total_transferencias_saida_realizadas = totais_realizados['total_transferencias_saida'] or 0
	total_transferencias_realizadas = totais_realizados['total_transferencias'] or 0

	resumo_contas_ciclo = []
	resumos_contas_qs = (
		movimentacoes_ciclo.exclude(conta_bancaria__isnull=True)
			.values('conta_bancaria_id', 'conta_bancaria__nome')
			.annotate(
				total_entradas_previstas=Coalesce(
					Sum('valor', filter=Q(tipo='Receita')),
					Decimal('0.00'),
				),
				total_saidas_previstas=Coalesce(
					Sum('valor', filter=Q(tipo__in=['Despesa', 'Investimento', 'TransfSaida'])),
					Decimal('0.00'),
				),
				total_entradas_realizadas=Coalesce(
					Sum(
						'valor',
						filter=Q(tipo='Receita') & (
							Q(status__in=[Movimentacao.Status.EFETIVADO, Movimentacao.Status.VALIDADO])
							| Q(data_pagamento__isnull=False, data_pagamento__lte=hoje)
						),
					),
					Decimal('0.00'),
				),
				total_saidas_realizadas=Coalesce(
					Sum(
						'valor',
						filter=Q(tipo__in=['Despesa', 'Investimento', 'TransfSaida']) & (
							Q(status__in=[Movimentacao.Status.EFETIVADO, Movimentacao.Status.VALIDADO])
							| Q(data_pagamento__isnull=False, data_pagamento__lte=hoje)
						),
					),
					Decimal('0.00'),
				),
			)
			.order_by('conta_bancaria__nome')
	)
	for resumo in resumos_contas_qs:
		total_entradas_previstas = resumo['total_entradas_previstas'] or Decimal('0.00')
		total_saidas_previstas = resumo['total_saidas_previstas'] or Decimal('0.00')
		total_entradas_realizadas = resumo['total_entradas_realizadas'] or Decimal('0.00')
		total_saidas_realizadas = resumo['total_saidas_realizadas'] or Decimal('0.00')
		resumo_contas_ciclo.append(
			{
				'conta_nome': resumo['conta_bancaria__nome'],
				'total_entradas': total_entradas_previstas,
				'saldo_previsto': total_entradas_previstas - total_saidas_previstas,
				'saldo_atual': total_entradas_realizadas - total_saidas_realizadas,
			}
		)

	saldo_atual = sum((item['saldo_atual'] for item in resumo_contas_ciclo), Decimal('0.00'))
	saldo_final_previsto = (
		total_entradas
		- total_despesas
		- total_investimentos
		- total_transferencias_saida
	)

	pendentes_count = movimentacoes_ciclo.filter(status=Movimentacao.Status.PENDENTE).count()
	encerramento_bloqueado = abs(saldo_final_previsto) > Decimal('0.005')
	encerramento_info = request.GET.get('encerramento_info')
	encerramento_erro = request.GET.get('encerramento_erro')

	contas = ContaBancaria.objects.all().order_by('nome')
	plano_contas = PlanoConta.objects.all().order_by('nome')

	total_categorias_macro = macro_orcamento_mes.count()
	teto_total_mes = macro_orcamento_mes.aggregate(total=Sum('valor_teto'))['total'] or Decimal('0.00')
	tem_teto_definido_mes = total_categorias_macro > 0
	margem_ciclo = teto_total_mes - Decimal(total_despesas_realizadas or 0)

	return render(
		request,
		'orcamento/cockpit_ciclo.html',
		{
			'ciclo_ativo': ciclo_ativo,
			'categorias_consumo': categorias_consumo,
			'movimentacoes_ciclo': movimentacoes_ciclo,
			'movimentacoes_tabela': movimentacoes_tabela,
			'visao_tabela': visao_tabela,
			'dias_restantes': dias_restantes,
			'total_entradas': total_entradas,
			'total_despesas': total_despesas,
			'total_investimentos': total_investimentos,
			'total_transferencias': total_transferencias,
			'total_transferencias_saida': total_transferencias_saida,
			'saldo_atual': saldo_atual,
			'saldo_final_previsto': saldo_final_previsto,
			'total_transferencias_realizadas': total_transferencias_realizadas,
			'pendentes_count': pendentes_count,
			'encerramento_bloqueado': encerramento_bloqueado,
			'encerramento_info': encerramento_info,
			'encerramento_erro': encerramento_erro,
			'total_categorias_macro': total_categorias_macro,
			'tem_teto_definido_mes': tem_teto_definido_mes,
			'teto_total_mes': teto_total_mes,
			'margem_ciclo': margem_ciclo,
			'resumo_contas_ciclo': resumo_contas_ciclo,
			'ano_ciclo': ano_ciclo,
			'mes_ciclo': mes_ciclo,
			'contas': contas,
			'plano_contas': plano_contas,
			'hoje': hoje,
			'data_alerta_pendente': data_alerta_pendente,
			'form_action': reverse('transacoes:nova_transacao'),
			'cancel_url': reverse('orcamento:cockpit_ciclo'),
			'titulo_form_transacao': 'Nova Movimentacao no Ciclo',
			'subtitulo_form_transacao': 'Use o formulario padrao para adicionar um novo lancamento vinculado a este ciclo.',
			'ciclo_id_form': ciclo_ativo.id,
			'next_url_form': reverse('orcamento:cockpit_ciclo'),
			'status_default_form': Movimentacao.Status.PENDENTE,
			'tipo_default_form': 'Despesa',
		},
	)


def abrir_ciclo(request):
	if request.method != 'POST':
		return redirect('orcamento:cockpit_ciclo')

	data_inicio = request.POST.get('data_inicio')
	data_fim = request.POST.get('data_fim')

	if not data_inicio or not data_fim:
		return redirect('orcamento:cockpit_ciclo')

	data_inicio_obj = parse_date(data_inicio)
	data_fim_obj = parse_date(data_fim)
	if not data_inicio_obj or not data_fim_obj:
		return redirect('orcamento:cockpit_ciclo')

	ciclo = Ciclo.objects.create(
		data_inicio=data_inicio_obj,
		data_fim=data_fim_obj,
		status=Ciclo.Status.ABERTO,
	)

	injetar_movimentacoes_no_ciclo(ciclo)
	return redirect('orcamento:cockpit_ciclo')


def confirmar_movimentacao(request, movimentacao_id):
	if request.method != 'POST':
		return redirect('orcamento:cockpit_ciclo')

	movimentacao = Movimentacao.objects.filter(id=movimentacao_id).first()
	if not movimentacao:
		return redirect('orcamento:cockpit_ciclo')

	if movimentacao.status == Movimentacao.Status.PENDENTE:
		movimentacao.status = Movimentacao.Status.EFETIVADO
		if not movimentacao.data_pagamento:
			movimentacao.data_pagamento = timezone.localdate()
		movimentacao.save(update_fields=['status', 'data_pagamento', 'updated_at'])

	visao = request.POST.get('visao') or request.GET.get('visao')
	query = '?visao=movimentacoes' if visao == 'movimentacoes' else ''
	return redirect(f"{reverse('orcamento:cockpit_ciclo')}{query}")


def remover_movimentacao_do_ciclo(request, movimentacao_id):
	if request.method != 'POST':
		return redirect('orcamento:cockpit_ciclo')

	ciclo_ativo = Ciclo.objects.filter(status=Ciclo.Status.ABERTO).first()
	if not ciclo_ativo:
		return redirect('orcamento:cockpit_ciclo')

	movimentacao = Movimentacao.objects.filter(id=movimentacao_id, ciclo_id=ciclo_ativo.id).first()
	if not movimentacao:
		return redirect('orcamento:cockpit_ciclo')

	movimentacao.ciclo = None
	movimentacao.save(update_fields=['ciclo', 'updated_at'])

	visao = request.POST.get('visao') or request.GET.get('visao')
	query = '?visao=movimentacoes' if visao == 'movimentacoes' else '?visao=pendentes' if visao == 'pendentes' else ''
	return redirect(f"{reverse('orcamento:cockpit_ciclo')}{query}")


def encerrar_ciclo(request):
	if request.method != 'POST':
		return redirect('orcamento:cockpit_ciclo')

	ciclo_ativo = Ciclo.objects.filter(status=Ciclo.Status.ABERTO).first()
	if not ciclo_ativo:
		return redirect('orcamento:cockpit_ciclo')

	hoje = timezone.localdate()
	confirmar_pendentes = request.POST.get('confirmar_pendentes') == '1'
	movimentacoes_ciclo = Movimentacao.objects.filter(ciclo_id=ciclo_ativo.id)
	pendentes_qs = movimentacoes_ciclo.filter(status=Movimentacao.Status.PENDENTE)

	if pendentes_qs.exists() and not confirmar_pendentes:
		return redirect(f"{reverse('orcamento:cockpit_ciclo')}?encerramento_info=pendentes")

	if confirmar_pendentes and pendentes_qs.exists():
		pendentes_qs.filter(data_pagamento__isnull=True).update(data_pagamento=hoje)
		pendentes_qs.update(status=Movimentacao.Status.EFETIVADO)

	totais_ciclo = movimentacoes_ciclo.aggregate(
		total_entradas=Sum('valor', filter=Q(tipo='Receita')),
		total_despesas=Sum('valor', filter=Q(tipo='Despesa')),
		total_investimentos=Sum('valor', filter=Q(tipo='Investimento')),
		total_transferencias_saida=Sum('valor', filter=Q(tipo='TransfSaida')),
	)

	saldo_final_previsto = (
		(totais_ciclo['total_entradas'] or 0)
		- (totais_ciclo['total_despesas'] or 0)
		- (totais_ciclo['total_investimentos'] or 0)
		- (totais_ciclo['total_transferencias_saida'] or 0)
	)
	if abs(saldo_final_previsto) > Decimal('0.005'):
		return redirect(f"{reverse('orcamento:cockpit_ciclo')}?encerramento_erro=saldo")

	movimentacoes_realizadas = movimentacoes_ciclo.filter(
		Q(status__in=[Movimentacao.Status.EFETIVADO, Movimentacao.Status.VALIDADO])
		| Q(data_pagamento__isnull=False, data_pagamento__lte=hoje)
	)
	totais_realizados = movimentacoes_realizadas.aggregate(
		total_entradas=Sum('valor', filter=Q(tipo='Receita')),
		total_despesas=Sum('valor', filter=Q(tipo='Despesa')),
		total_investimentos=Sum('valor', filter=Q(tipo='Investimento')),
		total_transferencias_saida=Sum('valor', filter=Q(tipo='TransfSaida')),
	)
	saldo_final_realizado = (
		(totais_realizados['total_entradas'] or 0)
		- (totais_realizados['total_despesas'] or 0)
		- (totais_realizados['total_investimentos'] or 0)
		- (totais_realizados['total_transferencias_saida'] or 0)
	)

	ciclo_ativo.status = Ciclo.Status.FECHADO
	ciclo_ativo.saldo_final_realizado = saldo_final_realizado
	ciclo_ativo.save(update_fields=['status', 'saldo_final_realizado', 'updated_at'])

	return redirect('orcamento:cockpit_ciclo')

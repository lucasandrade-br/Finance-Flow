from datetime import datetime
from decimal import Decimal, InvalidOperation
import re

from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_http_methods
import json

from apps.contas.models import ContaBancaria, PlanoConta, Tag
from apps.transacoes.models import LancamentoFuturo, Movimentacao, MovimentacaoExcluida, TipoTransacao, TransacaoRecorrente


def _add_months(data_base, meses):
	ano = data_base.year + ((data_base.month - 1 + meses) // 12)
	mes = ((data_base.month - 1 + meses) % 12) + 1
	# 28 evita problemas de virada de mês (29/30/31)
	dia = min(data_base.day, 28)
	return data_base.replace(year=ano, month=mes, day=dia)


def _to_decimal_or_zero(raw):
	try:
		return Decimal(str(raw or '0'))
	except (InvalidOperation, TypeError, ValueError):
		return Decimal('0')


def _parse_date_range(raw):
	if not raw:
		return (None, None)
	partes = re.findall(r'\d{4}-\d{2}-\d{2}', raw)
	if not partes:
		return (None, None)
	inicio = parse_date(partes[0])
	fim = parse_date(partes[-1]) if len(partes) > 1 else inicio
	if inicio and fim and inicio > fim:
		inicio, fim = fim, inicio
	return (inicio, fim)


def livro_razao(request):
	data_range = (request.GET.get('data_range') or '').strip()
	tipo = (request.GET.get('tipo') or '').strip()
	plano_conta_id = (request.GET.get('plano_conta_id') or '').strip()
	status = (request.GET.get('status') or '').strip()
	tag_id = (request.GET.get('tag_id') or '').strip()

	transacoes = Movimentacao.objects.select_related(
		'plano_conta',
		'conta_bancaria',
	).prefetch_related('tags').annotate(
		data_referencia=Coalesce('data_pagamento', 'data_vencimento'),
	)

	if data_range:
		data_inicio, data_fim = _parse_date_range(data_range)
		if data_inicio and data_fim:
			transacoes = transacoes.filter(data_referencia__range=(data_inicio, data_fim))
	if tipo:
		transacoes = transacoes.filter(tipo=tipo)
	if plano_conta_id:
		transacoes = transacoes.filter(plano_conta_id=plano_conta_id)
	if status:
		transacoes = transacoes.filter(status=status)
	if tag_id:
		transacoes = transacoes.filter(tags__id=tag_id)

	transacoes = transacoes.distinct().order_by('-data_referencia', '-created_at')

	movimentacoes_excluidas = MovimentacaoExcluida.objects.select_related(
		'plano_conta',
		'conta_bancaria',
	).order_by('-excluida_em', '-created_at')[:100]

	context = {
		'transacoes': transacoes,
		'movimentacoes_excluidas': movimentacoes_excluidas,
		'tipos_transacao': TipoTransacao.choices,
		'status_choices': Movimentacao.Status.choices,
		'plano_contas': PlanoConta.objects.order_by('codigo', 'nome'),
		'tags': Tag.objects.order_by('nome'),
		'filtros': {
			'data_range': data_range,
			'tipo': tipo,
			'plano_conta_id': plano_conta_id,
			'status': status,
			'tag_id': tag_id,
		},
	}
	return render(request, 'transacoes/padrao/livro_razao.html', context)


@require_http_methods(["POST"])
def excluir_movimentacao(request, movimentacao_id):
	movimentacao = get_object_or_404(Movimentacao, pk=movimentacao_id)
	next_url = request.POST.get('next') or request.GET.get('next')
	if next_url and not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
		next_url = None

	tags_snapshot = list(movimentacao.tags.values('id', 'nome'))

	with transaction.atomic():
		MovimentacaoExcluida.objects.create(
			original_movimentacao_id=movimentacao.id,
			tipo=movimentacao.tipo,
			valor=movimentacao.valor,
			formato_pagamento=movimentacao.formato_pagamento,
			frequencia=movimentacao.frequencia,
			descricao=movimentacao.descricao,
			comprovante_path=movimentacao.comprovante.name if movimentacao.comprovante else '',
			data_pagamento=movimentacao.data_pagamento,
			data_vencimento=movimentacao.data_vencimento,
			parcela_atual=movimentacao.parcela_atual,
			total_parcelas=movimentacao.total_parcelas,
			plano_conta=movimentacao.plano_conta,
			conta_bancaria=movimentacao.conta_bancaria,
			conta_destino=movimentacao.conta_destino,
			ciclo=movimentacao.ciclo,
			cofre=movimentacao.cofre,
			status=movimentacao.status,
			tags_snapshot=tags_snapshot,
		)
		movimentacao.delete()

	return redirect(next_url or 'transacoes:livro_razao')


@require_http_methods(["POST"])
def restaurar_movimentacao_excluida(request, item_id):
	item = get_object_or_404(MovimentacaoExcluida, pk=item_id)
	next_url = request.POST.get('next') or request.GET.get('next')
	if next_url and not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
		next_url = None

	with transaction.atomic():
		movimentacao = Movimentacao.objects.create(
			tipo=item.tipo,
			valor=item.valor,
			formato_pagamento=item.formato_pagamento,
			frequencia=item.frequencia,
			descricao=item.descricao,
			data_pagamento=item.data_pagamento,
			data_vencimento=item.data_vencimento or timezone.localdate(),
			parcela_atual=item.parcela_atual,
			total_parcelas=item.total_parcelas,
			plano_conta=item.plano_conta,
			conta_bancaria=item.conta_bancaria,
			conta_destino=item.conta_destino,
			ciclo=item.ciclo,
			cofre=item.cofre,
			status=item.status,
		)
		if item.comprovante_path:
			movimentacao.comprovante = item.comprovante_path
			movimentacao.save(update_fields=['comprovante', 'updated_at'])

		tag_ids = [registro.get('id') for registro in (item.tags_snapshot or []) if registro.get('id')]
		if tag_ids:
			movimentacao.tags.set(Tag.objects.filter(id__in=tag_ids))

		item.delete()

	return redirect(next_url or 'transacoes:livro_razao')


def nova_transacao(request):
	contas = ContaBancaria.objects.all().order_by('nome')
	plano_contas = PlanoConta.objects.all().order_by('codigo', 'nome')
	tags = Tag.objects.all().order_by('nome')
	ciclo_id_raw = request.POST.get('ciclo_id') or request.GET.get('ciclo_id')
	next_url = request.POST.get('next') or request.GET.get('next')

	if next_url and not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
		next_url = None

	ciclo_id = None
	if ciclo_id_raw:
		try:
			ciclo_id = int(ciclo_id_raw)
		except (TypeError, ValueError):
			ciclo_id = None

	if request.method == 'POST':
		tipo = request.POST.get('tipo')
		valor = request.POST.get('valor')
		descricao = request.POST.get('descricao', '').strip()
		data_pagamento = request.POST.get('data_pagamento')
		conta_bancaria_id = request.POST.get('conta_bancaria_id')
		conta_destino_id = request.POST.get('conta_destino_id')
		plano_conta_id = request.POST.get('plano_conta_id') or request.POST.get('plano_contas_id')
		status = request.POST.get('status')
		formato_pagamento = request.POST.get('formato_pagamento', 'PIX')
		frequencia = request.POST.get('frequencia', 'Variavel')
		comprovante = request.FILES.get('comprovante')
		tag_ids = request.POST.getlist('tags')

		if tipo == TipoTransacao.TRANSFERENCIA:
			if not conta_destino_id or conta_destino_id == conta_bancaria_id:
				context = {
					'contas': contas,
					'plano_contas': plano_contas,
					'tags': tags,
					'hoje': timezone.localdate(),
					'ciclo_id_form': ciclo_id,
					'next_url_form': next_url,
					'cancel_url': next_url,
					'status_default_form': Movimentacao.Status.PENDENTE if ciclo_id else Movimentacao.Status.EFETIVADO,
					'tipo_default_form': tipo,
					'erro_formulario': 'Selecione uma conta destino diferente da conta de origem para transferências.',
				}
				return render(request, 'transacoes/padrao/form_lancamento.html', context)

			with transaction.atomic():
				mov_saida = Movimentacao.objects.create(
					tipo=TipoTransacao.TRANSFERENCIA_SAIDA,
					valor=valor,
					descricao=descricao,
					data_pagamento=data_pagamento,
					data_vencimento=data_pagamento or timezone.now().date(),
					conta_bancaria_id=conta_bancaria_id,
					conta_destino_id=conta_destino_id,
					plano_conta_id=plano_conta_id,
					status=status,
					formato_pagamento=formato_pagamento,
					frequencia=frequencia,
					comprovante=comprovante,
					ciclo_id=ciclo_id,
				)
				mov_entrada = Movimentacao.objects.create(
					tipo=TipoTransacao.TRANSFERENCIA_ENTRADA,
					valor=valor,
					descricao=descricao,
					data_pagamento=data_pagamento,
					data_vencimento=data_pagamento or timezone.now().date(),
					conta_bancaria_id=conta_destino_id,
					conta_destino_id=conta_bancaria_id,
					plano_conta_id=plano_conta_id,
					status=status,
					formato_pagamento=formato_pagamento,
					frequencia=frequencia,
					ciclo_id=ciclo_id,
				)
				mov_saida.lancamento_par = mov_entrada
				mov_saida.save(update_fields=['lancamento_par', 'updated_at'])
				mov_entrada.lancamento_par = mov_saida
				mov_entrada.save(update_fields=['lancamento_par', 'updated_at'])

				if tag_ids:
					mov_saida.tags.set(tag_ids)
					mov_entrada.tags.set(tag_ids)

			if next_url:
				return redirect(next_url)

			return redirect('transacoes:livro_razao')

		movimentacao = Movimentacao.objects.create(
			tipo=tipo,
			valor=valor,
			descricao=descricao,
			data_pagamento=data_pagamento,
			data_vencimento=data_pagamento or timezone.now().date(),
			conta_bancaria_id=conta_bancaria_id,
			conta_destino_id=conta_destino_id or None,
			plano_conta_id=plano_conta_id,
			status=status,
			formato_pagamento=formato_pagamento,
			frequencia=frequencia,
			comprovante=comprovante,
			ciclo_id=ciclo_id,
		)

		if tag_ids:
			movimentacao.tags.set(tag_ids)

		if next_url:
			return redirect(next_url)

		return redirect('transacoes:livro_razao')

	context = {
		'contas': contas,
		'plano_contas': plano_contas,
		'tags': tags,
		'hoje': timezone.localdate(),
		'ciclo_id_form': ciclo_id,
		'next_url_form': next_url,
		'cancel_url': next_url,
		'status_default_form': Movimentacao.Status.PENDENTE if ciclo_id else Movimentacao.Status.EFETIVADO,
		'tipo_default_form': TipoTransacao.DESPESA,
	}
	return render(request, 'transacoes/padrao/form_lancamento.html', context)


def partida_dupla(request):
	contas = ContaBancaria.objects.all().order_by('nome')
	plano_contas = PlanoConta.objects.all().order_by('codigo', 'nome')
	tags = Tag.objects.all().order_by('nome')
	hoje = timezone.localdate()

	if request.method == 'POST':
		try:
			data = json.loads(request.body)
			lancamentos = data.get('lancamentos', [])
			if not lancamentos or len(lancamentos) < 2:
				return JsonResponse({'error': 'Operação inválida.'}, status=400)
			with transaction.atomic():
				for l in lancamentos:
					mov = Movimentacao.objects.create(
						tipo=l.get('tipo'),
						valor=l.get('valor'),
						descricao=(l.get('descricao') or '').strip(),
						data_pagamento=l.get('data_pagamento'),
						data_vencimento=l.get('data_pagamento') or hoje,
						plano_conta_id=l.get('plano_conta_id'),
						conta_bancaria_id=l.get('conta_bancaria_id'),
						status=l.get('status', Movimentacao.Status.PENDENTE),
						formato_pagamento=l.get('formato_pagamento', 'PIX'),
					)
					# Salva tags se vierem
					tag_ids = l.get('tag_ids') or l.get('tags')
					if tag_ids:
						mov.tags.set(tag_ids)
			return JsonResponse({'ok': True})
		except Exception as e:
			return JsonResponse({'error': str(e)}, status=400)

	context = {
		'contas': contas,
		'plano_contas': plano_contas,
		'tags': tags,
		'hoje': hoje,
	}
	return render(request, 'transacoes/padrao/partida_dupla.html', context)


def lista_recorrentes(request):
	recorrentes = TransacaoRecorrente.objects.select_related(
		'plano_conta',
		'conta_bancaria',
	).order_by('descricao')
	return render(request, 'transacoes/recorrentes/lista_recorrentes.html', {'recorrentes': recorrentes})


@require_http_methods(["POST"])
def excluir_recorrente(request, recorrente_id):
	recorrente = get_object_or_404(TransacaoRecorrente, pk=recorrente_id)
	next_url = request.POST.get('next') or request.GET.get('next')
	if next_url and not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
		next_url = None

	recorrente.delete()
	return redirect(next_url or 'transacoes:lista_recorrentes')


def nova_recorrente(request):
	contas = ContaBancaria.objects.all().order_by('nome')
	plano_contas = PlanoConta.objects.all().order_by('codigo', 'nome')
	tags = Tag.objects.all().order_by('nome')

	if request.method == 'POST':
		tag_ids = request.POST.getlist('tags')
		recorrente = TransacaoRecorrente.objects.create(
			descricao=request.POST.get('descricao', '').strip(),
			tipo=request.POST.get('tipo', 'Despesa'),
			plano_conta_id=request.POST.get('plano_conta_id'),
			conta_bancaria_id=request.POST.get('conta_bancaria_id'),
			formato_pagamento=request.POST.get('formato_pagamento', 'PIX'),
			dia_vencimento=request.POST.get('dia_vencimento') or 1,
			valor_base=request.POST.get('valor_base') or 0,
			tipo_valor=request.POST.get('tipo_valor', TransacaoRecorrente.TipoValor.EXATO),
			frequencia='Fixa',
			status_ativa=bool(request.POST.get('status_ativa')),
		)
		if tag_ids:
			recorrente.tags.set(tag_ids)
		return redirect('transacoes:lista_recorrentes')

	context = {
		'contas': contas,
		'plano_contas': plano_contas,
		'tags': tags,
	}
	return render(request, 'transacoes/recorrentes/nova_recorrente.html', context)


def lista_futuros(request):
	futuros = LancamentoFuturo.objects.select_related(
		'plano_conta',
		'conta_bancaria',
	).order_by('data_vencimento', 'descricao')
	return render(request, 'transacoes/futuros/lista_futuros.html', {'futuros': futuros})


@require_http_methods(["POST"])
def excluir_futuro(request, futuro_id):
	futuro = get_object_or_404(LancamentoFuturo, pk=futuro_id)
	next_url = request.POST.get('next') or request.GET.get('next')
	if next_url and not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
		next_url = None

	futuro.delete()
	return redirect(next_url or 'transacoes:lista_futuros')


def novo_futuro(request):
	contas = ContaBancaria.objects.all().order_by('nome')
	plano_contas = PlanoConta.objects.all().order_by('codigo', 'nome')
	tags = Tag.objects.all().order_by('nome')

	if request.method == 'POST':
		tag_ids = request.POST.getlist('tags')
		descricao = request.POST.get('descricao', '').strip()
		tipo = request.POST.get('tipo', 'Despesa')
		plano_conta_id = request.POST.get('plano_conta_id')
		conta_bancaria_id = request.POST.get('conta_bancaria_id')
		formato_pagamento = request.POST.get('formato_pagamento', 'PIX')
		frequencia = request.POST.get('frequencia', 'Variavel')
		data_vencimento_str = request.POST.get('data_vencimento')
		valor_total_str = request.POST.get('valor') or '0'
		status = request.POST.get('status', LancamentoFuturo.Status.PENDENTE)
		total_parcelas = int(request.POST.get('total_parcelas') or 1)
		total_parcelas = max(total_parcelas, 1)
		comprovante_upload = request.FILES.get('comprovante')
		modo_lancamento = request.POST.get('modo_lancamento', 'unico')
		parcelas_valores_json = request.POST.get('parcelas_valores_json', '[]')
		parcelas_datas_json = request.POST.get('parcelas_datas_json', '[]')

		data_base = datetime.strptime(data_vencimento_str, '%Y-%m-%d').date()

		try:
			valor_total = Decimal(valor_total_str)
		except (InvalidOperation, TypeError):
			valor_total = Decimal('0')

		parcelas_custom = []
		if modo_lancamento == 'parcelado':
			try:
				valores_custom = json.loads(parcelas_valores_json)
				datas_custom = json.loads(parcelas_datas_json)
			except json.JSONDecodeError:
				valores_custom = []
				datas_custom = []

			if len(valores_custom) == total_parcelas and len(datas_custom) == total_parcelas:
				soma_parcelas = Decimal('0')
				for indice in range(total_parcelas):
					try:
						valor_parcela = Decimal(str(valores_custom[indice]))
						data_parcela = datetime.strptime(datas_custom[indice], '%Y-%m-%d').date()
					except (InvalidOperation, TypeError, ValueError):
						valor_parcela = Decimal('0')
						data_parcela = _add_months(data_base, indice)
					parcelas_custom.append((valor_parcela, data_parcela))
					soma_parcelas += valor_parcela

				if soma_parcelas.quantize(Decimal('0.01')) != valor_total.quantize(Decimal('0.01')):
					context = {
						'contas': contas,
						'plano_contas': plano_contas,
						'tags': tags,
						'hoje': timezone.localdate(),
						'erro_parcelas': 'A soma das parcelas deve ser igual ao valor total da compra.',
					}
					return render(request, 'transacoes/futuros/novo_futuro.html', context)

		primeiro = None
		for parcela in range(1, total_parcelas + 1):
			if parcelas_custom:
				valor_parcela, vencimento_parcela = parcelas_custom[parcela - 1]
			else:
				vencimento_parcela = _add_months(data_base, parcela - 1)
				valor_parcela = valor_total
			kwargs = {
				'descricao': descricao,
				'tipo': tipo,
				'plano_conta_id': plano_conta_id,
				'conta_bancaria_id': conta_bancaria_id,
				'formato_pagamento': formato_pagamento,
				'frequencia': frequencia,
				'data_vencimento': vencimento_parcela,
				'valor': valor_parcela,
				'status': status,
				'parcela_atual': parcela if total_parcelas > 1 else None,
				'total_parcelas': total_parcelas if total_parcelas > 1 else None,
			}

			if parcela == 1:
				if comprovante_upload:
					kwargs['comprovante'] = comprovante_upload
				futuro = LancamentoFuturo.objects.create(**kwargs)
				primeiro = futuro
			else:
				kwargs['lancamento_pai'] = primeiro
				if primeiro and primeiro.comprovante:
					kwargs['comprovante'] = primeiro.comprovante.name
				futuro = LancamentoFuturo.objects.create(**kwargs)

			if tag_ids:
				futuro.tags.set(tag_ids)
		return redirect('transacoes:lista_futuros')

	context = {
		'contas': contas,
		'plano_contas': plano_contas,
		'tags': tags,
		'hoje': timezone.localdate(),
	}
	return render(request, 'transacoes/futuros/novo_futuro.html', context)


@xframe_options_sameorigin
def painel_edicao(request, origem, registro_id):
	config = {
		'movimentacao': {
			'model': Movimentacao,
			'titulo': 'Editar Movimentacao',
			'lista_url': 'transacoes:livro_razao',
		},
		'futuro': {
			'model': LancamentoFuturo,
			'titulo': 'Editar Lancamento Futuro',
			'lista_url': 'transacoes:lista_futuros',
		},
		'recorrente': {
			'model': TransacaoRecorrente,
			'titulo': 'Editar Conta Fixa',
			'lista_url': 'transacoes:lista_recorrentes',
		},
	}

	if origem not in config:
		return redirect('core:home')

	next_url = request.POST.get('next') or request.GET.get('next')
	embed_mode = (request.GET.get('embed') == '1')
	if next_url and not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
		next_url = None

	default_redirect = config[origem]['lista_url']
	redirect_destino = next_url or default_redirect

	def _resposta_pos_salvar():
		if embed_mode:
			return render(
				request,
				'transacoes/padrao/painel_edicao_salvo_embed.html',
				{'redirect_url': redirect_destino},
			)
		return redirect(redirect_destino)

	model = config[origem]['model']
	registro = get_object_or_404(model, pk=registro_id)

	contas = ContaBancaria.objects.all().order_by('nome')
	plano_contas = PlanoConta.objects.all().order_by('codigo', 'nome')
	tags = Tag.objects.all().order_by('nome')
	erro_formulario = None

	if request.method == 'POST':
		if origem == 'movimentacao':
			tipo = request.POST.get('tipo')
			conta_origem_id = request.POST.get('conta_bancaria_id')
			conta_destino_id = request.POST.get('conta_destino_id') or None
			if tipo == TipoTransacao.TRANSFERENCIA and (not conta_destino_id or conta_destino_id == conta_origem_id):
				erro_formulario = 'Selecione uma conta destino diferente da origem para transferencia.'
			else:
				registro.tipo = tipo
				registro.valor = _to_decimal_or_zero(request.POST.get('valor'))
				registro.descricao = (request.POST.get('descricao') or '').strip()
				registro.formato_pagamento = request.POST.get('formato_pagamento') or registro.formato_pagamento
				registro.frequencia = request.POST.get('frequencia') or registro.frequencia
				registro.status = request.POST.get('status') or registro.status
				registro.data_pagamento = parse_date(request.POST.get('data_pagamento')) if request.POST.get('data_pagamento') else None
				registro.data_vencimento = parse_date(request.POST.get('data_vencimento')) or registro.data_vencimento
				registro.conta_bancaria_id = conta_origem_id or registro.conta_bancaria_id
				registro.conta_destino_id = conta_destino_id
				registro.plano_conta_id = request.POST.get('plano_conta_id') or registro.plano_conta_id
				if request.FILES.get('comprovante'):
					registro.comprovante = request.FILES.get('comprovante')
				registro.save()
				registro.tags.set(request.POST.getlist('tags'))
				return _resposta_pos_salvar()

		elif origem == 'futuro':
			registro.tipo = request.POST.get('tipo') or registro.tipo
			registro.valor = _to_decimal_or_zero(request.POST.get('valor'))
			registro.descricao = (request.POST.get('descricao') or '').strip()
			registro.formato_pagamento = request.POST.get('formato_pagamento') or registro.formato_pagamento
			registro.frequencia = request.POST.get('frequencia') or registro.frequencia
			registro.status = request.POST.get('status') or registro.status
			registro.data_vencimento = parse_date(request.POST.get('data_vencimento')) or registro.data_vencimento
			registro.conta_bancaria_id = request.POST.get('conta_bancaria_id') or registro.conta_bancaria_id
			registro.conta_destino_id = request.POST.get('conta_destino_id') or None
			registro.plano_conta_id = request.POST.get('plano_conta_id') or registro.plano_conta_id
			if request.FILES.get('comprovante'):
				registro.comprovante = request.FILES.get('comprovante')
			registro.save()
			registro.tags.set(request.POST.getlist('tags'))
			return _resposta_pos_salvar()

		elif origem == 'recorrente':
			tipo = request.POST.get('tipo') or registro.tipo
			conta_origem_id = request.POST.get('conta_bancaria_id')
			conta_destino_id = request.POST.get('conta_destino_id') or None
			if tipo == TipoTransacao.TRANSFERENCIA and (not conta_destino_id or conta_destino_id == conta_origem_id):
				erro_formulario = 'Selecione uma conta destino diferente da origem para transferencia.'
			else:
				registro.tipo = tipo
				registro.valor_base = _to_decimal_or_zero(request.POST.get('valor_base'))
				registro.descricao = (request.POST.get('descricao') or '').strip()
				registro.formato_pagamento = request.POST.get('formato_pagamento') or registro.formato_pagamento
				registro.dia_vencimento = int(request.POST.get('dia_vencimento') or registro.dia_vencimento or 1)
				registro.tipo_valor = request.POST.get('tipo_valor') or registro.tipo_valor
				registro.status_ativa = bool(request.POST.get('status_ativa'))
				registro.conta_bancaria_id = conta_origem_id or registro.conta_bancaria_id
				registro.conta_destino_id = conta_destino_id
				registro.plano_conta_id = request.POST.get('plano_conta_id') or registro.plano_conta_id
				registro.save()
				registro.tags.set(request.POST.getlist('tags'))
				return _resposta_pos_salvar()

	context = {
		'origem': origem,
		'registro': registro,
		'contas': contas,
		'plano_contas': plano_contas,
		'tags': tags,
		'titulo': config[origem]['titulo'],
		'lista_url': config[origem]['lista_url'],
		'retorno_url': redirect_destino,
		'next_url_form': next_url,
		'hide_sidebar': embed_mode,
		'erro_formulario': erro_formulario,
		'tipos_transacao': TipoTransacao.choices,
		'formatos_pagamento': Movimentacao._meta.get_field('formato_pagamento').choices,
		'frequencias': Movimentacao._meta.get_field('frequencia').choices,
		'mov_status': Movimentacao.Status.choices,
		'fut_status': LancamentoFuturo.Status.choices,
		'tipo_valor_choices': TransacaoRecorrente.TipoValor.choices,
	}
	return render(request, 'transacoes/padrao/painel_edicao.html', context)

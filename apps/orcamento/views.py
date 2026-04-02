from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.utils import timezone
from decimal import Decimal

from apps.contas.models import ContaBancaria, PlanoConta
from apps.orcamento.models import Ciclo, MacroOrcamento
from apps.orcamento.services import injetar_movimentacoes_no_ciclo
from apps.transacoes.models import Movimentacao


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
	plano_contas = plano_contas_qs.order_by('codigo', 'nome')

	if request.method == 'POST':
		for plano in plano_contas:
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

		query_tipo = f'&tipo={filtro_tipo}' if filtro_tipo != 'Todos' else ''
		return redirect(f"{reverse('orcamento:matriz_planejamento')}?ano={ano_selecionado}{query_tipo}")

	planejamentos = MacroOrcamento.objects.filter(ano=ano_selecionado, plano_conta__in=plano_contas)
	planejado_por_categoria_mes = {
		(item.plano_conta_id, item.mes): item.valor_teto
		for item in planejamentos
	}

	real_ano_passado_qs = (
		Movimentacao.objects.filter(
			data_pagamento__year=ano_anterior,
			status=Movimentacao.Status.EFETIVADO,
			plano_conta__in=plano_contas,
		)
		.values('plano_conta_id', 'data_pagamento__month')
		.annotate(total=Coalesce(Sum('valor'), Decimal('0.00')))
	)
	real_por_categoria_mes = {
		(item['plano_conta_id'], item['data_pagamento__month']): item['total']
		for item in real_ano_passado_qs
	}

	matriz = []
	for plano in plano_contas:
		linha_meses = []
		total_anual = Decimal('0.00')
		for mes, mes_label in MESES_ANO:
			chave_mes = (plano.id, mes)
			valor_planejado = planejado_por_categoria_mes.get(chave_mes)
			valor_real = real_por_categoria_mes.get((plano.id, mes), Decimal('0.00'))
			total_anual += valor_planejado or Decimal('0.00')
			linha_meses.append(
				{
					'mes': mes,
					'mes_label': mes_label,
					'valor_planejado': valor_planejado,
					'tem_valor_planejado': chave_mes in planejado_por_categoria_mes,
					'valor_real_ano_passado': valor_real,
					'valor_real_ano_passado_fmt': formatar_moeda_br(valor_real),
				}
			)

		matriz.append(
			{
				'plano_conta': plano,
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
	for categoria in categorias_consumo:
		categoria.teto_categoria = teto_por_plano.get(categoria.id)
		categoria.tem_teto_categoria = categoria.id in teto_por_plano
		categoria.margem_categoria = (
			categoria.teto_categoria - categoria.total_gasto
			if categoria.tem_teto_categoria
			else None
		)

	hoje = timezone.localdate()
	dias_restantes = max((ciclo_ativo.data_fim - hoje).days, 0)
	visao_tabela = request.GET.get('visao', 'categorias')
	if visao_tabela not in {'categorias', 'movimentacoes'}:
		visao_tabela = 'categorias'

	movimentacoes_ciclo = Movimentacao.objects.filter(ciclo_id=ciclo_ativo.id).select_related(
		'plano_conta',
		'conta_bancaria',
	).order_by('-data_vencimento', '-created_at')

	totais_ciclo = movimentacoes_ciclo.aggregate(
		total_entradas=Sum('valor', filter=Q(tipo='Receita')),
		total_despesas=Sum('valor', filter=Q(tipo='Despesa')),
		total_investimentos=Sum('valor', filter=Q(tipo='Investimento')),
		total_transferencias=Sum('valor', filter=Q(tipo__in=['Transferencia', 'TransfEntrada', 'TransfSaida'])),
	)
	total_entradas = totais_ciclo['total_entradas'] or 0
	total_despesas = totais_ciclo['total_despesas'] or 0
	total_investimentos = totais_ciclo['total_investimentos'] or 0
	total_transferencias = totais_ciclo['total_transferencias'] or 0

	movimentacoes_realizadas = movimentacoes_ciclo.filter(
		status__in=[Movimentacao.Status.EFETIVADO, Movimentacao.Status.VALIDADO]
	)
	totais_realizados = movimentacoes_realizadas.aggregate(
		total_entradas=Sum('valor', filter=Q(tipo='Receita')),
		total_despesas=Sum('valor', filter=Q(tipo='Despesa')),
		total_investimentos=Sum('valor', filter=Q(tipo='Investimento')),
		total_transferencias=Sum('valor', filter=Q(tipo__in=['Transferencia', 'TransfEntrada', 'TransfSaida'])),
	)
	total_entradas_realizadas = totais_realizados['total_entradas'] or 0
	total_despesas_realizadas = totais_realizados['total_despesas'] or 0
	total_investimentos_realizados = totais_realizados['total_investimentos'] or 0
	total_transferencias_realizadas = totais_realizados['total_transferencias'] or 0

	saldo_atual = (
		total_entradas_realizadas
		- total_despesas_realizadas
		- total_investimentos_realizados
	)
	saldo_final_previsto = (
		total_entradas
		- total_despesas
		- total_investimentos
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
			'visao_tabela': visao_tabela,
			'dias_restantes': dias_restantes,
			'total_entradas': total_entradas,
			'total_despesas': total_despesas,
			'total_investimentos': total_investimentos,
			'total_transferencias': total_transferencias,
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
			'ano_ciclo': ano_ciclo,
			'mes_ciclo': mes_ciclo,
			'contas': contas,
			'plano_contas': plano_contas,
			'hoje': hoje,
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
	)
	saldo_final_previsto = (
		(totais_ciclo['total_entradas'] or 0)
		- (totais_ciclo['total_despesas'] or 0)
		- (totais_ciclo['total_investimentos'] or 0)
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
	)
	saldo_final_realizado = (
		(totais_realizados['total_entradas'] or 0)
		- (totais_realizados['total_despesas'] or 0)
		- (totais_realizados['total_investimentos'] or 0)
	)

	ciclo_ativo.status = Ciclo.Status.FECHADO
	ciclo_ativo.saldo_final_realizado = saldo_final_realizado
	ciclo_ativo.save(update_fields=['status', 'saldo_final_realizado', 'updated_at'])

	return redirect('orcamento:cockpit_ciclo')

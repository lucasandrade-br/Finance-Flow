import json
import re
from decimal import Decimal, InvalidOperation

from django.db.models import Case, DecimalField, F, ProtectedError, Q, Sum, Value, When
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.contas.models import ContaBancaria, PlanoConta, Tag
from apps.transacoes.models import Movimentacao, TipoTransacao


STATUS_CONSOLIDADO = [Movimentacao.Status.EFETIVADO, Movimentacao.Status.VALIDADO]


def _to_decimal(value, default=Decimal('0')):
    try:
        return Decimal(str(value or '')).quantize(Decimal('0.01'))
    except (InvalidOperation, TypeError, ValueError):
        return default


def _to_int_or_none(value):
    if value in (None, ''):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _sugerir_codigo_plano(conta_pai_id=None):
    if conta_pai_id:
        pai = PlanoConta.objects.filter(pk=conta_pai_id).only('id', 'codigo').first()
        if not pai:
            return ''
        prefixo = f'{pai.codigo}.'
        irmaos = PlanoConta.objects.filter(conta_pai_id=conta_pai_id).only('codigo')
        sufixos = []
        for irmao in irmaos:
            if not irmao.codigo or not irmao.codigo.startswith(prefixo):
                continue
            ultimo = irmao.codigo.split('.')[-1]
            if ultimo.isdigit():
                sufixos.append(int(ultimo))
        proximo = max(sufixos) + 1 if sufixos else 1
        return f'{pai.codigo}.{proximo}'

    raizes = PlanoConta.objects.filter(conta_pai__isnull=True).only('codigo')
    candidatos = []
    for item in raizes:
        if item.codigo and re.match(r'^\d+$', item.codigo):
            candidatos.append(int(item.codigo))
    proximo = max(candidatos) + 1 if candidatos else 1
    return str(proximo)


def _validar_codigo_hierarquico(codigo, conta_pai_id, plano_atual_id=None):
    if not codigo:
        return 'Código do plano é obrigatório.'
    if not re.match(r'^\d+(\.\d+)*$', codigo):
        return 'Código inválido. Use o padrão 1, 1.1, 1.1.1.'

    existe = PlanoConta.objects.filter(codigo=codigo)
    if plano_atual_id:
        existe = existe.exclude(pk=plano_atual_id)
    if existe.exists():
        return 'Já existe um plano com este código.'

    partes = codigo.split('.')
    if conta_pai_id:
        pai = PlanoConta.objects.filter(pk=conta_pai_id).only('id', 'codigo').first()
        if not pai:
            return 'Conta pai inválida.'
        prefixo = f'{pai.codigo}.'
        if not codigo.startswith(prefixo):
            return f'O código deve iniciar com {prefixo}'
        partes_pai = pai.codigo.split('.')
        if len(partes) != len(partes_pai) + 1:
            return 'O código deve ter exatamente um nível abaixo da conta pai.'
    else:
        if len(partes) != 1:
            return 'Plano sem conta pai deve ter código de primeiro nível, como 1 ou 2.'

    return None


@require_http_methods(["GET"])
def lista_planos_conta(request):
    query = (request.GET.get('q') or '').strip()
    tipo = (request.GET.get('tipo') or '').strip()

    planos = PlanoConta.objects.select_related('conta_pai').order_by('codigo')
    if query:
        planos = planos.filter(Q(nome__icontains=query) | Q(codigo__icontains=query) | Q(conta_pai__nome__icontains=query))
    if tipo:
        planos = planos.filter(tipo_natureza=tipo)

    context = {
        'planos': planos,
        'query': query,
        'tipo': tipo,
        'tipo_choices': PlanoConta.TipoNatureza.choices,
    }
    return render(request, 'contas/planos/lista.html', context)


@require_http_methods(["GET", "POST"])
def novo_plano_conta(request):
    planos_pai = PlanoConta.objects.order_by('codigo', 'nome')
    erro_formulario = None
    codigo_sugerido = _sugerir_codigo_plano()

    if request.method == 'POST':
        codigo = (request.POST.get('codigo') or '').strip()
        nome = (request.POST.get('nome') or '').strip()
        tipo_natureza = request.POST.get('tipo_natureza')
        conta_pai_id = _to_int_or_none(request.POST.get('conta_pai_id'))
        codigo_sugerido = _sugerir_codigo_plano(conta_pai_id)

        erro_codigo = _validar_codigo_hierarquico(codigo, conta_pai_id)
        if erro_codigo:
            erro_formulario = erro_codigo
        elif not nome:
            erro_formulario = 'Nome do plano de conta é obrigatório.'
        else:
            PlanoConta.objects.create(
                codigo=codigo,
                nome=nome,
                tipo_natureza=tipo_natureza,
                conta_pai_id=conta_pai_id,
            )
            return redirect('contas:lista_planos_conta')

    context = {
        'acao': 'novo',
        'plano': None,
        'planos_pai': planos_pai,
        'tipo_choices': PlanoConta.TipoNatureza.choices,
        'erro_formulario': erro_formulario,
        'codigo_sugerido': codigo_sugerido,
    }
    return render(request, 'contas/planos/form.html', context)


@require_http_methods(["GET", "POST"])
def editar_plano_conta(request, plano_id):
    plano = get_object_or_404(PlanoConta, pk=plano_id)
    planos_pai = PlanoConta.objects.exclude(pk=plano.id).order_by('codigo', 'nome')
    erro_formulario = None
    codigo_sugerido = plano.codigo

    if request.method == 'POST':
        codigo = (request.POST.get('codigo') or '').strip()
        nome = (request.POST.get('nome') or '').strip()
        tipo_natureza = request.POST.get('tipo_natureza')
        conta_pai_id = _to_int_or_none(request.POST.get('conta_pai_id'))
        codigo_sugerido = _sugerir_codigo_plano(conta_pai_id) if conta_pai_id else _sugerir_codigo_plano()

        erro_codigo = _validar_codigo_hierarquico(codigo, conta_pai_id, plano_atual_id=plano.id)
        if erro_codigo:
            erro_formulario = erro_codigo
        elif not nome:
            erro_formulario = 'Nome do plano de conta é obrigatório.'
        else:
            codigo_antigo = plano.codigo
            plano.nome = nome
            plano.codigo = codigo
            plano.tipo_natureza = tipo_natureza
            plano.conta_pai_id = conta_pai_id
            plano.save()

            if codigo != codigo_antigo:
                descendentes = PlanoConta.objects.filter(codigo__startswith=f'{codigo_antigo}.').exclude(pk=plano.id)
                for item in descendentes:
                    item.codigo = item.codigo.replace(f'{codigo_antigo}.', f'{codigo}.', 1)
                    item.save(update_fields=['codigo', 'updated_at'])
            return redirect('contas:lista_planos_conta')

    context = {
        'acao': 'editar',
        'plano': plano,
        'planos_pai': planos_pai,
        'tipo_choices': PlanoConta.TipoNatureza.choices,
        'erro_formulario': erro_formulario,
        'codigo_sugerido': codigo_sugerido,
    }
    return render(request, 'contas/planos/form.html', context)


@require_http_methods(["GET"])
def sugerir_codigo_plano(request):
    conta_pai_id = _to_int_or_none(request.GET.get('conta_pai_id'))
    codigo = _sugerir_codigo_plano(conta_pai_id)
    return JsonResponse({'codigo': codigo})


@require_http_methods(["POST"])
def excluir_plano_conta(request, plano_id):
    plano = get_object_or_404(PlanoConta, pk=plano_id)
    try:
        plano.delete()
    except ProtectedError:
        return redirect('contas:lista_planos_conta')
    return redirect('contas:lista_planos_conta')


@require_http_methods(["GET"])
def lista_tags(request):
    query = (request.GET.get('q') or '').strip()
    tags = Tag.objects.select_related('plano_conta').order_by('nome')
    if query:
        tags = tags.filter(Q(nome__icontains=query) | Q(plano_conta__nome__icontains=query))

    context = {
        'tags': tags,
        'query': query,
    }
    return render(request, 'contas/tags/lista.html', context)


@require_http_methods(["GET", "POST"])
def nova_tag(request):
    planos = PlanoConta.objects.order_by('codigo', 'nome')
    erro_formulario = None

    if request.method == 'POST':
        nome = (request.POST.get('nome') or '').strip()
        plano_conta_id = _to_int_or_none(request.POST.get('plano_conta_id'))
        cor_hexadecimal = (request.POST.get('cor_hexadecimal') or '').strip() or None

        if not nome:
            erro_formulario = 'Nome da tag é obrigatório.'
        else:
            Tag.objects.create(
                nome=nome,
                plano_conta_id=plano_conta_id,
                cor_hexadecimal=cor_hexadecimal,
            )
            return redirect('contas:lista_tags')

    context = {
        'acao': 'novo',
        'tag': None,
        'planos': planos,
        'erro_formulario': erro_formulario,
    }
    return render(request, 'contas/tags/form.html', context)


@require_http_methods(["GET", "POST"])
def editar_tag(request, tag_id):
    tag = get_object_or_404(Tag, pk=tag_id)
    planos = PlanoConta.objects.order_by('codigo', 'nome')
    erro_formulario = None

    if request.method == 'POST':
        nome = (request.POST.get('nome') or '').strip()
        plano_conta_id = _to_int_or_none(request.POST.get('plano_conta_id'))
        cor_hexadecimal = (request.POST.get('cor_hexadecimal') or '').strip() or None

        if not nome:
            erro_formulario = 'Nome da tag é obrigatório.'
        else:
            tag.nome = nome
            tag.plano_conta_id = plano_conta_id
            tag.cor_hexadecimal = cor_hexadecimal
            tag.save()
            return redirect('contas:lista_tags')

    context = {
        'acao': 'editar',
        'tag': tag,
        'planos': planos,
        'erro_formulario': erro_formulario,
    }
    return render(request, 'contas/tags/form.html', context)


@require_http_methods(["POST"])
def excluir_tag(request, tag_id):
    tag = get_object_or_404(Tag, pk=tag_id)
    tag.delete()
    return redirect('contas:lista_tags')


@require_http_methods(["GET"])
def lista_contas_bancarias(request):
    query = (request.GET.get('q') or '').strip()
    tipo = (request.GET.get('tipo') or '').strip()

    contas = ContaBancaria.objects.order_by('nome')
    if query:
        contas = contas.filter(nome__icontains=query)
    if tipo:
        contas = contas.filter(tipo=tipo)

    contas = list(contas)
    conta_ids = [conta.id for conta in contas]
    mapa_saldo_mov = {conta_id: Decimal('0.00') for conta_id in conta_ids}

    if conta_ids:
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
        for item in agregados:
            mapa_saldo_mov[item['conta_bancaria_id']] = (item['total_creditos'] - item['total_debitos']).quantize(Decimal('0.01'))

    for conta in contas:
        saldo_mov = mapa_saldo_mov.get(conta.id, Decimal('0.00'))
        conta.saldo_atual = (conta.saldo_inicial + saldo_mov).quantize(Decimal('0.01'))

    context = {
        'contas': contas,
        'query': query,
        'tipo': tipo,
        'tipo_choices': ContaBancaria.Tipo.choices,
    }
    return render(request, 'contas/contas_bancarias/lista.html', context)


@require_http_methods(["GET", "POST"])
def nova_conta_bancaria(request):
    erro_formulario = None

    if request.method == 'POST':
        nome = (request.POST.get('nome') or '').strip()
        tipo = request.POST.get('tipo')
        saldo_inicial = _to_decimal(request.POST.get('saldo_inicial'))
        limite_credito = _to_decimal(request.POST.get('limite_credito'), default=None)
        dia_vencimento = _to_int_or_none(request.POST.get('dia_vencimento'))
        dia_fechamento = _to_int_or_none(request.POST.get('dia_fechamento'))

        if not nome:
            erro_formulario = 'Nome da conta bancária é obrigatório.'
        else:
            ContaBancaria.objects.create(
                nome=nome,
                tipo=tipo,
                saldo_inicial=saldo_inicial,
                limite_credito=limite_credito,
                dia_vencimento=dia_vencimento,
                dia_fechamento=dia_fechamento,
            )
            return redirect('contas:lista_contas_bancarias')

    context = {
        'acao': 'novo',
        'conta': None,
        'tipo_choices': ContaBancaria.Tipo.choices,
        'erro_formulario': erro_formulario,
    }
    return render(request, 'contas/contas_bancarias/form.html', context)


@require_http_methods(["GET", "POST"])
def editar_conta_bancaria(request, conta_id):
    conta = get_object_or_404(ContaBancaria, pk=conta_id)
    erro_formulario = None

    if request.method == 'POST':
        nome = (request.POST.get('nome') or '').strip()
        tipo = request.POST.get('tipo')
        saldo_inicial = _to_decimal(request.POST.get('saldo_inicial'))
        limite_credito = _to_decimal(request.POST.get('limite_credito'), default=None)
        dia_vencimento = _to_int_or_none(request.POST.get('dia_vencimento'))
        dia_fechamento = _to_int_or_none(request.POST.get('dia_fechamento'))

        if not nome:
            erro_formulario = 'Nome da conta bancária é obrigatório.'
        else:
            conta.nome = nome
            conta.tipo = tipo
            conta.saldo_inicial = saldo_inicial
            conta.limite_credito = limite_credito
            conta.dia_vencimento = dia_vencimento
            conta.dia_fechamento = dia_fechamento
            conta.save()
            return redirect('contas:lista_contas_bancarias')

    context = {
        'acao': 'editar',
        'conta': conta,
        'tipo_choices': ContaBancaria.Tipo.choices,
        'erro_formulario': erro_formulario,
    }
    return render(request, 'contas/contas_bancarias/form.html', context)


@require_http_methods(["POST"])
def excluir_conta_bancaria(request, conta_id):
    conta = get_object_or_404(ContaBancaria, pk=conta_id)
    try:
        conta.delete()
    except ProtectedError:
        return redirect('contas:lista_contas_bancarias')
    return redirect('contas:lista_contas_bancarias')


@require_http_methods(["GET"])
def listar_tags_json(request):
    """Retorna lista de tags em JSON, com busca opcional via 'q'."""
    query = request.GET.get('q', '').strip()
    tipo = request.GET.get('tipo', '').strip()

    tags = Tag.objects.select_related('plano_conta').all().order_by('nome')
    if query:
        tags = tags.filter(nome__icontains=query)

    if tipo:
        tags_prioritarias = list(tags.filter(plano_conta__tipo_natureza=tipo)[:20])
        ids_prioritarias = [tag.id for tag in tags_prioritarias]
        limite_restante = max(20 - len(tags_prioritarias), 0)
        tags_demais = list(tags.exclude(id__in=ids_prioritarias)[:limite_restante]) if limite_restante else []
        tags_ordenadas = tags_prioritarias + tags_demais
    else:
        tags_ordenadas = list(tags[:20])

    data = {
        'results': [
            {
                'id': tag.id,
                'text': tag.nome,
                'plano_conta_id': tag.plano_conta_id,
            }
            for tag in tags_ordenadas
        ]
    }
    return JsonResponse(data)


@require_http_methods(["POST"])
def criar_tag_ajax(request):
    """Cria uma nova tag via AJAX e retorna JSON com id e nome."""
    try:
        nome = request.POST.get('nome', '').strip()
        plano_conta_id = request.POST.get('plano_conta_id')
        cor_hexadecimal = request.POST.get('cor_hexadecimal', '').strip() or None

        if not nome:
            return JsonResponse({'error': 'Nome da tag é obrigatório'}, status=400)

        # Verifica se já existe
        tag_existente = Tag.objects.filter(nome=nome).first()
        if tag_existente:
            return JsonResponse({
                'id': tag_existente.id,
                'text': tag_existente.nome,
                'plano_conta_id': tag_existente.plano_conta_id,
                'message': 'Tag já existe'
            })

        # Se plano_conta_id foi fornecido, usa; caso contrário, deixa null
        plano_conta = None
        if plano_conta_id:
            try:
                plano_conta = PlanoConta.objects.get(id=plano_conta_id)
            except PlanoConta.DoesNotExist:
                pass

        # Cria nova tag
        tag = Tag.objects.create(nome=nome, plano_conta=plano_conta, cor_hexadecimal=cor_hexadecimal)

        return JsonResponse({
            'id': tag.id,
            'text': tag.nome,
            'plano_conta_id': tag.plano_conta_id,
            'message': 'Tag criada com sucesso'
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

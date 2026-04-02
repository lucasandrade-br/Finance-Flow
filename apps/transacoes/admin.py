from django.contrib import admin

from .models import LancamentoFuturo, Movimentacao, TransacaoRecorrente


@admin.register(TransacaoRecorrente)
class TransacaoRecorrenteAdmin(admin.ModelAdmin):
    list_display = ('descricao', 'tipo', 'valor_base', 'dia_vencimento', 'status_ativa')
    list_filter = ('tipo', 'status_ativa', 'formato_pagamento')
    search_fields = ('descricao',)


@admin.register(LancamentoFuturo)
class LancamentoFuturoAdmin(admin.ModelAdmin):
    list_display = ('descricao', 'tipo', 'valor', 'data_vencimento', 'status')
    list_filter = ('tipo', 'status', 'formato_pagamento')
    search_fields = ('descricao',)
    date_hierarchy = 'data_vencimento'


@admin.register(Movimentacao)
class MovimentacaoAdmin(admin.ModelAdmin):
    list_display = ('descricao', 'tipo', 'valor', 'status', 'data_vencimento', 'data_pagamento', 'conta_bancaria')
    list_filter = ('tipo', 'status', 'formato_pagamento')
    search_fields = ('descricao',)
    date_hierarchy = 'data_vencimento'
    autocomplete_fields = ('conta_bancaria', 'plano_conta')
    raw_id_fields = ('ciclo', 'cofre', 'lancamento_pai', 'lancamento_par')

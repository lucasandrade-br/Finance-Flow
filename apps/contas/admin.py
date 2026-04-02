from django.contrib import admin

from .models import ContaBancaria, PlanoConta, Tag


@admin.register(PlanoConta)
class PlanoContaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'tipo_natureza', 'conta_pai')
    list_filter = ('tipo_natureza',)
    search_fields = ('nome',)


@admin.register(ContaBancaria)
class ContaBancariaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'tipo', 'saldo_inicial')
    list_filter = ('tipo',)
    search_fields = ('nome',)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('nome', 'plano_conta')
    search_fields = ('nome',)

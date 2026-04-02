from django.urls import path

from apps.orcamento.views import (
    abrir_ciclo,
    cockpit_ciclo,
    confirmar_movimentacao,
    encerrar_ciclo,
    matriz_planejamento,
)

app_name = 'orcamento'

urlpatterns = [
    path('cockpit/', cockpit_ciclo, name='cockpit_ciclo'),
    path('planejamento/matriz/', matriz_planejamento, name='matriz_planejamento'),
    path('planejamento/matriz/<int:ano>/', matriz_planejamento, name='matriz_planejamento_ano'),
    path('cockpit/movimentacoes/<int:movimentacao_id>/confirmar/', confirmar_movimentacao, name='confirmar_movimentacao'),
    path('cockpit/abrir/', abrir_ciclo, name='abrir_ciclo'),
    path('cockpit/encerrar/', encerrar_ciclo, name='encerrar_ciclo'),
]
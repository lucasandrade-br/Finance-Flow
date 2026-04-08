from django.urls import path

from apps.orcamento.views import (
    abrir_ciclo,
    cockpit_ciclo,
    confirmar_movimentacao,
    remover_movimentacao_do_ciclo,
    editar_movimentacao_orcamento,
    encerrar_ciclo,
    excluir_movimentacao_orcamento,
    lista_movimentacoes_orcamento,
    matriz_planejamento,
    nova_movimentacao_orcamento,
    simulacao_capital,
)

app_name = 'orcamento'

urlpatterns = [
    path('cockpit/', cockpit_ciclo, name='cockpit_ciclo'),
    path('planejamento/matriz/', matriz_planejamento, name='matriz_planejamento'),
    path('planejamento/matriz/<int:ano>/', matriz_planejamento, name='matriz_planejamento_ano'),
    path('planejamento/movimentacoes/', lista_movimentacoes_orcamento, name='lista_movimentacoes_orcamento'),
    path('planejamento/movimentacoes/nova/', nova_movimentacao_orcamento, name='nova_movimentacao_orcamento'),
    path('planejamento/movimentacoes/<int:registro_id>/editar/', editar_movimentacao_orcamento, name='editar_movimentacao_orcamento'),
    path('planejamento/movimentacoes/<int:registro_id>/excluir/', excluir_movimentacao_orcamento, name='excluir_movimentacao_orcamento'),
    path('planejamento/simulacao/', simulacao_capital, name='simulacao_capital'),
    path('planejamento/simulacao/<int:ano>/', simulacao_capital, name='simulacao_capital_ano'),
    path('cockpit/movimentacoes/<int:movimentacao_id>/confirmar/', confirmar_movimentacao, name='confirmar_movimentacao'),
    path('cockpit/movimentacoes/<int:movimentacao_id>/remover-ciclo/', remover_movimentacao_do_ciclo, name='remover_movimentacao_do_ciclo'),
    path('cockpit/abrir/', abrir_ciclo, name='abrir_ciclo'),
    path('cockpit/encerrar/', encerrar_ciclo, name='encerrar_ciclo'),
]
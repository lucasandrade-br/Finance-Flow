from django.urls import path

from . import views

app_name = 'investimentos'

urlpatterns = [
    path('metas/', views.lista_metas, name='lista_metas'),
    path('metas/nova/', views.nova_meta, name='nova_meta'),
    path('metas/<int:meta_id>/roteiro/', views.roteiro_meta, name='roteiro_meta'),
    path('metas/<int:meta_id>/painel/', views.painel_meta, name='painel_meta'),
    path('metas/<int:meta_id>/editar/', views.editar_meta, name='editar_meta'),
    path('metas/<int:meta_id>/excluir/', views.excluir_meta, name='excluir_meta'),
]

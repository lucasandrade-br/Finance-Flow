from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('analises/dashboard/', views.dashboard_analitico, name='dashboard_analitico'),
]

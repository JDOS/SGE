from django.urls import path

from . import views, views_vistoria

urlpatterns = [
    path("", views.home, name="home"),
    path("modulos/", views.modulos, name="modulos"),
    path("painel/", views.painel, name="painel"),
    path("metodologia/", views.metodologia, name="metodologia"),
    path("escolas/", views.pesquisa_escolas, name="pesquisa_escolas"),
    path("escolas/<int:pk>/", views.escola_detalhe, name="escola_detalhe"),
    # vistoria — etapa 1: locais e problemas
    path("vistorias/<int:pk>/locais/", views_vistoria.vistoria_locais, name="vistoria_locais"),
    path("vistorias/<int:pk>/ocorrencias/nova/", views_vistoria.ocorrencia_form, name="ocorrencia_nova"),
    path("vistorias/<int:pk>/ocorrencias/<int:oc>/", views_vistoria.ocorrencia_form, name="ocorrencia_editar"),
    path("vistorias/<int:pk>/ocorrencias/<int:oc>/excluir/", views_vistoria.ocorrencia_excluir, name="ocorrencia_excluir"),
]

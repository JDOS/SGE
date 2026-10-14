from django.urls import path

from sge.views import index, pesquisa_escolas, escola_detalhe, metodologia, painel, modulos

from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('', index, name='index'),
    path("painel/", painel, name="painel"),
    path("escolas/", pesquisa_escolas, name="pesquisa_escolas"),
    path("escolas/<int:pk>/", escola_detalhe, name="escola_detalhe"),
    path("metodologia/", metodologia, name="metodologia"),
    path("modulos/", modulos, name="modulos"),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
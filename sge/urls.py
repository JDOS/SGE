from django.urls import path

from sge.views import index, pesquisa_escolas, escola_detalhe, metodologia

from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('', index, name='index'),
    path("escolas/", pesquisa_escolas, name="pesquisa_escolas"),
    path("escolas/<int:pk>/", escola_detalhe, name="escola_detalhe"),
    path("metodologia/", metodologia, name="metodologia"),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
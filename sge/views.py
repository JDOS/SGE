from django.shortcuts import render
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from .painel_dados import gerar_painel

from .models import Escola

def index(request):
    return render(request,'sge/index.html')

ETAPAS = {
    "infantil": ("educacao_infantil", "Educação infantil"),
    "fund1": ("fundamental_1", "Fundamental I"),
    "fund2": ("fundamental_2", "Fundamental II"),
    "eja": ("eja", "EJA"),
}

def painel(request):
    return render(request, "sge/painel.html", {"painel": gerar_painel()})


def metodologia(request):
    return render(request, "sge/metodologia.html")

def modulos(request):
    painel = reverse("painel")
    itens = [
        ("Não conformidades", "nao_conformidades.png", painel,
         "Problemas encontrados nas vistorias"),
        ("Segurança contra fogo", "seguranca_fogo.png", painel + "?categoria=Segurança+contra+incêndio",
         "Extintores, rotas de fuga e sinalização"),
        ("Acessibilidade", "acessibilidade.png", painel + "?categoria=Acessibilidade",
         "Rampas, sanitários PCD e piso tátil"),
        ("Índice de Performance", "indice_performance.png", painel,
         "Nota e ranking das escolas"),
        ("Conforto", "conforto.png", painel + "?categoria=Conforto+térmico",
         "Térmico, visual e acústico"),
        ("Histórico", "historico.png", "", "Evolução das escolas ao longo do tempo"),
        ("Relatórios", "relatorios.png", "", "Documentos de vistoria e orçamento"),
        ("Araucarinho", "araucarinho.png", "", "Educação e conscientização dos alunos"),
    ]
    modulos = [
        {"titulo": t, "imagem": "img/modulos/" + img, "url": url, "descricao": d}
        for t, img, url, d in itens
    ]
    return render(request, "sge/modulos.html", {"modulos": modulos})


def pesquisa_escolas(request):
    escolas = Escola.objects.all()

    busca = request.GET.get("q", "").strip()
    municipio = request.GET.get("municipio", "").strip()
    etapa = request.GET.get("etapa", "").strip()

    if busca:
        escolas = escolas.filter(
            Q(nome__icontains=busca) | Q(codigo_inep__icontains=busca)
            | Q(bairro__icontains=busca) | Q(endereco__icontains=busca)
        )
    if municipio:
        escolas = escolas.filter(municipio=municipio)
    if etapa in ETAPAS:
        escolas = escolas.filter(**{ETAPAS[etapa][0]: True})

    # dados para o mapa (só escolas com coordenadas)
    pontos = [
        {
            "id": e.pk,
            "nome": e.nome,
            "lat": float(e.latitude),
            "lng": float(e.longitude),
            "endereco": e.endereco,
            "municipio": e.municipio,
            "foto": e.foto.url if e.foto else "",
            "url": reverse("escola_detalhe", args=[e.pk]),
        }
        for e in escolas
        if e.latitude is not None and e.longitude is not None
    ]

    contexto = {
        "escolas": escolas,
        "pontos": pontos,
        "municipios": Escola.objects.order_by("municipio")
                                    .values_list("municipio", flat=True).distinct(),
        "etapas": [(chave, rotulo) for chave, (_, rotulo) in ETAPAS.items()],
        "filtro": {"q": busca, "municipio": municipio, "etapa": etapa},
        "filtro_ativo": bool(busca or municipio or etapa),
    }
    return render(request, "sge/escolas_pesquisa.html", contexto)


def escola_detalhe(request, pk):
    escola = get_object_or_404(Escola, pk=pk)
    return render(request, "sge/escola_detalhe.html", {"escola": escola})

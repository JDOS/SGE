from django.shortcuts import render
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from .painel_dados import gerar_painel
from decimal import Decimal
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
 
    # vistorias da escola, da mais recente para a mais antiga, com o orçamento de cada uma
    vistorias = list(escola.vistorias.select_related("responsavel").order_by("-data", "-pk"))
    for v in vistorias:
        v.itens = v.itens_orcamento()
        v.total = sum((i.custo_calc for i in v.itens), Decimal("0.00"))
        c = v.contagem()
        v.qtd_criterios = sum(c.values())
        v.respondidos = v.qtd_criterios - c[""]
        v.qtd_nao = c["N"]
        aplicaveis = c["S"] + c["N"]
        v.atende = round(100 * c["S"] / aplicaveis) if aplicaveis else None
 
    # resumo por categoria da vistoria mais recente
    ultima = vistorias[0] if vistorias else None
    categorias = []
    if ultima and ultima.itens:
        grupos = {}
        for i in ultima.itens:
            nome = i.criterio.categoria.nome
            g = grupos.setdefault(nome, {"nome": nome, "qtd": 0, "total": Decimal("0.00")})
            g["qtd"] += 1
            g["total"] += i.custo_calc
        categorias = sorted(grupos.values(), key=lambda g: g["total"], reverse=True)
        maior = categorias[0]["total"] or Decimal("1")
        for g in categorias:
            g["barra"] = round(100 * g["total"] / maior)
            g["parcela"] = round(100 * g["total"] / ultima.total) if ultima.total else 0
 
    return render(request, "sge/escola_detalhe.html", {
        "escola": escola,
        "vistorias": vistorias,
        "ultima": ultima,
        "categorias": categorias,
    })
 
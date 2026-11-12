"""
Vistoria — Etapa 1: locais e problemas.

O engenheiro percorre os locais da escola. Em cada local com problema, registra uma
ocorrência: escolhe (ou cadastra) o local, procura o problema, marca as causas e os
serviços (reparos) com as quantidades. A soma de tudo é o orçamento da vistoria.
Depois segue para a Etapa 2 (critérios S / N / NA), no admin.
"""
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.db.models import Prefetch
from django.db.models.functions import Lower
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import (
    ItemSolucao, Local, Ocorrencia, OcorrenciaReparo, Problema, TipoLocal, Vistoria, custos_unitarios,
)


# ----------------------------------------------------------------- auxiliares
def _decimal(texto):
    """Aceita 12,5 · 12.5 · 1.234,50. Devolve None se vazio ou inválido."""
    texto = (texto or "").strip()
    if not texto:
        return None
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return Decimal(texto)
    except InvalidOperation:
        return None


def _dados_problemas():
    """Problemas -> causas -> reparos (com tipo e condição da solução), para o JavaScript."""
    problemas = Problema.objects.prefetch_related(
        "causas__problema",
        Prefetch("causas__solucoes__itens",
                 queryset=ItemSolucao.objects.select_related("reparo__unidade", "solucao")),
    )
    reparos_usados = {}
    lista = []
    for p in problemas:
        causas = []
        for c in p.causas.all():
            reparos, solucoes = [], []
            for sol in c.solucoes.all():
                grupos = {}
                for item in sol.itens.all():
                    r = item.reparo
                    reparos_usados[r.pk] = r
                    reparos.append({
                        "id": r.pk,
                        "tipo": sol.get_tipo_display(),
                        "condicao": sol.condicao,
                        "rotulo": item.rotulo,
                    })
                    grupos.setdefault(item.grupo, []).append({"id": r.pk, "rotulo": item.rotulo})
                solucoes.append({
                    "id": sol.pk, "tipo": sol.get_tipo_display(), "condicao": sol.condicao,
                    "grupos": [grupos[g] for g in sorted(grupos)],
                })
            causas.append({"id": c.pk, "codigo": c.codigo, "descricao": c.descricao,
                           "reparos": reparos, "solucoes": solucoes})
        lista.append({"id": p.pk, "codigo": p.codigo, "nome": p.nome, "causas": causas})

    unitarios = custos_unitarios(set(reparos_usados))
    reparos = {
        str(pk): {
            "codigo": r.codigo, "nome": r.nome, "sigla": r.unidade.sigla,
            "custo": str(unitarios.get(pk, Decimal("0.00"))),
        }
        for pk, r in reparos_usados.items()
    }
    return {"problemas": lista, "reparos": reparos}


# --------------------------------------------------------------- etapa 1: lista
@staff_member_required
def vistoria_locais(request, pk):
    vistoria = get_object_or_404(Vistoria.objects.select_related("escola", "responsavel"), pk=pk)
    itens = vistoria.itens_orcamento()

    # agrupa: local -> ocorrências -> itens
    por_ocorrencia = {}
    for i in itens:
        por_ocorrencia.setdefault(i.ocorrencia_id, []).append(i)

    ocorrencias = (vistoria.ocorrencias
                   .select_related("local__tipo_local", "problema")
                   .prefetch_related("causas__problema")
                   .order_by(Lower("local__nome"), "pk"))
    locais = []
    for oc in ocorrencias:
        oc.lista_itens = por_ocorrencia.get(oc.pk, [])
        oc.subtotal = sum((i.custo_calc for i in oc.lista_itens), Decimal("0.00"))
        if not locais or locais[-1]["local"].pk != oc.local_id:
            locais.append({"local": oc.local, "ocorrencias": [], "subtotal": Decimal("0.00")})
        locais[-1]["ocorrencias"].append(oc)
        locais[-1]["subtotal"] += oc.subtotal

    return render(request, "sge/vistoria_locais.html", {
        "vistoria": vistoria,
        "locais": locais,
        "qtd_ocorrencias": sum(len(l["ocorrencias"]) for l in locais),
        "total": sum((i.custo_calc for i in itens), Decimal("0.00")),
        "url_etapa2": reverse("admin:sge_vistoria_change", args=[vistoria.pk]),
    })


# ------------------------------------------------------ etapa 1: registrar/editar
@staff_member_required
def ocorrencia_form(request, pk, oc=None):
    vistoria = get_object_or_404(Vistoria.objects.select_related("escola"), pk=pk)
    escola = vistoria.escola
    ocorrencia = get_object_or_404(Ocorrencia, pk=oc, vistoria=vistoria) if oc else None

    dados = _dados_problemas()
    erros = []

    # valores iniciais (edição) ou enviados (POST com erro)
    valores = {
        "local": str(ocorrencia.local_id) if ocorrencia else "",
        "problema": str(ocorrencia.problema_id) if ocorrencia else "",
        "causas": [str(c) for c in ocorrencia.causas.values_list("pk", flat=True)] if ocorrencia else [],
        "reparos": {str(i.reparo_id): str(i.quantidade) for i in ocorrencia.itens.all()} if ocorrencia else {},
        "observacao": ocorrencia.observacao if ocorrencia else "",
        "novo": {"nome": "", "tipo": "", "tipo_novo": "", "ambiente": "interno", "coberto": True, "area_molhada": False},
    }

    if request.method == "POST":
        post = request.POST
        valores["local"] = post.get("local", "")
        valores["problema"] = post.get("problema", "")
        valores["causas"] = post.getlist("causas")
        valores["reparos"] = {rid: post.get(f"qtd_{rid}", "") for rid in post.getlist("reparos")}
        valores["observacao"] = post.get("observacao", "").strip()
        valores["novo"] = {
            "nome": post.get("novo_nome", "").strip(),
            "tipo": post.get("novo_tipo", ""),
            "tipo_novo": post.get("novo_tipo_novo", "").strip(),
            "ambiente": post.get("novo_ambiente", "interno"),
            "coberto": bool(post.get("novo_coberto")),
            "area_molhada": bool(post.get("novo_area_molhada")),
        }

        # ---- local
        local = None
        if valores["local"] == "novo":
            n = valores["novo"]
            if not n["nome"]:
                erros.append("Informe o nome do novo local.")
            elif escola.locais.filter(nome__iexact=n["nome"]).exists():
                erros.append(f"A escola já tem um local chamado “{n['nome']}”. Escolha-o na lista.")
            if not n["tipo"] and not n["tipo_novo"]:
                erros.append("Escolha o tipo do novo local (ou digite um tipo novo).")
        else:
            local = escola.locais.filter(pk=valores["local"] or 0).first()
            if local is None:
                erros.append("Escolha o local onde o problema foi visto.")

        # ---- problema
        problema = Problema.objects.filter(pk=valores["problema"] or 0).first()
        if problema is None:
            erros.append("Escolha o problema visualizado.")

        # ---- causas e reparos (precisam pertencer ao problema)
        causas, itens = [], []
        if problema:
            info = next(p for p in dados["problemas"] if p["id"] == problema.pk)
            causas_validas = {str(c["id"]) for c in info["causas"]}
            reparos_validos = {str(r["id"]) for c in info["causas"] for r in c["reparos"]}
            causas = [c for c in valores["causas"] if c in causas_validas]
            for rid, qtd_texto in valores["reparos"].items():
                if rid not in reparos_validos:
                    continue
                qtd = _decimal(qtd_texto)
                rep = dados["reparos"][rid]
                if qtd is None or qtd <= 0:
                    erros.append(f"Informe a quantidade (em {rep['sigla']}) de “{rep['nome']}”.")
                else:
                    itens.append((int(rid), qtd))
            if not causas and not itens:
                erros.append("Marque pelo menos uma causa ou um serviço.")

        if not erros:
            with transaction.atomic():
                if local is None:
                    n = valores["novo"]
                    tipo = (TipoLocal.objects.filter(pk=n["tipo"] or 0).first()
                            or TipoLocal.objects.get_or_create(nome=n["tipo_novo"])[0])
                    local = Local.objects.create(
                        escola=escola, tipo_local=tipo, nome=n["nome"],
                        ambiente=n["ambiente"] if n["ambiente"] in Local.Ambiente.values else Local.Ambiente.INTERNO,
                        coberto=n["coberto"], area_molhada=n["area_molhada"],
                    )
                if ocorrencia is None:
                    ocorrencia = Ocorrencia(vistoria=vistoria)
                ocorrencia.local = local
                ocorrencia.problema = problema
                ocorrencia.observacao = valores["observacao"]
                if request.FILES.get("foto"):
                    ocorrencia.foto = request.FILES["foto"]
                elif post.get("remover_foto"):
                    ocorrencia.foto = None
                ocorrencia.save()
                ocorrencia.causas.set(causas)
                ocorrencia.itens.all().delete()
                OcorrenciaReparo.objects.bulk_create(
                    OcorrenciaReparo(ocorrencia=ocorrencia, reparo_id=rid, quantidade=qtd) for rid, qtd in itens
                )
            messages.success(request, f"Problema registrado em “{local.nome}”.")
            if post.get("continuar"):
                return redirect("ocorrencia_nova", pk=vistoria.pk)
            return redirect("vistoria_locais", pk=vistoria.pk)

    return render(request, "sge/ocorrencia_form.html", {
        "vistoria": vistoria,
        "ocorrencia": ocorrencia,
        "locais": escola.locais.select_related("tipo_local").order_by("tipo_local__nome", Lower("nome")),
        "tipos_local": TipoLocal.objects.all(),
        "ambientes": Local.Ambiente.choices,
        "dados": dados,
        "valores": valores,
        "erros": erros,
    })


@staff_member_required
@require_POST
def ocorrencia_excluir(request, pk, oc):
    ocorrencia = get_object_or_404(Ocorrencia, pk=oc, vistoria_id=pk)
    ocorrencia.delete()
    messages.success(request, "Ocorrência excluída.")
    return redirect("vistoria_locais", pk=pk)

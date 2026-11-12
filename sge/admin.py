import re
from decimal import Decimal, ROUND_HALF_UP

from django import forms
from django.contrib import admin
from django.contrib.admin.widgets import AutocompleteSelectMultiple
from django.db import models
from django.db.models import Count
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe

from .models import (
    Atividade, Categoria, Causa, Criterio, Escola, ItemSolucao, Local, Ocorrencia, OcorrenciaReparo, Problema,
    Reparo, ReparoAtividade, RespostaVistoria, Solucao, TipoLocal,
    Unidade, Vistoria,
)



def _nome_usuario(usuario):
    """Nome completo do usuário; se não tiver nome cadastrado, usa o login."""
    return usuario.get_full_name() or usuario.username


def _num(valor):
    """Número no formato brasileiro, sem zeros sobrando: 0.020000 -> 0,02 ; 1.000000 -> 1"""
    texto = format(Decimal(valor).normalize(), "f")
    return texto.replace(".", ",")


def _brl(valor):
    """Formata um número como dinheiro: 1234.5 -> R$ 1.234,50"""
    texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"

class EscolaAdminForm(forms.ModelForm):
    coordenadas = forms.CharField(
        label="coordenadas (GPS)",
        required=False,
        help_text="Cole direto do Google Maps. Ex.: -25.585836494122628, -49.41221799143538",
        widget=forms.TextInput(attrs={"size": 45, "placeholder": "-25.585836, -49.412217"}),
    )

    class Meta:
        model = Escola
        exclude = ("latitude", "longitude")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        inst = self.instance
        if inst.pk and inst.latitude is not None and inst.longitude is not None:
            self.fields["coordenadas"].initial = f"{inst.latitude}, {inst.longitude}"

    def clean_coordenadas(self):
        texto = (self.cleaned_data.get("coordenadas") or "").strip()
        if not texto:
            self._lat = self._lng = None
            return texto
        numeros = re.findall(r"-?\d+(?:\.\d+)?", texto)
        if len(numeros) != 2:
            raise forms.ValidationError(
                "Use o formato latitude, longitude. Ex.: -25.585836, -49.412217"
            )
        seis_casas = Decimal("0.000001")
        lat = Decimal(numeros[0]).quantize(seis_casas, rounding=ROUND_HALF_UP)
        lng = Decimal(numeros[1]).quantize(seis_casas, rounding=ROUND_HALF_UP)
        if not -90 <= lat <= 90:
            raise forms.ValidationError("A latitude deve estar entre -90 e 90.")
        if not -180 <= lng <= 180:
            raise forms.ValidationError("A longitude deve estar entre -180 e 180.")
        self._lat, self._lng = lat, lng
        return texto

    def save(self, commit=True):
        self.instance.latitude = getattr(self, "_lat", self.instance.latitude)
        self.instance.longitude = getattr(self, "_lng", self.instance.longitude)
        return super().save(commit=commit)


class LocalFormSet(forms.BaseInlineFormSet):
    """Impede nomes repetidos (sem diferenciar maiúsculas) entre as linhas enviadas juntas."""

    def clean(self):
        super().clean()
        vistos = {}
        for form in self.forms:
            if not hasattr(form, "cleaned_data") or form.cleaned_data.get("DELETE"):
                continue
            nome = (form.cleaned_data.get("nome") or "").strip().lower()
            if not nome:
                continue
            if nome in vistos:
                form.add_error("nome", "Nome repetido: já existe outro local com esse nome nesta escola.")
            vistos[nome] = form


class LocalInline(admin.TabularInline):
    model = Local
    formset = LocalFormSet
    extra = 1
    fields = ("tipo_local", "nome", "ambiente", "coberto", "area_molhada", "foto", "miniatura")
    readonly_fields = ("miniatura",)
    verbose_name_plural = "Locais da escola"

    @admin.display(description="")
    def miniatura(self, obj):
        if obj.foto:
            return format_html(
                '<a href="{0}" target="_blank" rel="noopener"><img src="{0}" '
                'style="width:72px;height:54px;object-fit:cover;border-radius:3px;"></a>',
                obj.foto.url,
            )
        return ""


@admin.register(Escola)
class EscolaAdmin(admin.ModelAdmin):
    form = EscolaAdminForm
    inlines = [LocalInline]
    list_display = (
        "miniatura", "nome", "codigo_inep", "municipio", "bairro",
        "alunos_matriculados", "funcionarios", "sistema_construtivo",
    )
    list_display_links = ("miniatura", "nome")
    search_fields = ("nome", "codigo_inep", "municipio", "bairro", "diretor")
    list_filter = (
        "municipio", "sistema_construtivo",
        "educacao_infantil", "fundamental_1", "fundamental_2", "eja",
        "turno_integral",
    )
    readonly_fields = ("previa_foto", "link_mapa", "criado_em", "atualizado_em")
    list_per_page = 25

    fieldsets = (
        ("1. Identificação", {
            "fields": ("nome", "codigo_inep", ("foto", "previa_foto"), "relatorio"),
        }),
        ("Localização", {
            "fields": ("endereco", ("bairro", "municipio", "uf"), ("coordenadas", "link_mapa")),
        }),
        ("Etapas de ensino", {
            "fields": (("educacao_infantil", "fundamental_1", "fundamental_2", "eja"),),
        }),
        ("Turnos", {
            "fields": (("turno_manha", "turno_tarde", "turno_noite", "turno_integral"),),
        }),
        ("Comunidade escolar", {
            "fields": (
                ("alunos_matriculados", "funcionarios"),
                ("alunos_com_deficiencia", "detalhe_deficiencia"),
            ),
        }),
        ("Edificação", {
            "fields": (
                ("area_terreno", "area_construida"),
                ("pavimentos", "pavimentos_obs"),
                "ano_construcao",
                ("ultima_reforma_ano", "ultima_reforma_escopo"),
                "sistema_construtivo",
            ),
        }),
        ("Contato", {
            "fields": ("diretor", ("telefone", "email")),
        }),
        ("Registro", {
            "classes": ("collapse",),
            "fields": (("criado_em", "atualizado_em"),),
        }),
    )

    @admin.display(description="Foto")
    def miniatura(self, obj):
        if obj.foto:
            return format_html(
                '<img src="{}" style="width:64px;height:44px;object-fit:cover;border-radius:3px;">',
                obj.foto.url,
            )
        return "—"

    @admin.display(description="Prévia")
    def previa_foto(self, obj):
        if obj.foto:
            return format_html(
                '<img src="{}" style="max-width:320px;max-height:220px;border-radius:4px;">',
                obj.foto.url,
            )
        return "Nenhuma foto enviada."

    @admin.display(description="Mapa")
    def link_mapa(self, obj):
        if obj.latitude is not None and obj.longitude is not None:
            return format_html(
                '<a href="https://www.google.com/maps?q={},{}" target="_blank" rel="noopener">Ver no Google Maps</a>',
                obj.latitude, obj.longitude,
            )
        return "—"



class CriterioInline(admin.TabularInline):
    model = Criterio
    extra = 1
    fields = ("nome", "o_que_verificar")


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nome", "qtd_criterios")
    search_fields = ("nome",)
    inlines = [CriterioInline]

    @admin.display(description="Critérios")
    def qtd_criterios(self, obj):
        return obj.criterios.count()


@admin.register(Unidade)
class UnidadeAdmin(admin.ModelAdmin):
    list_display = ("nome", "sigla")
    search_fields = ("nome", "sigla")


@admin.register(Criterio)
class CriterioAdmin(admin.ModelAdmin):
    list_display = ("nome", "categoria", "resumo", "qtd_reparos")
    list_filter = ("categoria",)
    search_fields = ("nome", "o_que_verificar", "categoria__nome")
    list_select_related = ("categoria",)
    fields = ("categoria", "nome", "o_que_verificar", "reparos")
    filter_horizontal = ("reparos",)

    @admin.display(description="Reparos")
    def qtd_reparos(self, obj):
        return obj.reparos.count()

    @admin.display(description="O que verificar")
    def resumo(self, obj):
        texto = obj.o_que_verificar
        return texto if len(texto) <= 90 else texto[:90] + "…"


class ReparoAtividadeInline(admin.TabularInline):
    model = ReparoAtividade
    extra = 1
    autocomplete_fields = ("atividade",)
    fields = ("atividade", "coeficiente", "unidade_atividade", "custo_atividade", "subtotal_fmt")
    readonly_fields = ("unidade_atividade", "custo_atividade", "subtotal_fmt")
    verbose_name = "item"
    verbose_name_plural = "Composição (bases de referência × coeficiente)"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("atividade__unidade")

    @admin.display(description="Unid.")
    def unidade_atividade(self, obj):
        return obj.atividade.unidade.sigla if obj.pk and obj.atividade.unidade else ""

    @admin.display(description="Custo unit.")
    def custo_atividade(self, obj):
        if not obj.pk:
            return ""
        return _brl(obj.atividade.custo) if obj.atividade.custo is not None else "sem custo"

    @admin.display(description="Subtotal")
    def subtotal_fmt(self, obj):
        return _brl(obj.subtotal) if obj.pk else ""


@admin.register(Reparo)
class ReparoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nome", "unidade", "qtd_atividades", "custo_unitario_fmt", "resumo")
    list_display_links = ("codigo", "nome")
    list_filter = ("unidade", ("itens_solucao__solucao__causa", admin.RelatedOnlyFieldListFilter))
    search_fields = ("codigo", "nome", "descricao")
    list_select_related = ("unidade",)
    fields = (("codigo", "nome"), "unidade", "descricao", "custo_calculado")
    readonly_fields = ("custo_calculado",)
    inlines = [ReparoAtividadeInline]

    @admin.display(description="Custo unitário")
    def custo_unitario_fmt(self, obj):
        return f"{_brl(obj.custo_unitario)} / {obj.unidade.sigla}"

    @admin.display(description="Custo calculado")
    def custo_calculado(self, obj):
        if not obj.pk:
            return "Salve o reparo para calcular o custo."
        itens = list(obj.composicao.select_related("atividade__unidade"))
        if not itens:
            return "Nenhum item da base de referência escolhido."
        linhas = format_html_join(
            "",
            "<tr><td>{}</td><td style='text-align:right'>{}</td>"
            "<td style='text-align:right'>× {}</td><td style='text-align:right'>{}</td></tr>",
            (
                (str(i.atividade),
                 _brl(i.atividade.custo) if i.atividade.custo is not None else "sem custo",
                 _num(i.coeficiente),
                 _brl(i.subtotal))
                for i in itens
            ),
        )
        sem_custo = sum(1 for i in itens if i.atividade.custo is None)
        aviso = format_html(
            "<p style='color:#b23a3a;margin:6px 0 0'>{} item(ns) sem custo, contados como R$ 0,00.</p>", sem_custo,
        ) if sem_custo else ""
        return format_html(
            "<table style='min-width:560px'><tr><th>Base de referência</th><th>Custo unit.</th>"
            "<th>Coeficiente</th><th>Subtotal</th></tr>{}<tr><th colspan='3'>Total por {}</th>"
            "<th style='text-align:right'>{}</th></tr></table>{}",
            linhas, obj.unidade.sigla, _brl(obj.custo_unitario), aviso,
        )

    @admin.display(description="Bases de referência")
    def qtd_atividades(self, obj):
        return obj.atividades.count()

    @admin.display(description="Descrição")
    def resumo(self, obj):
        texto = obj.descricao
        return texto if len(texto) <= 90 else texto[:90] + "…"


@admin.register(Atividade)
class AtividadeAdmin(admin.ModelAdmin):
    list_display = ("resumo", "codigo", "fonte", "unidade", "custo_formatado")
    list_display_links = ("resumo",)
    list_filter = ("fonte", "unidade")
    search_fields = ("descricao", "codigo")
    list_select_related = ("unidade",)
    fields = (("codigo", "fonte"), "descricao", ("unidade", "custo"))
    formfield_overrides = {
        models.TextField: {"widget": forms.Textarea(attrs={"rows": 3, "cols": 80})},
    }

    @admin.display(description="Descrição", ordering="descricao")
    def resumo(self, obj):
        texto = obj.descricao
        return texto if len(texto) <= 90 else texto[:90] + "…"

    @admin.display(description="Custo", ordering="custo")
    def custo_formatado(self, obj):
        if obj.custo is None:
            return "—"
        if obj.unidade:
            return f"{_brl(obj.custo)} / {obj.unidade.sigla}"
        return _brl(obj.custo)

# ================= VISTORIA =================

class FotoInput(forms.ClearableFileInput):
    """Campo de foto compacto: miniatura + botão para trocar + opção de remover."""

    def render(self, name, value, attrs=None, renderer=None):
        attrs = {**(attrs or {}), "accept": "image/*", "capture": "environment"}
        campo = forms.FileInput().render(name, None, attrs)
        if not (value and getattr(value, "url", None)):
            return campo
        limpar = self.clear_checkbox_name(name)
        return format_html(
            '<div class="foto-resposta">'
            '<a href="{url}" target="_blank" rel="noopener" title="Abrir foto">'
            '<img src="{url}" alt="Foto do critério"></a>'
            '<div>{campo}<label><input type="checkbox" name="{limpar}" id="{limpar}_id"> remover</label></div>'
            '</div>',
            url=value.url, campo=campo, limpar=limpar,
        )


class RespostaForm(forms.ModelForm):
    resposta = forms.ChoiceField(
        label="Resposta",
        choices=RespostaVistoria.Resposta.choices,
        widget=forms.RadioSelect(attrs={"class": "radio-sna"}),
        required=False,
    )

    class Meta:
        model = RespostaVistoria
        fields = ("resposta", "observacao", "foto")
        widgets = {
            "observacao": forms.TextInput(attrs={"size": 28, "placeholder": "Observação (opcional)"}),
            "foto": FotoInput(),
        }


class RespostaInline(admin.TabularInline):
    model = RespostaVistoria
    form = RespostaForm
    fields = ("categoria", "criterio_nome", "o_que_verificar", "resposta", "observacao", "foto")
    readonly_fields = ("categoria", "criterio_nome", "o_que_verificar")
    extra = 0
    can_delete = False
    verbose_name = "critério"
    verbose_name_plural = "Critérios da vistoria"

    class Media:
        css = {"all": ("css/vistoria_admin.css",)}
        js = ("js/vistoria_admin.js",)

    def has_add_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return (super().get_queryset(request)
                .select_related("criterio__categoria")
                .order_by("criterio_id"))

    @admin.display(description="Categoria")
    def categoria(self, obj):
        return obj.criterio.categoria.nome

    @admin.display(description="Critério")
    def criterio_nome(self, obj):
        return obj.criterio.nome

    @admin.display(description="O que verificar")
    def o_que_verificar(self, obj):
        return obj.criterio.o_que_verificar


@admin.register(Vistoria)
class VistoriaAdmin(admin.ModelAdmin):
    list_display = ("escola", "data", "responsavel_nome", "link_etapa1", "progresso", "qtd_sim", "qtd_nao", "qtd_na", "qtd_fotos", "atendimento", "custo_total_fmt")
    list_filter = ("data", "escola")
    search_fields = ("escola__nome", "escola__codigo_inep")
    date_hierarchy = "data"
    autocomplete_fields = ("escola",)
    fields = ("etapas", "escola", ("data", "responsavel"), "observacoes", "orcamento")
    readonly_fields = ("etapas", "orcamento")

    @admin.display(description="Etapas")
    def etapas(self, obj):
        if not obj.pk:
            return "Salve para começar pela Etapa 1 (locais e problemas)."
        return format_html(
            '<a class="button" href="{}">1. Locais e problemas</a> '
            '<span style="margin:0 6px">→</span> <b>2. Critérios (S / N / NA)</b> — abaixo',
            reverse("vistoria_locais", args=[obj.pk]),
        )

    @admin.display(description="Etapa 1")
    def link_etapa1(self, obj):
        return format_html('<a href="{}">locais e problemas ({})</a>',
                           reverse("vistoria_locais", args=[obj.pk]), obj.ocorrencias.count())

    @admin.display(description="Custo total")
    def custo_total_fmt(self, obj):
        return _brl(obj.custo_total)

    @admin.display(description="Orçamento estimado")
    def orcamento(self, obj):
        if not obj.pk:
            return "Salve a vistoria para calcular o orçamento."
        itens = obj.itens_orcamento()
        if not itens:
            return "Nenhum reparo lançado ainda na Etapa 1 (locais e problemas)."
        linhas = format_html_join(
            "",
            "<tr><td>{}</td><td>{}</td><td>{}</td><td style='text-align:right'>{} {}</td>"
            "<td style='text-align:right'>{}</td><td style='text-align:right'><b>{}</b></td></tr>",
            (
                (i.ocorrencia.local.nome, i.ocorrencia.problema, str(i.reparo),
                 _num(i.quantidade), i.reparo.unidade.sigla, _brl(i.custo_unit), _brl(i.custo_calc))
                for i in itens
            ),
        )
        total = sum((i.custo_calc for i in itens), 0)
        return format_html(
            "<table class='orcamento-vistoria'><thead><tr><th>Local</th><th>Problema</th><th>Reparo</th>"
            "<th>Quantidade</th><th>Custo unit.</th><th>Custo</th></tr></thead><tbody>{}</tbody>"
            "<tfoot><tr><th colspan='5'>Total</th><th style='text-align:right'>{}</th></tr></tfoot></table>",
            linhas, _brl(total),
        )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        campo = super().formfield_for_foreignkey(db_field, request, **kwargs)
        if db_field.name == "responsavel":
            campo.label_from_instance = _nome_usuario
            campo.queryset = campo.queryset.order_by("first_name", "last_name", "username")
        return campo

    @admin.display(description="Responsável", ordering="responsavel__first_name")
    def responsavel_nome(self, obj):
        return _nome_usuario(obj.responsavel) if obj.responsavel else "—"

    def get_inlines(self, request, obj):
        # os critérios aparecem depois do primeiro "Salvar"
        return [RespostaInline] if obj else []

    def save_model(self, request, obj, form, change):
        if not obj.responsavel_id:
            obj.responsavel = request.user
        super().save_model(request, obj, form, change)
        obj.preparar_respostas()

    def change_view(self, request, object_id, form_url="", extra_context=None):
        obj = self.get_object(request, object_id)
        if obj:
            novos = obj.preparar_respostas()   # inclui critérios cadastrados depois
            if novos:
                messages.info(request, f"{novos} critério(s) novo(s) incluído(s) nesta vistoria.")
        return super().change_view(request, object_id, form_url, extra_context)

    def response_add(self, request, obj, post_url_continue=None):
        messages.success(request, "Vistoria criada. Comece pela Etapa 1: percorra os locais e registre os problemas.")
        return HttpResponseRedirect(reverse("vistoria_locais", args=[obj.pk]))

    # ---------- colunas da lista ----------
    def get_queryset(self, request):
        return super().get_queryset(request).select_related("escola", "responsavel").prefetch_related("respostas")

    def _cont(self, obj):
        if not hasattr(obj, "_contagem"):
            obj._contagem = {"S": 0, "N": 0, "NA": 0, "": 0}
            for r in obj.respostas.all():
                obj._contagem[r.resposta] = obj._contagem.get(r.resposta, 0) + 1
        return obj._contagem

    @admin.display(description="Respondidos")
    def progresso(self, obj):
        c = self._cont(obj)
        total = sum(c.values())
        return f"{total - c['']}/{total}"

    @admin.display(description="S")
    def qtd_sim(self, obj):
        return self._cont(obj)["S"]

    @admin.display(description="N")
    def qtd_nao(self, obj):
        return self._cont(obj)["N"]

    @admin.display(description="NA")
    def qtd_na(self, obj):
        return self._cont(obj)["NA"]

    @admin.display(description="Fotos")
    def qtd_fotos(self, obj):
        return sum(1 for r in obj.respostas.all() if r.foto)

    @admin.display(description="% atende")
    def atendimento(self, obj):
        c = self._cont(obj)
        aplicaveis = c["S"] + c["N"]
        return f"{100 * c['S'] / aplicaveis:.0f}%" if aplicaveis else "—"


@admin.register(TipoLocal)
class TipoLocalAdmin(admin.ModelAdmin):
    list_display = ("nome", "qtd_locais")
    search_fields = ("nome",)

    @admin.display(description="Locais")
    def qtd_locais(self, obj):
        return obj.locais.count()


@admin.register(Local)
class LocalAdmin(admin.ModelAdmin):
    list_display = ("miniatura", "nome", "escola", "tipo_local", "ambiente", "coberto", "area_molhada")
    list_display_links = ("miniatura", "nome")
    list_filter = ("tipo_local", "ambiente", "coberto", "area_molhada", "escola")
    search_fields = ("nome", "escola__nome", "tipo_local__nome")
    list_select_related = ("escola", "tipo_local")
    autocomplete_fields = ("escola",)
    fields = ("escola", ("tipo_local", "nome"), ("ambiente", "coberto", "area_molhada"), ("foto", "previa_foto"))
    readonly_fields = ("previa_foto",)

    @admin.display(description="Foto")
    def miniatura(self, obj):
        if obj.foto:
            return format_html(
                '<img src="{}" style="width:64px;height:44px;object-fit:cover;border-radius:3px;">',
                obj.foto.url,
            )
        return "—"

    @admin.display(description="Prévia")
    def previa_foto(self, obj):
        if obj.foto:
            return format_html(
                '<img src="{}" style="max-width:320px;max-height:220px;border-radius:4px;">',
                obj.foto.url,
            )
        return "Nenhuma foto enviada."


# ================= PROBLEMAS E CAUSAS =================

class CausaInline(admin.TabularInline):
    model = Causa
    extra = 1
    fields = ("numero", "descricao", "codigo_catalogo", "avaliacao_especializada", "observacao")
    formfield_overrides = {
        models.TextField: {"widget": forms.Textarea(attrs={"rows": 2, "cols": 36})},
    }


@admin.register(Problema)
class ProblemaAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nome", "qtd_causas")
    search_fields = ("codigo", "nome", "causas__descricao")
    inlines = [CausaInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_qtd=Count("causas"))

    @admin.display(description="Causas", ordering="_qtd")
    def qtd_causas(self, obj):
        return obj._qtd


class SolucaoInlineForm(forms.ModelForm):
    """Solução com escolha múltipla de reparos direto na tela da causa.
    "Vão juntos (+)" marcado (padrão): todos os reparos da solução são feitos juntos (A + B).
    Desmarcado: são alternativas (A ou B). Combinações como (A ou B) + C, em "Modificar"."""

    reparos = forms.ModelMultipleChoiceField(
        label="Reparos",
        queryset=Reparo.objects.select_related("unidade"),
        required=False,
        widget=AutocompleteSelectMultiple(ItemSolucao._meta.get_field("reparo"), admin.site,
                                          attrs={"style": "width: 30em"}),
    )

    juntos = forms.BooleanField(
        label="Vão juntos (+)", required=False, initial=True,
        help_text="Marque quando TODOS os reparos escolhidos devem ser feitos juntos (A + B). "
                  "Desmarcado = alternativas (A ou B).",
    )

    class Meta:
        model = Solucao
        fields = ("tipo", "condicao", "ordem")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._juntos_antes = False
        if self.instance.pk:
            self.fields["reparos"].initial = list(self.instance.itens.values_list("reparo_id", flat=True))
            grupos = self.instance.grupos()
            # "juntos" = mais de um grupo e cada grupo com um só reparo (A + B + C)
            self._juntos_antes = len(grupos) > 1 and all(len(g) == 1 for g in grupos.values())
            self.fields["juntos"].initial = self._juntos_antes

    def _sincronizar_itens(self, solucao):
        escolhidos = {r.pk for r in self.cleaned_data.get("reparos", [])}
        atuais = {i.reparo_id: i for i in solucao.itens.all()}
        # remove os que foram tirados da lista (mantém grupo/rótulo dos que ficaram)
        for reparo_id, item in atuais.items():
            if reparo_id not in escolhidos:
                item.delete()
        # acrescenta os novos no grupo 1
        ItemSolucao.objects.bulk_create(
            ItemSolucao(solucao=solucao, reparo_id=pk, grupo=1)
            for pk in escolhidos - atuais.keys()
        )
        juntos = self.cleaned_data.get("juntos")
        itens = list(solucao.itens.order_by("grupo", "pk"))
        if juntos:
            # A + B + C: cada reparo no seu próprio grupo
            for n, item in enumerate(itens, start=1):
                if item.grupo != n:
                    item.grupo = n
                    item.save(update_fields=["grupo"])
        elif self._juntos_antes:
            # desmarcou "juntos": todos viram alternativas (A ou B)
            ItemSolucao.objects.filter(solucao=solucao).update(grupo=1)
        # desmarcado e já não era "juntos": mantém os grupos (combinações feitas em "Modificar")

    def save(self, commit=True):
        solucao = super().save(commit=commit)
        if commit:
            self._sincronizar_itens(solucao)
        else:
            salvar_m2m = self.save_m2m

            def save_m2m():
                salvar_m2m()
                self._sincronizar_itens(solucao)
            self.save_m2m = save_m2m
        return solucao


class SolucaoInline(admin.TabularInline):
    model = Solucao
    form = SolucaoInlineForm
    extra = 1
    fields = ("tipo", "condicao", "ordem", "reparos", "juntos", "resumo_itens")
    readonly_fields = ("resumo_itens",)
    show_change_link = True   # abre a solução para ajustar grupos e rótulos
    verbose_name_plural = "Soluções — escolha os reparos; marque “Vão juntos (+)” quando forem feitos juntos"

    @admin.display(description="Como fica")
    def resumo_itens(self, obj):
        return obj.resumo if obj.pk else ""


def _quadro_solucoes(solucoes):
    """Quadro de leitura: tipo / condição / grupos com as opções."""
    blocos = []
    for sol in solucoes:
        grupos = sol.grupos()
        if not grupos:
            continue
        partes = []
        for n, itens in grupos.items():
            opcoes = format_html_join(
                mark_safe(" <b>ou</b> "), "{}",
                ((format_html("{} <small style='color:#666'>({})</small>",
                              i.rotulo or i.reparo.nome, i.reparo.codigo or i.reparo.unidade.sigla),)
                 for i in itens),
            )
            partes.append(format_html("<span style='white-space:nowrap'>[{}]</span>", opcoes))
        juntos = format_html_join(mark_safe(" <b>+</b> "), "{}", ((p,) for p in partes))
        blocos.append(format_html(
            "<tr><td><b>{}</b></td><td>{}</td><td>{}</td></tr>",
            sol.get_tipo_display(), sol.condicao or "—", juntos,
        ))
    if not blocos:
        return ""
    return format_html(
        "<table><tr><th>Tipo</th><th>Condição</th><th>Opções (dentro de [ ] escolhe-se uma; + = vão juntos)</th></tr>{}</table>",
        format_html_join("", "{}", ((b,) for b in blocos)),
    )


@admin.register(Causa)
class CausaAdmin(admin.ModelAdmin):
    list_display = ("relacao", "problema", "descricao", "codigo_catalogo", "avaliacao_especializada", "tem_observacao")
    list_display_links = ("relacao", "descricao")
    list_filter = ("avaliacao_especializada", "problema")
    search_fields = ("descricao", "codigo_catalogo", "problema__codigo", "problema__nome", "observacao")
    list_select_related = ("problema",)
    fields = (("problema", "numero"), "descricao", ("codigo_catalogo", "avaliacao_especializada"), "observacao",
              "solucoes_resumo")
    readonly_fields = ("solucoes_resumo",)
    inlines = [SolucaoInline]

    @admin.display(description="Reparos desta causa")
    def solucoes_resumo(self, obj):
        if not obj.pk:
            return "Salve a causa para cadastrar as soluções."
        return _quadro_solucoes(obj.solucoes.all()) or "Nenhuma solução cadastrada ainda."

    @admin.display(description="Relação", ordering="problema__codigo")
    def relacao(self, obj):
        return obj.codigo

    @admin.display(description="Obs.", boolean=True)
    def tem_observacao(self, obj):
        return bool(obj.observacao)


class ItemSolucaoInline(admin.TabularInline):
    model = ItemSolucao
    extra = 3
    autocomplete_fields = ("reparo",)
    fields = ("grupo", "rotulo", "reparo", "unidade_reparo", "custo_reparo")
    readonly_fields = ("unidade_reparo", "custo_reparo")
    verbose_name_plural = "Reparos da solução — mesmo grupo = alternativas (escolhe-se uma); grupos diferentes = vão juntos (+)"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("reparo__unidade")

    @admin.display(description="Unid.")
    def unidade_reparo(self, obj):
        return obj.reparo.unidade.sigla if obj.pk else ""

    @admin.display(description="Custo unit.")
    def custo_reparo(self, obj):
        return _brl(obj.reparo.custo_unitario) if obj.pk else ""


@admin.register(Solucao)
class SolucaoAdmin(admin.ModelAdmin):
    list_display = ("causa", "tipo", "condicao", "resumo_itens")
    list_filter = ("tipo", "causa__problema")
    search_fields = ("condicao", "causa__descricao", "causa__problema__codigo",
                     "itens__reparo__codigo", "itens__reparo__nome", "itens__rotulo")
    list_select_related = ("causa__problema",)
    autocomplete_fields = ("causa",)
    fields = ("causa", ("tipo", "ordem"), "condicao", "regra")
    readonly_fields = ("regra",)
    inlines = [ItemSolucaoInline]

    @admin.display(description="Reparos")
    def resumo_itens(self, obj):
        return obj.resumo

    @admin.display(description="Como fica a escolha")
    def regra(self, obj):
        if not obj.pk:
            return "Salve para ver o resumo."
        return _quadro_solucoes([obj]) or "Nenhum reparo cadastrado ainda."


class OcorrenciaReparoInline(admin.TabularInline):
    model = OcorrenciaReparo
    extra = 0
    autocomplete_fields = ("reparo",)
    fields = ("reparo", "quantidade")


@admin.register(Ocorrencia)
class OcorrenciaAdmin(admin.ModelAdmin):
    list_display = ("vistoria", "local", "problema", "custo_fmt")
    list_filter = ("problema", "vistoria__escola")
    search_fields = ("local__nome", "problema__nome", "problema__codigo", "vistoria__escola__nome")
    list_select_related = ("vistoria__escola", "local", "problema")
    autocomplete_fields = ("vistoria", "problema")
    filter_horizontal = ("causas",)
    inlines = [OcorrenciaReparoInline]

    @admin.display(description="Custo")
    def custo_fmt(self, obj):
        return _brl(obj.custo)

import re
from decimal import Decimal, ROUND_HALF_UP

from django import forms
from django.contrib import admin
from django.db.models import Count
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html, format_html_join

from .models import (
    Atividade, Categoria, Criterio, Escola, Reparo, RespostaVistoria, Unidade, Vistoria,
)



def _nome_usuario(usuario):
    """Nome completo do usuário; se não tiver nome cadastrado, usa o login."""
    return usuario.get_full_name() or usuario.username


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


@admin.register(Escola)
class EscolaAdmin(admin.ModelAdmin):
    form = EscolaAdminForm
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


@admin.register(Reparo)
class ReparoAdmin(admin.ModelAdmin):
    list_display = ("nome", "unidade", "qtd_atividades", "custo_unitario_fmt", "resumo")
    list_filter = ("unidade",)
    search_fields = ("nome", "descricao")
    list_select_related = ("unidade",)
    fields = ("nome", "unidade", "descricao", "atividades", "custo_calculado")
    readonly_fields = ("custo_calculado",)
    filter_horizontal = ("atividades",)

    @admin.display(description="Custo unitário")
    def custo_unitario_fmt(self, obj):
        return f"{_brl(obj.custo_unitario)} / {obj.unidade.sigla}"

    @admin.display(description="Custo calculado")
    def custo_calculado(self, obj):
        if not obj.pk:
            return "Salve o reparo para calcular o custo."
        atividades = list(obj.atividades.select_related("unidade"))
        if not atividades:
            return "Nenhuma atividade escolhida."
        linhas = format_html_join(
            "", "<tr><td>{}</td><td style='text-align:right'>{}</td></tr>",
            ((str(a), _brl(a.custo) if a.custo is not None else "sem custo") for a in atividades),
        )
        sem_custo = sum(1 for a in atividades if a.custo is None)
        aviso = format_html(
            "<p style='color:#b23a3a;margin:6px 0 0'>{} atividade(s) sem custo, contadas como R$ 0,00.</p>", sem_custo,
        ) if sem_custo else ""
        return format_html(
            "<table style='min-width:420px'>{}<tr><th>Total por {}</th>"
            "<th style='text-align:right'>{}</th></tr></table>{}",
            linhas, obj.unidade.sigla, _brl(obj.custo_unitario), aviso,
        )

    @admin.display(description="Atividades")
    def qtd_atividades(self, obj):
        return obj.atividades.count()

    @admin.display(description="Descrição")
    def resumo(self, obj):
        texto = obj.descricao
        return texto if len(texto) <= 90 else texto[:90] + "…"


@admin.register(Atividade)
class AtividadeAdmin(admin.ModelAdmin):
    list_display = ("nome", "cod_sicro", "unidade", "custo_formatado")
    list_display_links = ("nome",)
    list_filter = ("unidade",)
    search_fields = ("nome", "cod_sicro", "descricao")
    list_select_related = ("unidade",)
    fields = ("nome", ("cod_sicro", "unidade"), "custo", "descricao")

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


class ReparoSelect(forms.Select):
    """Lista de reparos que guarda a sigla da unidade de cada opção (data-sigla)."""

    def __init__(self, *args, siglas=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.siglas = siglas or {}

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        opcao = super().create_option(name, value, label, selected, index, subindex, attrs)
        pk = getattr(value, "value", value)
        if pk in self.siglas:
            opcao["attrs"]["data-sigla"] = self.siglas[pk]
        return opcao


class RespostaForm(forms.ModelForm):
    resposta = forms.ChoiceField(
        label="Resposta",
        choices=RespostaVistoria.Resposta.choices,
        widget=forms.RadioSelect(attrs={"class": "radio-sna"}),
        required=False,
    )

    class Meta:
        model = RespostaVistoria
        fields = ("resposta", "reparo", "valor", "observacao", "foto")
        widgets = {
            "observacao": forms.TextInput(attrs={"size": 20, "placeholder": "Observação (opcional)"}),
            "foto": FotoInput(),
            "valor": forms.NumberInput(attrs={"step": "0.01", "min": "0", "class": "valor-input", "placeholder": "0,00"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        criterio = self.instance.criterio if self.instance.criterio_id else None
        reparos = criterio.reparos.select_related("unidade") if criterio else Reparo.objects.none()
        campo = self.fields["reparo"]
        campo.queryset = reparos
        campo.label_from_instance = lambda r: r.nome
        campo.widget = ReparoSelect(
            siglas={r.pk: r.unidade.sigla for r in reparos},
            attrs={"class": "reparo-select"},
        )
        campo.widget.choices = campo.choices
        if reparos:
            campo.empty_label = "— escolha o reparo —"
        else:
            campo.empty_label = "nenhum reparo cadastrado"
            campo.disabled = True
            self.fields["valor"].disabled = True


class RespostaInline(admin.TabularInline):
    model = RespostaVistoria
    form = RespostaForm
    fields = ("categoria", "criterio_nome", "o_que_verificar", "resposta", "reparo", "valor", "custo_linha", "observacao", "foto")
    readonly_fields = ("categoria", "criterio_nome", "o_que_verificar", "custo_linha")
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
                .select_related("criterio__categoria", "reparo__unidade")
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

    @admin.display(description="Custo")
    def custo_linha(self, obj):
        custo = obj.custo
        return _brl(custo) if custo else ""


@admin.register(Vistoria)
class VistoriaAdmin(admin.ModelAdmin):
    list_display = ("escola", "data", "responsavel_nome", "progresso", "qtd_sim", "qtd_nao", "qtd_na", "qtd_fotos", "atendimento", "custo_total_fmt")
    list_filter = ("data", "escola")
    search_fields = ("escola__nome", "escola__codigo_inep")
    date_hierarchy = "data"
    autocomplete_fields = ("escola",)
    fields = ("escola", ("data", "responsavel"), "observacoes", "orcamento")
    readonly_fields = ("orcamento",)

    @admin.display(description="Custo total")
    def custo_total_fmt(self, obj):
        return _brl(obj.custo_total)

    @admin.display(description="Orçamento estimado")
    def orcamento(self, obj):
        if not obj.pk:
            return "Salve a vistoria para calcular o orçamento."
        itens = obj.itens_orcamento()
        if not itens:
            return "Nenhuma resposta N com reparo e valor ainda."
        linhas = format_html_join(
            "",
            "<tr><td>{}</td><td>{}</td><td>{}</td><td style='text-align:right'>{} {}</td>"
            "<td style='text-align:right'>{}</td><td style='text-align:right'><b>{}</b></td></tr>",
            (
                (i.criterio.categoria.nome, i.criterio.nome, i.reparo.nome,
                 f"{i.valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), i.reparo.unidade.sigla,
                 _brl(i.custo_unit), _brl(i.custo_calc))
                for i in itens
            ),
        )
        total = sum((i.custo_calc for i in itens), 0)
        return format_html(
            "<table class='orcamento-vistoria'><thead><tr><th>Categoria</th><th>Critério</th><th>Reparo</th>"
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
        messages.success(request, "Vistoria criada. Agora marque S, N ou NA em cada critério.")
        return HttpResponseRedirect(reverse("admin:sge_vistoria_change", args=[obj.pk]))

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
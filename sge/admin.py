import re
from decimal import Decimal, ROUND_HALF_UP

from django import forms
from django.contrib import admin
from django.utils.html import format_html

from .models import Escola, Categoria, Unidade, Criterio, Reparo, Atividade


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
            "fields": ("nome", "codigo_inep", ("foto", "previa_foto")),
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
    list_display = ("nome","qtd_criterios")
    search_fields = ("nome",)
    inlines = [CriterioInline]
 
    @admin.display(description="QTD Critérios")
    def qtd_criterios(self, obj):
        return obj.criterios.count()
    

@admin.register(Unidade)
class UnidadeAdmin(admin.ModelAdmin):
    list_display = ("nome", "sigla")
    search_fields = ("nome", "sigla")


@admin.register(Criterio)
class CriterioAdmin(admin.ModelAdmin):
    list_display = ("nome", "categoria", "resumo")
    list_filter = ("categoria",)
    search_fields = ("nome", "o_que_verificar", "categoria__nome")
    list_select_related = ("categoria",)
    fields = ("categoria", "nome", "o_que_verificar")
 
    @admin.display(description="O que verificar")
    def resumo(self, obj):
        texto = obj.o_que_verificar
        return texto if len(texto) <= 90 else texto[:90] + "…"



@admin.register(Reparo)
class ReparoAdmin(admin.ModelAdmin):
    list_display = ("nome", "unidade", "qtd_atividades", "resumo")
    list_filter = ("unidade",)
    search_fields = ("nome", "descricao")
    list_select_related = ("unidade",)
    fields = ("nome", "unidade", "descricao", "atividades")
    filter_horizontal = ("atividades",)
 
    @admin.display(description="Atividades")
    def qtd_atividades(self, obj):
        return obj.atividades.count()
 
    @admin.display(description="Descrição")
    def resumo(self, obj):
        texto = obj.descricao
        return texto if len(texto) <= 90 else texto[:90] + "…"
 

 
@admin.register(Atividade)
class AtividadeAdmin(admin.ModelAdmin):
    list_display = ("nome", "cod_sicro", "unidade")
    list_display_links = ("nome",)
    list_filter = ("unidade",)
    search_fields = ("nome", "cod_sicro", "descricao")
    list_select_related = ("unidade",)
    fields = ("nome", ("cod_sicro", "unidade"), "descricao")
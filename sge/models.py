from django.core.validators import MaxValueValidator, MinValueValidator
from django.conf import settings
from django.core.exceptions import ValidationError
from decimal import Decimal
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Sum
from django.utils import timezone

class Categoria(models.Model):
    nome = models.CharField(max_length=100, unique=True)
 
    class Meta:
        verbose_name = "categoria"
        verbose_name_plural = "categorias"
        ordering = ["nome"]
 
    def __str__(self):
        return self.nome

class Criterio(models.Model):
    categoria = models.ForeignKey(
        Categoria, on_delete=models.PROTECT, related_name="criterios",
    )
    nome = models.CharField(max_length=150)
    o_que_verificar = models.TextField("o que verificar")
    reparos = models.ManyToManyField(
        "Reparo", related_name="criterios", blank=True,
        help_text="Reparos possíveis quando o critério não é atendido.",
    )
    class Meta:
        verbose_name = "critério"
        verbose_name_plural = "critérios"
        ordering = ["categoria__nome", "nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["categoria", "nome"], name="criterio_unico_por_categoria",
            ),
        ]

    def __str__(self):
        return f"{self.categoria} – {self.nome}"
    
class Unidade(models.Model):
    nome = models.CharField(max_length=50, unique=True)
    sigla = models.CharField(max_length=10, unique=True)

    class Meta:
        verbose_name = "unidade"
        verbose_name_plural = "unidades"
        ordering = ["nome"]

    def __str__(self):
        return f"{self.nome} ({self.sigla})"

class Atividade(models.Model):
    cod_sicro = models.CharField("código SINAP", max_length=20, blank=True)
    nome = models.CharField(max_length=200)
    descricao = models.TextField("descrição", blank=True)
    unidade = models.ForeignKey(
        Unidade, on_delete=models.PROTECT, related_name="atividades",
        verbose_name="unidade de medida", blank=True, null=True,
    )
    custo = models.DecimalField(
        "custo (R$)", max_digits=12, decimal_places=2, blank=True, null=True,
        validators=[MinValueValidator(0)],
        help_text="Custo unitário, por unidade de medida.(CAMPO DEMOSTRATIVO LIGAÇÃO FUTURA PELO CODIGO SINAP)",
    )
    class Meta:
        verbose_name = "atividade"
        verbose_name_plural = "atividades"
        ordering = ["nome"]

    def __str__(self):
        if self.cod_sicro:
            return f"{self.cod_sicro} – {self.nome}"
        return self.nome
    
class Reparo(models.Model):
    nome = models.CharField(max_length=150, unique=True)
    descricao = models.TextField("descrição", blank=True)
    unidade = models.ForeignKey(
        Unidade, on_delete=models.PROTECT, related_name="reparos",
    )
    atividades = models.ManyToManyField(
        "Atividade", related_name="reparos", blank=True,
        help_text="Atividades (serviços) que compõem este reparo.",
    )
    class Meta:
        verbose_name = "reparo"
        verbose_name_plural = "reparos"
        ordering = ["nome"]
 
    def __str__(self):
        return f"{self.nome} ({self.unidade.sigla})"

    @property
    def custo_unitario(self):
        """Soma do custo de todas as atividades do reparo (R$ por unidade do reparo).
        Atividades sem custo cadastrado contam como zero."""
        total = self.atividades.aggregate(total=Sum("custo"))["total"] or 0
        return Decimal(str(total)).quantize(Decimal("0.01"))

    def calcular_custo(self, quantidade):
        """Custo do reparo para uma quantidade (na unidade do reparo).
        Ex.: reparo.calcular_custo(12.5) -> custo de 12,5 m²."""
        if quantidade in (None, ""):
            return Decimal("0.00")
        return (self.custo_unitario * Decimal(str(quantidade))).quantize(Decimal("0.01"))
    
class Escola(models.Model):

    class SistemaConstrutivo(models.TextChoices):
        ALVENARIA = "alvenaria", "Alvenaria (bloco)"
        PRE_MOLDADO = "pre_moldado", "Pré-moldado"
        MADEIRA = "madeira", "Madeira"
        MISTO = "misto", "Misto"

    # ---------- identificação ----------
    nome = models.CharField("nome da escola", max_length=200)
    codigo_inep = models.CharField(
        "código INEP", max_length=8, unique=True,
        help_text="8 dígitos, conforme o Censo Escolar.",
    )
    foto = models.ImageField(
        "foto da escola", upload_to="escolas/fotos/", blank=True, null=True,
    )

    # ---------- localização ----------
    endereco = models.CharField("endereço completo", max_length=255)
    bairro = models.CharField(max_length=100, blank=True)
    municipio = models.CharField("município", max_length=100)
    uf = models.CharField("UF", max_length=2, default="PR")
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, blank=True, null=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
        help_text="Ex.: -25.500000",
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, blank=True, null=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
        help_text="Ex.: -49.400000",
    )

    # ---------- etapas de ensino ----------
    educacao_infantil = models.BooleanField("educação infantil", default=False)
    fundamental_1 = models.BooleanField("fundamental I", default=False)
    fundamental_2 = models.BooleanField("fundamental II", default=False)
    eja = models.BooleanField("EJA", default=False)

    # ---------- turnos ----------
    turno_manha = models.BooleanField("manhã", default=False)
    turno_tarde = models.BooleanField("tarde", default=False)
    turno_noite = models.BooleanField("noite", default=False)
    turno_integral = models.BooleanField("integral", default=False)

    # ---------- comunidade escolar ----------
    alunos_matriculados = models.PositiveIntegerField("nº de alunos matriculados", default=0)
    alunos_com_deficiencia = models.PositiveIntegerField("nº de alunos com deficiência", default=0)
    detalhe_deficiencia = models.CharField(
        "detalhamento das deficiências", max_length=255, blank=True,
        help_text="Ex.: 3 cadeirantes, 2 baixa visão, 4 TEA",
    )
    funcionarios = models.PositiveIntegerField("nº de funcionários", default=0)

    # ---------- edificação ----------
    area_terreno = models.DecimalField("área do terreno (m²)", max_digits=10, decimal_places=2, blank=True, null=True)
    area_construida = models.DecimalField("área construída (m²)", max_digits=10, decimal_places=2, blank=True, null=True)
    pavimentos = models.PositiveSmallIntegerField("nº de pavimentos", default=1)
    pavimentos_obs = models.CharField(
        "observação sobre pavimentos", max_length=255, blank=True,
        help_text="Ex.: 2 (bloco de salas de aula); demais blocos térreos",
    )
    ano_construcao = models.PositiveSmallIntegerField(
        "ano de construção", blank=True, null=True,
        validators=[MinValueValidator(1800), MaxValueValidator(2100)],
    )
    ultima_reforma_ano = models.PositiveSmallIntegerField(
        "ano da última reforma", blank=True, null=True,
        validators=[MinValueValidator(1800), MaxValueValidator(2100)],
    )
    ultima_reforma_escopo = models.CharField(
        "escopo da última reforma", max_length=255, blank=True,
        help_text="Deixe em branco se não houver reforma geral registrada.",
    )
    sistema_construtivo = models.CharField(
        max_length=20, choices=SistemaConstrutivo.choices, default=SistemaConstrutivo.ALVENARIA,
    )

    relatorio = models.FileField(
        "relatório", upload_to="escolas/relatorios/", blank=True, null=True,
        validators=[FileExtensionValidator(["pdf", "doc", "docx"])],
        help_text="PDF ou Word. Quando houver arquivo, o botão de download aparece na pesquisa de escolas.",
    )   
    # ---------- contato ----------
    diretor = models.CharField("diretor(a)", max_length=150, blank=True)
    telefone = models.CharField(max_length=20, blank=True)
    email = models.EmailField("e-mail", blank=True)

    # ---------- controle ----------
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "escola"
        verbose_name_plural = "escolas"
        ordering = ["nome"]

    def __str__(self):
        return f"{self.nome} ({self.codigo_inep})"

    @property
    def etapas_texto(self):
        etapas = [
            (self.educacao_infantil, "Educação infantil"),
            (self.fundamental_1, "Fundamental I"),
            (self.fundamental_2, "Fundamental II"),
            (self.eja, "EJA"),
        ]
        return ", ".join(nome for marcado, nome in etapas if marcado) or "—"

    @property
    def turnos_texto(self):
        turnos = [
            (self.turno_manha, "Manhã"),
            (self.turno_tarde, "Tarde"),
            (self.turno_noite, "Noite"),
            (self.turno_integral, "Integral"),
        ]
        return ", ".join(nome for marcado, nome in turnos if marcado) or "—"


class Vistoria(models.Model):
    escola = models.ForeignKey(
        Escola, on_delete=models.PROTECT, related_name="vistorias",
    )
    data = models.DateField(default=timezone.localdate)
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="vistorias",
        verbose_name="Eng. Responsável",
        help_text="Se ficar em branco, será o usuário que salvou.",
    )
    observacoes = models.TextField("observações", blank=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)
 
    class Meta:
        verbose_name = "vistoria"
        verbose_name_plural = "vistorias"
        ordering = ["-data", "escola__nome"]
 
    def __str__(self):
        return f"{self.escola.nome} – {self.data:%d/%m/%Y}"
 
    def preparar_respostas(self):
        """Cria uma resposta (em branco) para cada critério que ainda não está na vistoria."""
        existentes = set(self.respostas.values_list("criterio_id", flat=True))
        novas = [
            RespostaVistoria(vistoria=self, criterio=c)
            for c in Criterio.objects.exclude(pk__in=existentes)
        ]
        RespostaVistoria.objects.bulk_create(novas)
        return len(novas)
 
    def itens_orcamento(self):
        """Respostas N com reparo e valor, cada uma com o custo calculado (atributo .custo_calc)."""
        itens = list(
            self.respostas.filter(resposta="N", reparo__isnull=False, valor__isnull=False)
            .select_related("criterio__categoria", "reparo__unidade")
        )
        # custo unitário de todos os reparos usados, numa consulta só
        unitarios = dict(
            Reparo.objects.filter(pk__in={i.reparo_id for i in itens})
            .annotate(total=Sum("atividades__custo"))
            .values_list("pk", "total")
        )
        centavos = Decimal("0.01")
        for i in itens:
            i.custo_unit = Decimal(str(unitarios.get(i.reparo_id) or 0)).quantize(centavos)
            i.custo_calc = (i.custo_unit * i.valor).quantize(centavos)
        return itens
 
    @property
    def custo_total(self):
        """Soma de reparo × valor de todas as respostas N da vistoria (R$)."""
        return sum((i.custo_calc for i in self.itens_orcamento()), Decimal("0.00"))
 
    def contagem(self):
        """Quantidade de respostas S, N, NA e em branco."""
        total = {"S": 0, "N": 0, "NA": 0, "": 0}
        for r in self.respostas.values_list("resposta", flat=True):
            total[r] = total.get(r, 0) + 1
        return total
 
 
class RespostaVistoria(models.Model):
 
    class Resposta(models.TextChoices):
        SIM = "S", "S"
        NAO = "N", "N"
        NAO_SE_APLICA = "NA", "NA"
 
    vistoria = models.ForeignKey(
        Vistoria, on_delete=models.CASCADE, related_name="respostas",
    )
    criterio = models.ForeignKey(
        Criterio, on_delete=models.PROTECT, related_name="respostas",
        verbose_name="critério",
    )
    resposta = models.CharField(max_length=2, choices=Resposta.choices, blank=True)
 
    # preenchidos só quando a resposta é N (não atende)
    reparo = models.ForeignKey(
        Reparo, on_delete=models.PROTECT, related_name="respostas",
        null=True, blank=True,
        help_text="Reparo necessário (só aparecem os reparos do critério).",
    )
    valor = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0)],
        help_text="Quantidade na unidade de medida do reparo.",
    )
 
    observacao = models.CharField("observação", max_length=255, blank=True)
    foto = models.ImageField(
        "foto", upload_to="vistorias/fotos/%Y/%m/", blank=True, null=True,
    )
 
    class Meta:
        verbose_name = "resposta"
        verbose_name_plural = "respostas"
        # ordem de cadastro dos critérios = ordem da ficha de campo
        ordering = ["criterio_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["vistoria", "criterio"], name="resposta_unica_por_criterio",
            ),
        ]
 
    def __str__(self):
        return f"{self.criterio.nome}: {self.resposta or '—'}"
 
    @property
    def unidade_sigla(self):
        return self.reparo.unidade.sigla if self.reparo_id else ""
 
    @property
    def custo(self):
        """Custo desta resposta: reparo × valor (R$). Zero se não for N ou faltar dado."""
        if self.resposta != self.Resposta.NAO or not self.reparo_id or self.valor is None:
            return Decimal("0.00")
        return self.reparo.calcular_custo(self.valor)
 
    def clean(self):
        # reparo e valor só fazem sentido quando o critério não é atendido
        if self.resposta != self.Resposta.NAO:
            self.reparo = None
            self.valor = None
            return
        erros = {}
        if self.reparo_id and not self.criterio.reparos.filter(pk=self.reparo_id).exists():
            erros["reparo"] = "Esse reparo não pertence ao critério."
        if self.reparo_id and self.valor is None:
            erros["valor"] = f"Informe o valor em {self.reparo.unidade.sigla}."
        if self.valor is not None and not self.reparo_id:
            erros["reparo"] = "Escolha o reparo correspondente ao valor."
        if erros:
            raise ValidationError(erros)
 
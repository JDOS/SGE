from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

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



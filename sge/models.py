from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.conf import settings
from django.core.exceptions import ValidationError
from decimal import Decimal

from django.db import models
from django.db.models import Sum
from django.db.models.functions import Lower
from django.utils import timezone


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
    relatorio = models.FileField(
        "relatório", upload_to="escolas/relatorios/", blank=True, null=True,
        validators=[FileExtensionValidator(["pdf", "doc", "docx"])],
        help_text="PDF ou Word. Quando houver arquivo, o botão de download aparece na pesquisa de escolas.",
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



class Categoria(models.Model):
    nome = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name = "categoria"
        verbose_name_plural = "categorias"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Unidade(models.Model):
    nome = models.CharField(max_length=50, unique=True)
    sigla = models.CharField(max_length=10, unique=True)

    class Meta:
        verbose_name = "unidade"
        verbose_name_plural = "unidades"
        ordering = ["nome"]

    def __str__(self):
        return f"{self.nome} ({self.sigla})"


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


class Reparo(models.Model):
    codigo = models.CharField(
        "código", max_length=20, blank=True,
        help_text="Código da macrocomposição. Ex.: 100111",
    )
    nome = models.CharField(max_length=255, unique=True)
    descricao = models.TextField("descrição", blank=True)
    unidade = models.ForeignKey(
        Unidade, on_delete=models.PROTECT, related_name="reparos",
    )
    atividades = models.ManyToManyField(
        "Atividade", related_name="reparos", blank=True,
        through="ReparoAtividade",
        verbose_name="bases de referência",
        help_text="Itens da base de referência (SINAPI, SINAPI-I ou cotação) que compõem este reparo.",
    )

    class Meta:
        verbose_name = "reparo"
        verbose_name_plural = "reparos"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["codigo"], condition=~models.Q(codigo=""),
                name="reparo_codigo_unico",
                violation_error_message="Já existe um reparo com esse código.",
            ),
        ]

    def __str__(self):
        if self.codigo:
            return f"{self.codigo} – {self.nome} ({self.unidade.sigla})"
        return f"{self.nome} ({self.unidade.sigla})"

    @property
    def custo_unitario(self):
        """Custo por unidade do reparo: soma de (custo da atividade × coeficiente).
        Atividades sem custo cadastrado contam como zero."""
        itens = self.composicao.values_list("atividade__custo", "coeficiente")
        return _somar_composicao(itens)

    def calcular_custo(self, quantidade):
        """Custo do reparo para uma quantidade (na unidade do reparo).
        Ex.: reparo.calcular_custo(12.5) -> custo de 12,5 m²."""
        if quantidade in (None, ""):
            return Decimal("0.00")
        return (self.custo_unitario * Decimal(str(quantidade))).quantize(Decimal("0.01"))


def _somar_composicao(itens):
    """Soma (custo × coeficiente) de uma lista de pares e arredonda em centavos."""
    total = sum(
        (Decimal(str(custo or 0)) * Decimal(str(coef if coef is not None else 1)) for custo, coef in itens),
        Decimal("0"),
    )
    return total.quantize(Decimal("0.01"))


def custos_unitarios(reparo_ids):
    """{reparo_id: custo unitário} de vários reparos numa consulta só."""
    por_reparo = {}
    for reparo_id, custo, coef in ReparoAtividade.objects.filter(
        reparo_id__in=reparo_ids
    ).values_list("reparo_id", "atividade__custo", "coeficiente"):
        por_reparo.setdefault(reparo_id, []).append((custo, coef))
    return {pk: _somar_composicao(lista) for pk, lista in por_reparo.items()}


class ReparoAtividade(models.Model):
    """Atividade (base de referência) dentro de um reparo, com o seu coeficiente."""
    reparo = models.ForeignKey(Reparo, on_delete=models.CASCADE, related_name="composicao")
    atividade = models.ForeignKey(
        "Atividade", on_delete=models.CASCADE, related_name="composicoes",
        verbose_name="base de referência",
    )
    coeficiente = models.DecimalField(
        max_digits=16, decimal_places=8, default=1,
        validators=[MinValueValidator(0)],
        help_text="Quantidade da atividade por unidade do reparo. Ex.: 0,02 m³ de argamassa por m².",
    )

    class Meta:
        db_table = "sge_reparo_atividades"   # reaproveita a tabela que já existe
        verbose_name = "item da composição"
        verbose_name_plural = "composição do reparo"
        unique_together = [("reparo", "atividade")]

    def __str__(self):
        return f"{self.atividade} × {self.coeficiente}"

    @property
    def subtotal(self):
        """Custo da atividade × coeficiente (sem arredondar)."""
        return Decimal(str(self.atividade.custo or 0)) * self.coeficiente


class Atividade(models.Model):

    class Fonte(models.TextChoices):
        SINAPI = "sinapi", "SINAPI"
        SINAPI_I = "sinapi_i", "SINAPI-I"
        COTACAO = "cotacao", "Cotação"

    codigo = models.CharField("código", max_length=20, blank=True)
    fonte = models.CharField(max_length=10, choices=Fonte.choices, default=Fonte.SINAPI)
    descricao = models.TextField("descrição")
    unidade = models.ForeignKey(
        Unidade, on_delete=models.PROTECT, related_name="atividades",
        verbose_name="unidade de medida", blank=True, null=True,
    )
    custo = models.DecimalField(
        "custo (R$)", max_digits=12, decimal_places=2, blank=True, null=True,
        validators=[MinValueValidator(0)],
        help_text="Custo unitário, por unidade de medida.",
    )

    class Meta:
        verbose_name = "base de referência"
        verbose_name_plural = "bases de referência"
        ordering = ["descricao"]

    def __str__(self):
        texto = self.descricao if len(self.descricao) <= 90 else self.descricao[:90] + "…"
        if self.codigo:
            return f"{self.codigo} – {texto}"
        return texto


class TipoLocal(models.Model):
    """Tipos de local que você mesmo cadastra: sala de aula, pátio, corredor, área externa..."""
    nome = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name = "tipo de local"
        verbose_name_plural = "tipos de local"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Local(models.Model):

    class Ambiente(models.TextChoices):
        INTERNO = "interno", "Interno"
        EXTERNO = "externo", "Externo"

    escola = models.ForeignKey(
        Escola, on_delete=models.CASCADE, related_name="locais",
    )
    tipo_local = models.ForeignKey(
        TipoLocal, on_delete=models.PROTECT, related_name="locais",
        verbose_name="tipo de local",
    )
    nome = models.CharField(max_length=150, help_text="Ex.: Sala 3, Pátio coberto, Banheiro feminino")
    foto = models.ImageField(upload_to="escolas/locais/", blank=True, null=True)

    # tipo do ambiente
    ambiente = models.CharField(max_length=10, choices=Ambiente.choices, default=Ambiente.INTERNO)
    coberto = models.BooleanField(default=True)
    area_molhada = models.BooleanField(
        "área molhada", default=False,
        help_text="Banheiros, cozinha, lavanderia e outros ambientes com água.",
    )

    class Meta:
        verbose_name = "local"
        verbose_name_plural = "locais"
        ordering = ["escola__nome", "tipo_local__nome", "nome"]
        constraints = [
            models.UniqueConstraint(
                Lower("nome"), "escola",
                name="local_unico_por_escola",
                violation_error_message="Esta escola já tem um local com esse nome.",
            ),
        ]

    def __str__(self):
        return f"{self.nome} ({self.tipo_local})"

    @property
    def tipo_texto(self):
        partes = [self.get_ambiente_display(), "coberto" if self.coberto else "descoberto"]
        if self.area_molhada:
            partes.append("área molhada")
        return ", ".join(partes)


class Vistoria(models.Model):
    escola = models.ForeignKey(
        Escola, on_delete=models.PROTECT, related_name="vistorias",
    )
    data = models.DateField(default=timezone.localdate)
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="vistorias",
        verbose_name="responsável",
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
        """Reparos lançados na Etapa 1 (locais e problemas), cada um com:
        .custo_unit (R$ por unidade do reparo) e .custo_calc (custo_unit × quantidade)."""
        itens = list(
            OcorrenciaReparo.objects.filter(ocorrencia__vistoria=self)
            .select_related("ocorrencia__local__tipo_local", "ocorrencia__problema", "reparo__unidade")
            .order_by("ocorrencia__local__nome", "ocorrencia_id", "pk")
        )
        unitarios = custos_unitarios({i.reparo_id for i in itens})
        centavos = Decimal("0.01")
        for i in itens:
            i.custo_unit = unitarios.get(i.reparo_id, Decimal("0.00"))
            i.custo_calc = (i.custo_unit * i.quantidade).quantize(centavos)
        return itens

    @property
    def custo_total(self):
        """Soma de todos os reparos lançados na Etapa 1 (R$)."""
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


class Problema(models.Model):
    """Problema observado na escola. Ex.: PR-01 Goteira ou infiltração pelo teto."""
    codigo = models.CharField("código", max_length=10, unique=True, help_text="Ex.: PR-01")
    nome = models.CharField(max_length=200)

    class Meta:
        verbose_name = "problema"
        verbose_name_plural = "problemas"
        ordering = ["codigo"]

    def __str__(self):
        return f"{self.codigo} {self.nome}"


class Causa(models.Model):
    """Causa provável de um problema. Ex.: PR-01.1 Telha quebrada, trincada ou deslocada."""
    problema = models.ForeignKey(
        Problema, on_delete=models.CASCADE, related_name="causas",
    )
    numero = models.PositiveSmallIntegerField(
        "nº", blank=True,
        help_text="Número da causa dentro do problema (o 1 de PR-01.1). Em branco, usa o próximo.",
    )
    descricao = models.CharField("causa", max_length=255)
    codigo_catalogo = models.CharField(
        "código no catálogo", max_length=20, blank=True, help_text="Ex.: COB-01",
    )
    avaliacao_especializada = models.BooleanField("avaliação especializada", default=False)
    observacao = models.TextField("observação", blank=True)

    class Meta:
        verbose_name = "causa"
        verbose_name_plural = "causas"
        ordering = ["problema__codigo", "numero"]
        constraints = [
            models.UniqueConstraint(
                fields=["problema", "numero"], name="causa_numero_unico_por_problema",
                violation_error_message="Este problema já tem uma causa com esse número.",
            ),
        ]

    def __str__(self):
        return f"{self.codigo} {self.descricao}"

    @property
    def codigo(self):
        """Código da relação, montado a partir do problema: PR-01.1, PR-01.2..."""
        if not self.problema_id or self.numero is None:
            return ""
        return f"{self.problema.codigo}.{self.numero}"

    def reparos_relacionados(self):
        """Todos os reparos que aparecem nas soluções desta causa."""
        return Reparo.objects.filter(itens_solucao__solucao__causa=self).distinct()

    def save(self, *args, **kwargs):
        if self.numero is None:
            ultimo = (Causa.objects.filter(problema_id=self.problema_id)
                      .aggregate(m=models.Max("numero"))["m"])
            self.numero = (ultimo or 0) + 1
        super().save(*args, **kwargs)


class Solucao(models.Model):
    """Uma forma de resolver a causa. Entre soluções do mesmo tipo, escolhe-se UMA."""

    class Tipo(models.TextChoices):
        PRINCIPAL = "principal", "Principal"
        COMPLEMENTAR = "complementar", "Complementar"

    causa = models.ForeignKey(Causa, on_delete=models.CASCADE, related_name="solucoes")
    tipo = models.CharField(max_length=12, choices=Tipo.choices, default=Tipo.PRINCIPAL)
    condicao = models.CharField(
        "condição", max_length=150, blank=True,
        help_text="Quando usar esta solução. Ex.: conforme a telha, conserto localizado, reforma, forro",
    )
    ordem = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "solução"
        verbose_name_plural = "soluções"
        ordering = ["causa__problema__codigo", "causa__numero", "-tipo", "ordem", "pk"]  # principal antes de complementar

    def __str__(self):
        texto = f"{self.causa.codigo} – {self.get_tipo_display()}"
        return f"{texto}: {self.condicao}" if self.condicao else texto

    def grupos(self):
        """Itens agrupados: {1: [item, item], 2: [item]} — mesmo grupo = alternativas (OU),
        grupos diferentes = vão juntos (+)."""
        grupos = {}
        for item in self.itens.select_related("reparo__unidade"):
            grupos.setdefault(item.grupo, []).append(item)
        return dict(sorted(grupos.items()))

    @property
    def resumo(self):
        """Texto no formato da planilha. Ex.: 400315 ou 400325 + 600312 ou 600322"""
        partes = []
        for itens in self.grupos().values():
            nomes = [i.reparo.codigo or i.reparo.nome for i in itens]
            partes.append(" ou ".join(nomes))
        return " + ".join(partes) or "—"


class ItemSolucao(models.Model):
    """Reparo dentro de uma solução. Mesmo grupo = escolhe-se um; grupos diferentes = todos."""
    solucao = models.ForeignKey(Solucao, on_delete=models.CASCADE, related_name="itens")
    grupo = models.PositiveSmallIntegerField(
        default=1,
        help_text="Mesmo número = alternativas (escolhe-se uma). Números diferentes = vão juntos (+).",
    )
    rotulo = models.CharField(
        "rótulo", max_length=100, blank=True,
        help_text="Como o usuário reconhece esta opção. Ex.: Telha cerâmica",
    )
    reparo = models.ForeignKey(Reparo, on_delete=models.PROTECT, related_name="itens_solucao")

    class Meta:
        verbose_name = "item da solução"
        verbose_name_plural = "itens da solução"
        ordering = ["grupo", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["solucao", "reparo"], name="item_solucao_reparo_unico",
                violation_error_message="Este reparo já está nesta solução.",
            ),
        ]

    def __str__(self):
        texto = self.rotulo or self.reparo.nome
        return f"grupo {self.grupo}: {texto}"


# ================= VISTORIA — ETAPA 1: LOCAIS E PROBLEMAS =================

class Ocorrencia(models.Model):
    """Problema encontrado num local da escola durante a vistoria."""
    vistoria = models.ForeignKey(Vistoria, on_delete=models.CASCADE, related_name="ocorrencias")
    local = models.ForeignKey(Local, on_delete=models.PROTECT, related_name="ocorrencias")
    problema = models.ForeignKey(Problema, on_delete=models.PROTECT, related_name="ocorrencias")
    causas = models.ManyToManyField(Causa, related_name="ocorrencias", blank=True)
    observacao = models.TextField("observação", blank=True)
    foto = models.ImageField(upload_to="vistorias/ocorrencias/%Y/%m/", blank=True, null=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "ocorrência"
        verbose_name_plural = "ocorrências"
        ordering = ["local__nome", "pk"]

    def __str__(self):
        return f"{self.local.nome} – {self.problema}"

    @property
    def custo(self):
        unitarios = custos_unitarios(set(self.itens.values_list("reparo_id", flat=True)))
        centavos = Decimal("0.01")
        return sum(
            ((unitarios.get(i.reparo_id, Decimal("0")) * i.quantidade).quantize(centavos) for i in self.itens.all()),
            Decimal("0.00"),
        )


class OcorrenciaReparo(models.Model):
    """Reparo escolhido para a ocorrência, com a quantidade na unidade do reparo."""
    ocorrencia = models.ForeignKey(Ocorrencia, on_delete=models.CASCADE, related_name="itens")
    reparo = models.ForeignKey(Reparo, on_delete=models.PROTECT, related_name="ocorrencias")
    quantidade = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])

    class Meta:
        verbose_name = "reparo da ocorrência"
        verbose_name_plural = "reparos da ocorrência"
        constraints = [
            models.UniqueConstraint(fields=["ocorrencia", "reparo"], name="ocorrencia_reparo_unico"),
        ]

    def __str__(self):
        return f"{self.reparo} × {self.quantidade}"
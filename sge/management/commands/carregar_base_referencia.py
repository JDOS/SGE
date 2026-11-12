"""
Importa a planilha da base de referência (SINAPI, SINAPI-I e cotações) para o model Atividade.

Uso:
    python manage.py carregar_base_referencia base_referencias.xlsx
    python manage.py carregar_base_referencia base_referencias.xlsx --simular     # só mostra, não grava
    python manage.py carregar_base_referencia base_referencias.xlsx --atualizar   # também atualiza os que já existem

Colunas esperadas (na 1ª linha): Fonte | Código | Descrição | Unidade | Custo (R$)

- Um item é considerado JÁ CADASTRADO quando existe uma atividade com a mesma fonte e o mesmo código.
- Sem --atualizar, os que já existem não são alterados; o comando só avisa se o custo da planilha for diferente.
- Com --atualizar, atualiza custo e unidade. Se houver mais de uma atividade com o mesmo código,
  todas recebem o custo novo, e a descrição de cada uma é mantida.
- Unidades que ainda não existem são criadas (M2 -> m², M3 -> m³, H -> h...).
Requer:  pip install openpyxl
"""
import unicodedata
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from sge.models import Atividade, Unidade

FONTES = {"sinapi": Atividade.Fonte.SINAPI, "sinapi-i": Atividade.Fonte.SINAPI_I, "sinapi i": Atividade.Fonte.SINAPI_I,
          "cotacao": Atividade.Fonte.COTACAO}

# sigla da planilha -> (sigla no sistema, nome da unidade)
UNIDADES = {
    "M2": ("m²", "Metros Quadrados"),
    "M": ("m", "Metros"),
    "M3": ("m³", "Metros Cúbicos"),
    "UN": ("UN", "Unidade"),
    "H": ("h", "Hora"),
    "KG": ("kg", "Quilograma"),
    "M3XKM": ("m³×km", "Metro cúbico × quilômetro"),
    "M2XMES": ("m²×mês", "Metro quadrado × mês"),
}

COLUNAS = {"fonte": "fonte", "codigo": "codigo", "descricao": "descricao", "unidade": "unidade", "custo (r$)": "custo",
           "custo": "custo"}


def _sem_acento(texto):
    texto = unicodedata.normalize("NFD", str(texto or ""))
    return "".join(ch for ch in texto if unicodedata.category(ch) != "Mn").strip().lower()


class Command(BaseCommand):
    help = "Cadastra na base de referência (Atividade) os itens da planilha que ainda não existem."

    def add_arguments(self, parser):
        parser.add_argument("arquivo", help="Caminho da planilha .xlsx")
        parser.add_argument("--simular", action="store_true", help="Mostra o que seria feito, sem gravar nada.")
        parser.add_argument("--atualizar", action="store_true",
                            help="Atualiza descrição, unidade e custo dos itens que já existem.")

    def handle(self, *args, arquivo, simular, atualizar, **options):
        try:
            import openpyxl
        except ImportError:
            raise CommandError("Instale o openpyxl:  pip install openpyxl")

        try:
            planilha = openpyxl.load_workbook(arquivo, read_only=True, data_only=True).active
        except FileNotFoundError:
            raise CommandError(f"Arquivo não encontrado: {arquivo}")

        linhas = planilha.iter_rows(values_only=True)
        cabecalho = [COLUNAS.get(_sem_acento(c)) for c in next(linhas)]
        faltando = {"fonte", "codigo", "descricao", "unidade", "custo"} - set(cabecalho)
        if faltando:
            raise CommandError(f"Colunas não encontradas na 1ª linha: {', '.join(sorted(faltando))}")

        unidades_cache = {}

        def unidade(sigla_planilha):
            chave = str(sigla_planilha or "").strip().upper()
            if not chave:
                return None
            if chave in unidades_cache:
                return unidades_cache[chave]
            sigla, nome = UNIDADES.get(chave, (str(sigla_planilha).strip(), str(sigla_planilha).strip()))
            u = Unidade.objects.filter(sigla__iexact=sigla).first() or Unidade.objects.filter(nome__iexact=nome).first()
            if u is None:
                self.stdout.write(f"  unidade nova: {nome} ({sigla})")
                u = Unidade(nome=nome, sigla=sigla)
                if not simular:
                    u.save()
            unidades_cache[chave] = u
            return u

        novos = existentes = atualizados = diferentes = 0
        erros = []

        with transaction.atomic():
            for n, valores in enumerate(linhas, start=2):
                linha = dict(zip(cabecalho, valores))
                if not any(linha.values()):
                    continue
                codigo = str(linha["codigo"] or "").strip()
                descricao = " ".join(str(linha["descricao"] or "").split())
                fonte = FONTES.get(_sem_acento(linha["fonte"]))
                if not fonte or not codigo or not descricao:
                    erros.append(f"linha {n}: fonte, código ou descrição inválidos ({linha['fonte']!r}, {codigo!r})")
                    continue
                try:
                    custo = Decimal(str(linha["custo"]).replace(",", ".")).quantize(Decimal("0.01"))
                except (InvalidOperation, TypeError):
                    erros.append(f"linha {n} ({codigo}): custo inválido {linha['custo']!r}")
                    continue
                un = unidade(linha["unidade"])

                iguais = list(Atividade.objects.filter(fonte=fonte, codigo=codigo).order_by("pk"))
                atual = iguais[0] if iguais else None
                if atual is None:
                    novos += 1
                    self.stdout.write(f"  + {codigo}: {descricao[:70]}")
                    if not simular:
                        Atividade.objects.create(fonte=fonte, codigo=codigo, descricao=descricao,
                                                 unidade=un if un and un.pk else None, custo=custo)
                    continue

                existentes += 1
                if len(iguais) > 1:
                    self.stdout.write(self.style.WARNING(
                        f"  ! {codigo}: há {len(iguais)} atividades com este código"
                        + (" (custo e unidade atualizados em todas; descrição mantida)" if atualizar else "")
                    ))
                if atualizar:
                    for a in iguais:
                        a.custo = custo
                        if un and un.pk:
                            a.unidade = un
                        if len(iguais) == 1:
                            a.descricao = descricao
                        if not simular:
                            a.save()
                        atualizados += 1
                elif atual.custo != custo:
                    diferentes += 1
                    self.stdout.write(self.style.WARNING(
                        f"  ≠ {codigo}: já cadastrado com R$ {atual.custo}; na planilha R$ {custo} (não alterado)"
                    ))

            if simular:
                transaction.set_rollback(True)

        resumo = f"{novos} novos, {existentes} já cadastrados"
        if atualizar:
            resumo += f" ({atualizados} atualizados)"
        elif diferentes:
            resumo += f" ({diferentes} com custo diferente — use --atualizar para aplicar)"
        if simular:
            resumo = "SIMULAÇÃO (nada foi gravado): " + resumo
        self.stdout.write(self.style.SUCCESS(resumo + "."))
        for e in erros:
            self.stdout.write(self.style.ERROR("  " + e))
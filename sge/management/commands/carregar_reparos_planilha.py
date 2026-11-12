"""
Importa os reparos (macrocomposições) e a composição de cada um a partir da planilha reparos.xlsx.

Uso:
    python manage.py carregar_reparos_planilha reparos.xlsx --simular     # só mostra, não grava
    python manage.py carregar_reparos_planilha reparos.xlsx               # cadastra os que faltam
    python manage.py carregar_reparos_planilha reparos.xlsx --atualizar   # também refaz os que já existem

Formato da planilha (colunas): Código | Item | Fonte | Código da referência | Descrição | Unidade | Coeficiente
- Linha "Área N" (descrição = nome da área): vale para os reparos abaixo dela.
- Linha com Código e SEM Item: o reparo (código, nome, unidade).
- Linhas com Código e Item: a composição (fonte + código da referência + coeficiente).
- Linhas "Custo unitário da macrocomposição" e em branco são ignoradas.

Regras:
- O reparo é identificado pelo CÓDIGO. Sem --atualizar, os que já existem não são alterados.
- Cada item da composição é procurado na base de referência (Atividade) pela fonte + código.
  Itens "sem código" são procurados pela descrição e, se não existirem, são criados sem custo.
- Coeficiente vazio vira 0.
- Se alguma referência não for encontrada, o reparo NÃO é cadastrado (para não ficar com custo errado)
  e o comando lista o que falta.
Requer:  pip install openpyxl
"""
import unicodedata
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from sge.models import Atividade, Reparo, ReparoAtividade, Unidade

FONTES = {"sinapi": Atividade.Fonte.SINAPI, "sinapi-i": Atividade.Fonte.SINAPI_I, "cotacao": Atividade.Fonte.COTACAO}
UNIDADES = {"m²": ("m²", "Metros Quadrados"), "m2": ("m²", "Metros Quadrados"), "m": ("m", "Metros"),
            "un": ("UN", "Unidade"), "m³": ("m³", "Metros Cúbicos"), "m3": ("m³", "Metros Cúbicos"),
            "h": ("h", "Hora"), "kg": ("kg", "Quilograma")}
OITO_CASAS = Decimal("0.00000001")


def _normal(texto):
    texto = unicodedata.normalize("NFD", str(texto or ""))
    return " ".join("".join(ch for ch in texto if unicodedata.category(ch) != "Mn").lower().split())


class Command(BaseCommand):
    help = "Cadastra os reparos (macrocomposições) da planilha, com a composição e os coeficientes."

    def add_arguments(self, parser):
        parser.add_argument("arquivo")
        parser.add_argument("--simular", action="store_true", help="Mostra o que seria feito, sem gravar.")
        parser.add_argument("--atualizar", action="store_true",
                            help="Refaz nome, unidade e composição dos reparos que já existem.")

    # ------------------------------------------------------------------ leitura
    def ler(self, arquivo):
        try:
            import openpyxl
        except ImportError:
            raise CommandError("Instale o openpyxl:  pip install openpyxl")
        try:
            # data_only: usa os valores calculados das fórmulas de coeficiente
            ws = openpyxl.load_workbook(arquivo, read_only=True, data_only=True).active
        except FileNotFoundError:
            raise CommandError(f"Arquivo não encontrado: {arquivo}")

        reparos, area, atual = [], "", None
        for n, linha in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            codigo, item, fonte, ref, descricao, unidade, coef = (list(linha) + [None] * 7)[:7]
            texto = " ".join(str(descricao or "").split())
            if isinstance(codigo, str) and codigo.strip().lower().startswith("área"):
                area = f"{codigo.strip()} – {texto}"
                continue
            if codigo in (None, ""):
                continue  # "Custo unitário da macrocomposição" e linhas em branco
            codigo = str(codigo).strip()
            if item in (None, ""):
                atual = {"codigo": codigo, "nome": texto, "unidade": str(unidade or "").strip(),
                         "area": area, "itens": [], "linha": n}
                reparos.append(atual)
                continue
            if atual is None or atual["codigo"] != codigo:
                raise CommandError(f"Linha {n}: item do reparo {codigo} sem a linha de cabeçalho do reparo antes.")
            try:
                coef = Decimal(repr(coef)).quantize(OITO_CASAS, ROUND_HALF_UP) if coef not in (None, "") else Decimal("0")
            except InvalidOperation:
                raise CommandError(f"Linha {n}: coeficiente inválido {coef!r}")
            atual["itens"].append({"linha": n, "fonte": str(fonte or "").strip(), "ref": str(ref or "").strip(),
                                   "descricao": texto, "unidade": str(unidade or "").strip(), "coef": coef})
        return reparos

    # --------------------------------------------------------------- execução
    def handle(self, *args, arquivo, simular, atualizar, **options):
        reparos = self.ler(arquivo)
        unidades = {}

        def unidade(texto):
            chave = texto.strip().lower()
            if chave not in unidades:
                sigla, nome = UNIDADES.get(chave, (texto.strip(), texto.strip()))
                u = (Unidade.objects.filter(sigla__iexact=sigla).first()
                     or Unidade.objects.filter(nome__iexact=nome).first())
                if u is None:
                    u = Unidade.objects.create(nome=nome, sigla=sigla)
                    self.stdout.write(f"  unidade nova: {u}")
                unidades[chave] = u
            return unidades[chave]

        def referencia(item):
            fonte = FONTES.get(_normal(item["fonte"]))
            if fonte is None:
                return None, f"fonte desconhecida {item['fonte']!r}"
            if _normal(item["ref"]) in ("", "sem codigo"):
                # item sem código: procura pela descrição; se não existir, cria sem custo
                a = (Atividade.objects.filter(fonte=fonte, codigo="", descricao__iexact=item["descricao"]).first())
                if a is None:
                    a = Atividade.objects.create(fonte=fonte, codigo="", descricao=item["descricao"],
                                                 unidade=unidade(item["unidade"]) if item["unidade"] else None)
                    self.stdout.write(self.style.WARNING(
                        f"  ! criada na base de referência SEM CUSTO: {item['descricao'][:60]} (preencha o custo)"))
                return a, None
            candidatas = list(Atividade.objects.filter(fonte=fonte, codigo=item["ref"]).order_by("pk"))
            if not candidatas:
                return None, f"{item['fonte']} {item['ref']} não está na base de referência"
            if len(candidatas) > 1:  # mesmo código em mais de uma atividade: escolhe pela descrição
                alvo = _normal(item["descricao"])
                for a in candidatas:
                    if _normal(a.descricao) == alvo:
                        return a, None
            return candidatas[0], None

        novos = atualizados = ignorados = 0
        problemas = []

        with transaction.atomic():
            for r in reparos:
                existente = Reparo.objects.filter(codigo=r["codigo"]).first()
                if existente and not atualizar:
                    ignorados += 1
                    continue

                outro = Reparo.objects.filter(nome=r["nome"]).exclude(codigo=r["codigo"]).first()
                if outro:
                    problemas.append(f"{r['codigo']}: já existe outro reparo com o mesmo nome (“{outro}”).")
                    continue

                composicao, faltando = [], []
                for item in r["itens"]:
                    atividade, erro = referencia(item)
                    if erro:
                        faltando.append(f"linha {item['linha']}: {erro}")
                    else:
                        composicao.append((atividade, item["coef"]))
                if faltando:
                    problemas.append(f"{r['codigo']} {r['nome'][:50]} — NÃO cadastrado: " + "; ".join(faltando))
                    continue

                # mesma atividade duas vezes no reparo: soma os coeficientes
                somados = {}
                for atividade, coef in composicao:
                    somados[atividade.pk] = somados.get(atividade.pk, Decimal("0")) + coef

                reparo = existente or Reparo(codigo=r["codigo"])
                reparo.nome = r["nome"]
                reparo.unidade = unidade(r["unidade"] or "un")
                reparo.descricao = reparo.descricao or r["area"]
                reparo.save()
                reparo.composicao.all().delete()
                ReparoAtividade.objects.bulk_create(
                    ReparoAtividade(reparo=reparo, atividade_id=pk, coeficiente=coef) for pk, coef in somados.items()
                )
                if existente:
                    atualizados += 1
                    self.stdout.write(f"  ~ {reparo.codigo} {reparo.nome[:60]}: R$ {reparo.custo_unitario}/{reparo.unidade.sigla}")
                else:
                    novos += 1
                    self.stdout.write(f"  + {reparo.codigo} {reparo.nome[:60]}: R$ {reparo.custo_unitario}/{reparo.unidade.sigla}")

            if simular:
                transaction.set_rollback(True)

        resumo = f"Reparos: {novos} novos, {atualizados} atualizados, {ignorados} já existiam (não alterados)"
        if problemas:
            resumo += f", {len(problemas)} com problema"
        self.stdout.write(self.style.SUCCESS(("SIMULAÇÃO (nada foi gravado): " if simular else "") + resumo + "."))
        for p in problemas:
            self.stdout.write(self.style.ERROR("  " + p))
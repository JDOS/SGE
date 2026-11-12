"""
Cadastra as soluções (reparos) de cada causa a partir da planilha causas_reparos.xlsx.

Uso:
    python manage.py carregar_solucoes causas_reparos.xlsx --simular
    python manage.py carregar_solucoes causas_reparos.xlsx
Opções:
    --substituir       apaga e recria as soluções das causas que JÁ têm soluções (sem isso, elas são puladas)
    --criar-pendentes  cria um reparo provisório (sem composição) para códigos que não existem no cadastro

Colunas: Causa | Código no catálogo | principal | complementares | Avaliação especializada

Como o texto é lido (exemplos da planilha):
    "100111, 100121 ou 100131 (conforme a telha)"   -> 3 soluções, condição "conforme a telha"
    "100312 ou 100322 (conserto localizado) ou 100902 (reforma)"
                                                     -> 100312 e 100322 com "conserto localizado"; 100902 com "reforma"
    "400315 ou 400325 + 600312 ou 600322"           -> 400315  |  400325 + 600312  |  600322
    "400201 + 600101, ou 400402 em parede com cerâmica"
                                                     -> 400201 + 600101  |  400402 ("em parede com cerâmica")
    "900401 para vidros e 600905 para pintura ..."   -> duas soluções, cada uma com a sua condição
    "Não se aplica"                                  -> nenhuma
Cada alternativa ("ou", ",") vira uma SOLUÇÃO; reparos ligados por "+" ficam juntos na mesma solução.

A causa é encontrada pela descrição. Se a mesma descrição existir em mais de um problema
(ex.: "Fissura em elemento estrutural"), as linhas são associadas na ordem dos problemas.
Requer:  pip install openpyxl
"""
import re
import unicodedata

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from sge.models import Causa, ItemSolucao, Reparo, Solucao, Unidade

CODIGO = re.compile(r"\d{6}")
PARENTESES = re.compile(r"\(([^)]*)\)")
ALTERNATIVAS = re.compile(r"\s*,\s*ou\s+|\s*,\s*|\s+ou\s+|\s+e\s+(?=\d{6})", re.IGNORECASE)


def _normal(texto):
    texto = unicodedata.normalize("NFD", str(texto or ""))
    return " ".join("".join(ch for ch in texto if unicodedata.category(ch) != "Mn").lower().split())


def interpretar(texto):
    """Texto da planilha -> lista de (lista de códigos que vão juntos, condição)."""
    texto = " ".join(str(texto or "").split())
    if _normal(texto) in ("", "-", "nao se aplica"):
        return []

    # 1) segmentos: cada "(...)" vale para o trecho que vem antes dele
    segmentos, inicio = [], 0
    for m in PARENTESES.finditer(texto):
        segmentos.append((texto[inicio:m.start()], m.group(1).strip()))
        inicio = m.end()
    if texto[inicio:].strip():
        segmentos.append((texto[inicio:], ""))

    resultado = []
    for trecho, condicao in segmentos:
        trecho = re.sub(r"^[\s,]*(ou\s+)?", "", trecho, flags=re.IGNORECASE).strip()
        if not trecho:
            continue
        alternativas = []
        for alt in ALTERNATIVAS.split(trecho):
            codigos = CODIGO.findall(alt)
            if not codigos:
                continue
            resto = CODIGO.sub("", alt).replace("+", " ")
            resto = " ".join(resto.strip(" ,;.").split())
            alternativas.append([codigos, condicao or resto])
        # "… após estabilização" / "… quando embutido" no fim vale para todas as alternativas do trecho
        if alternativas and not condicao:
            ultima = alternativas[-1][1]
            if _normal(ultima).startswith(("apos", "quando")):
                for alt in alternativas:
                    alt[1] = alt[1] or ultima
        resultado.extend((codigos, cond) for codigos, cond in alternativas)
    return resultado


class Command(BaseCommand):
    help = "Cadastra as soluções (reparos principais e complementares) de cada causa."

    def add_arguments(self, parser):
        parser.add_argument("arquivo")
        parser.add_argument("--simular", action="store_true")
        parser.add_argument("--substituir", action="store_true",
                            help="Recria as soluções das causas que já têm soluções.")
        parser.add_argument("--criar-pendentes", action="store_true",
                            help="Cria reparo provisório para códigos que não existem.")

    def handle(self, *args, arquivo, simular, substituir, criar_pendentes, **options):
        try:
            import openpyxl
        except ImportError:
            raise CommandError("Instale o openpyxl:  pip install openpyxl")
        try:
            ws = openpyxl.load_workbook(arquivo, read_only=True, data_only=True).active
        except FileNotFoundError:
            raise CommandError(f"Arquivo não encontrado: {arquivo}")

        # causas do sistema por descrição, na ordem dos problemas
        por_descricao = {}
        for c in Causa.objects.select_related("problema").order_by("problema__codigo", "numero"):
            por_descricao.setdefault(_normal(c.descricao), []).append(c)
        usadas = {}

        reparos = {r.codigo: r for r in Reparo.objects.exclude(codigo="")}
        pendentes, faltando = set(), set()
        cont = {"causas": 0, "puladas": 0, "solucoes": 0, "atributos": 0}
        avisos = []

        with transaction.atomic():
            unidade_un = None

            def reparo(codigo):
                nonlocal unidade_un
                if codigo in reparos:
                    return reparos[codigo]
                if not criar_pendentes:
                    faltando.add(codigo)
                    return None
                if unidade_un is None:
                    unidade_un = (Unidade.objects.filter(sigla__iexact="UN").first()
                                  or Unidade.objects.create(nome="Unidade", sigla="UN"))
                r = Reparo.objects.create(codigo=codigo, unidade=unidade_un,
                                          nome=f"{codigo} – reparo pendente de cadastro",
                                          descricao="Criado automaticamente pela planilha de causas x reparos. "
                                                    "Complete nome, unidade e composição.")
                reparos[codigo] = r
                pendentes.add(codigo)
                return r

            for n, linha in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                desc, catalogo, principal, complementar, especializada = (list(linha) + [None] * 5)[:5]
                if not desc:
                    continue
                chave = _normal(desc)
                candidatas = por_descricao.get(chave, [])
                i = usadas.get(chave, 0)
                if i >= len(candidatas):
                    avisos.append(f"linha {n}: causa “{desc}” não encontrada (cadastre os problemas e causas antes)")
                    continue
                causa = candidatas[i]
                usadas[chave] = i + 1

                # atributos da causa
                catalogo = str(catalogo or "").strip()
                esp = _normal(especializada) == "sim"
                if causa.codigo_catalogo != catalogo or causa.avaliacao_especializada != esp:
                    causa.codigo_catalogo, causa.avaliacao_especializada = catalogo, esp
                    causa.save(update_fields=["codigo_catalogo", "avaliacao_especializada"])
                    cont["atributos"] += 1

                if causa.solucoes.exists():
                    if not substituir:
                        cont["puladas"] += 1
                        avisos.append(f"{causa.codigo}: já tem soluções cadastradas (pulada; use --substituir)")
                        continue
                    causa.solucoes.all().delete()

                criadas = []
                for tipo, texto in ((Solucao.Tipo.PRINCIPAL, principal), (Solucao.Tipo.COMPLEMENTAR, complementar)):
                    for ordem, (codigos, condicao) in enumerate(interpretar(texto)):
                        itens = [reparo(c) for c in codigos]
                        if None in itens:
                            avisos.append(f"{causa.codigo}: solução “{' + '.join(codigos)}” não criada "
                                          f"(reparo sem cadastro)")
                            continue
                        sol = Solucao.objects.create(causa=causa, tipo=tipo, condicao=condicao[:150], ordem=ordem)
                        ItemSolucao.objects.bulk_create(
                            ItemSolucao(solucao=sol, reparo=r, grupo=g) for g, r in enumerate(itens, start=1)
                        )
                        criadas.append(f"{sol.get_tipo_display()[0]}: {' + '.join(codigos)}"
                                       + (f" ({condicao})" if condicao else ""))
                        cont["solucoes"] += 1
                cont["causas"] += 1
                self.stdout.write(f"  {causa.codigo}  " + "  |  ".join(criadas) if criadas else
                                  f"  {causa.codigo}  (sem soluções)")

            if simular:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS(
            ("SIMULAÇÃO (nada foi gravado): " if simular else "")
            + f"{cont['solucoes']} soluções criadas em {cont['causas']} causas; "
            + f"{cont['puladas']} causas puladas; {cont['atributos']} causas com catálogo/avaliação atualizados."
        ))
        if pendentes:
            self.stdout.write(self.style.WARNING(
                f"Reparos provisórios criados ({len(pendentes)}): {', '.join(sorted(pendentes))} — complete o cadastro."))
        if faltando:
            self.stdout.write(self.style.ERROR(
                f"Reparos que não existem no cadastro ({len(faltando)}): {', '.join(sorted(faltando))}. "
                "As soluções com eles não foram criadas. Cadastre esses reparos ou use --criar-pendentes."))
        for a in avisos:
            self.stdout.write(self.style.WARNING("  " + a))
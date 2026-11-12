"""
Cadastra os problemas e as causas da planilha problemas_causa.xlsx.

Uso:
    python manage.py carregar_problemas problemas_causa.xlsx --simular   # só mostra, não grava
    python manage.py carregar_problemas problemas_causa.xlsx

Colunas: Relação (PR-01.1) | Problema (PR-01 Goteira ou infiltração pelo teto) | Causa
- O problema é identificado pelo código (PR-01); o nome é atualizado se mudou.
- A causa é identificada pelo problema + número (o 1 de PR-01.1); a descrição é atualizada se mudou.
  Código no catálogo, avaliação especializada, observação e soluções da causa não são alterados.
- Pode rodar quantas vezes quiser: nada é duplicado.
Requer:  pip install openpyxl
"""
import re

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from sge.models import Causa, Problema

RELACAO = re.compile(r"^(PR-\d+)\.(\d+)$")
PROBLEMA = re.compile(r"^(PR-\d+)\s+(.+)$")


class Command(BaseCommand):
    help = "Cadastra (ou atualiza) os problemas e as causas da planilha."

    def add_arguments(self, parser):
        parser.add_argument("arquivo")
        parser.add_argument("--simular", action="store_true", help="Mostra o que seria feito, sem gravar.")

    @transaction.atomic
    def handle(self, *args, arquivo, simular, **options):
        try:
            import openpyxl
        except ImportError:
            raise CommandError("Instale o openpyxl:  pip install openpyxl")
        try:
            ws = openpyxl.load_workbook(arquivo, read_only=True, data_only=True).active
        except FileNotFoundError:
            raise CommandError(f"Arquivo não encontrado: {arquivo}")

        cont = {"prob_novo": 0, "prob_nome": 0, "causa_nova": 0, "causa_desc": 0, "igual": 0}
        erros, vistos = [], set()

        for n, linha in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            relacao, problema_txt, causa_txt = (list(linha) + [None] * 3)[:3]
            if not any((relacao, problema_txt, causa_txt)):
                continue
            rel = RELACAO.match(str(relacao or "").strip())
            prob = PROBLEMA.match(" ".join(str(problema_txt or "").split()))
            descricao = " ".join(str(causa_txt or "").split())
            if not rel or not prob or not descricao:
                erros.append(f"linha {n}: formato inesperado ({relacao!r}, {problema_txt!r})")
                continue
            if rel.group(1) != prob.group(1):
                erros.append(f"linha {n}: relação {relacao} não bate com o problema {prob.group(1)}")
                continue
            codigo, numero, nome = prob.group(1), int(rel.group(2)), prob.group(2).strip()
            if (codigo, numero) in vistos:
                erros.append(f"linha {n}: {relacao} repetida na planilha")
                continue
            vistos.add((codigo, numero))

            problema = Problema.objects.filter(codigo=codigo).first()
            if problema is None:
                problema = Problema.objects.create(codigo=codigo, nome=nome)
                cont["prob_novo"] += 1
                self.stdout.write(f"  + problema {codigo} {nome}")
            elif problema.nome != nome:
                self.stdout.write(f"  ~ problema {codigo}: “{problema.nome}” -> “{nome}”")
                problema.nome = nome
                problema.save(update_fields=["nome"])
                cont["prob_nome"] += 1

            causa = Causa.objects.filter(problema=problema, numero=numero).first()
            if causa is None:
                Causa.objects.create(problema=problema, numero=numero, descricao=descricao)
                cont["causa_nova"] += 1
            elif causa.descricao != descricao:
                self.stdout.write(f"  ~ causa {relacao}: “{causa.descricao}” -> “{descricao}”")
                causa.descricao = descricao
                causa.save(update_fields=["descricao"])
                cont["causa_desc"] += 1
            else:
                cont["igual"] += 1

        # causas que estão no sistema mas não na planilha (só avisa, não apaga)
        fora = [c for c in Causa.objects.select_related("problema")
                if (c.problema.codigo, c.numero) not in vistos]

        if simular:
            transaction.set_rollback(True)
        self.stdout.write(self.style.SUCCESS(
            ("SIMULAÇÃO (nada foi gravado): " if simular else "")
            + f"Problemas: {cont['prob_novo']} novos, {cont['prob_nome']} com nome atualizado. "
            + f"Causas: {cont['causa_nova']} novas, {cont['causa_desc']} com descrição atualizada, {cont['igual']} já iguais."
        ))
        for c in fora:
            self.stdout.write(self.style.WARNING(f"  ! {c.codigo} {c.descricao} — está no sistema mas não na planilha (mantida)"))
        for e in erros:
            self.stdout.write(self.style.ERROR("  " + e))
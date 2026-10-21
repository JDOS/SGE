"""
Cria os reparos a partir das atividades (SINAPI) e liga cada reparo aos critérios da ficha.

Uso:
    python manage.py carregar_reparos

- Pode rodar quantas vezes quiser: reparos com o mesmo nome são atualizados, nada é duplicado.
- As atividades são procuradas pelo NOME exato. Se alguma não existir, ela é criada com o
  código, a unidade e o custo da lista ATIVIDADES abaixo (as que já existem não são alteradas).
- O custo de cada reparo é a soma das suas atividades, por isso todas as atividades de um
  reparo estão na mesma unidade do reparo.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from sge.models import Atividade, Criterio, Reparo, Unidade

# sigla -> nome da unidade (usado só se a unidade ainda não existir)
UNIDADES = {"m²": "Metros Quadrados", "m": "Metros", "UN": "Unidade"}

# nome da atividade: (código SINAPI, sigla da unidade, custo) — usado só para criar as que faltarem
ATIVIDADES = {
    "Alvenaria de vedação, bloco cerâmico 9x19x19 cm": ("103329", "m²", "119.38"),
    "Aplicação manual de pintura com tinta texturizada acrílica em paredes externas de casas, duas cores. Af_03/2024": ("88431", "m²", "29.55"),
    "Barra de apoio lateral articulada em aço inox": ("100865", "UN", "638.85"),
    "Barra de apoio reta em aço inox, 80 cm": ("100868", "UN", "378.04"),
    "Cabo de cobre flexível 2,5 mm², 450/750 V": ("91926", "m", "5.79"),
    "Calha em chapa de aço galvanizado nº 24, desenvolvimento 50 cm": ("94228", "m", "97.04"),
    "Chapisco em alvenaria de fachada com vãos, traço 1:3": ("87905", "m²", "10.30"),
    "Chapisco em alvenaria e estrutura internas, traço 1:3": ("87879", "m²", "5.38"),
    "Corrimão duplo em aço galvanizado, Ø 1 1/2\"": ("99858", "m", "193.11"),
    "Corrimão simples em aço galvanizado, Ø 1 1/2\"": ("99855", "m", "97.78"),
    "Cumeeira para telha cerâmica emboçada, até 2 águas": ("94221", "m", "48.62"),
    "Demolição da proteção e da impermeabilização antigas": ("97631", "m²", "16.74"),
    "Demolição de argamassas, manual": ("97631", "m²", "16.74"),
    "Demolição de revestimento cerâmico, manual": ("97633", "m²", "33.43"),
    "Eletroduto flexível corrugado PVC DN 25, em parede": ("91854", "m", "13.07"),
    "Emboço/massa única em fachada com vãos, e = 25 mm": ("87775", "m²", "68.56"),
    "Extintor portátil CO2 4 kg, classe BC": ("101906", "UN", "701.23"),
    "Extintor portátil PQS 4 kg, classe BC": ("101908", "UN", "237.57"),
    "Impermeabilização com argamassa polimérica, 3 demãos": ("98555", "m²", "38.07"),
    "Impermeabilização com manta asfáltica 4 mm, com primer": ("98546", "m²", "137.79"),
    "Interruptor simples 10 A, com suporte e placa": ("91953", "UN", "41.12"),
    "Limpeza da laje com jato de alta pressão": ("99814", "m²", "2.23"),
    "Massa única em paredes internas, e = 10 mm, ambientes > 10 m²": ("104958", "m²", "27.78"),
    "Piso podotátil de borracha, alerta ou direcional": ("101094", "m", "208.66"),
    "Piso podotátil de concreto, alerta ou direcional": ("104658", "m²", "208.38"),
    "Proteção mecânica com argamassa 1:3, 3 cm": ("98565", "m²", "65.30"),
    "Quadro de distribuição de embutir, 24 disjuntores": ("101879", "UN", "633.63"),
    "Ralo sifonado PVC DN 100x40": ("89709", "UN", "27.38"),
    "Rampa de acessibilidade 8,33% em concreto, largura 1,20 m": ("105000", "m", "1386.42"),
    "Rampa de acessibilidade em calçada existente (≥ 3 m), com piso tátil": ("105003", "m²", "1417.38"),
    "Regularização com argamassa 1:4, 3 cm, sobre laje": ("87630", "m²", "43.79"),
    "Remoção de calhas e rufos, manual": ("104803", "m", "6.59"),
    "Remoção de forros de drywall, PVC e fibromineral": ("97640", "m²", "2.89"),
    "Remoção de janelas": ("97645", "m²", "35.98"),
    "Remoção de louças": ("97663", "UN", "19.10"),
    "Remoção de portas": ("97644", "m²", "13.94"),
    "Remoção de telhas (fibrocimento, metálica ou cerâmica), manual": ("97647", "m²", "5.20"),
    "Retirada e recolocação de telha cerâmica de encaixe, até 2 águas": ("100328", "m²", "33.06"),
    "Revestimento cerâmico de parede 20x20 cm, altura inteira": ("87265", "m²", "62.82"),
    "Rufo em chapa de aço galvanizado nº 24, corte 25 cm": ("94231", "m", "55.39"),
    "Subcobertura com manta plástica revestida de alumínio": ("94226", "m²", "23.72"),
    "Telhamento com telha de aço 0,5 mm": ("94213", "m²", "77.24"),
    "Telhamento com telha metálica termoacústica 30 mm": ("94216", "m²", "225.61"),
    "Telhamento com telha ondulada de fibrocimento 6 mm, inclinação > 10°": ("94207", "m²", "48.25"),
    "Tomada baixa 2P+T 10 A, com suporte e placa": ("92000", "UN", "42.95"),
    "Tomada média 2P+T 10 A, com suporte e placa": ("91996", "UN", "48.99"),
    "Torneira cromada de mesa para lavatório, monocomando": ("100853", "UN", "318.60"),
    "Torneira cromada de mesa para lavatório, padrão popular": ("86906", "UN", "74.96"),
    "Tratamento de rodapé com véu de poliéster": ("98559", "m", "5.86"),
    "Tubo PVC esgoto série normal DN 100, ramal": ("89714", "m", "54.36"),
    "Tubo PVC soldável 25 mm, ramal ou sub-ramal de água": ("89356", "m", "34.25"),
    "Tubo PVC série R, água pluvial, DN 100, condutor vertical": ("89578", "m", "44.43"),
}

# (nome do reparo, sigla da unidade, descrição, [atividades], [critérios da ficha])
REPAROS = [
    # ---------------- cobertura e águas pluviais
    ("Revisão de telhado cerâmico", "m²",
     "Retirada e recolocação das telhas cerâmicas, com troca das quebradas.",
     ["Retirada e recolocação de telha cerâmica de encaixe, até 2 águas"],
     ["Coberturas"]),
    ("Substituição por telha de fibrocimento", "m²",
     "Remoção das telhas existentes e novo telhamento em fibrocimento 6 mm.",
     ["Remoção de telhas (fibrocimento, metálica ou cerâmica), manual",
      "Telhamento com telha ondulada de fibrocimento 6 mm, inclinação > 10°"],
     ["Coberturas"]),
    ("Substituição por telha de aço", "m²",
     "Remoção das telhas existentes e novo telhamento com telha de aço 0,5 mm.",
     ["Remoção de telhas (fibrocimento, metálica ou cerâmica), manual",
      "Telhamento com telha de aço 0,5 mm"],
     ["Coberturas"]),
    ("Substituição por telha termoacústica", "m²",
     "Remoção das telhas existentes e novo telhamento com telha metálica termoacústica 30 mm.",
     ["Remoção de telhas (fibrocimento, metálica ou cerâmica), manual",
      "Telhamento com telha metálica termoacústica 30 mm"],
     ["Coberturas", "Isolamento térmico de coberturas", "Poluição sonora"]),
    ("Instalação de subcobertura térmica", "m²",
     "Manta plástica aluminizada sob as telhas, para reduzir o calor.",
     ["Subcobertura com manta plástica revestida de alumínio"],
     ["Isolamento térmico de coberturas"]),
    ("Recuperação de cumeeira", "m",
     "Cumeeira de telha cerâmica emboçada.",
     ["Cumeeira para telha cerâmica emboçada, até 2 águas"],
     ["Coberturas"]),
    ("Substituição de calhas", "m",
     "Remoção da calha existente e nova calha em aço galvanizado nº 24.",
     ["Remoção de calhas e rufos, manual",
      "Calha em chapa de aço galvanizado nº 24, desenvolvimento 50 cm"],
     ["Águas pluviais", "Coberturas"]),
    ("Substituição de rufos", "m",
     "Remoção do rufo existente e novo rufo em aço galvanizado nº 24.",
     ["Remoção de calhas e rufos, manual",
      "Rufo em chapa de aço galvanizado nº 24, corte 25 cm"],
     ["Coberturas", "Águas pluviais", "Estanqueidade"]),
    ("Instalação de condutor pluvial", "m",
     "Tubo PVC DN 100 para descida de água de chuva.",
     ["Tubo PVC série R, água pluvial, DN 100, condutor vertical"],
     ["Águas pluviais", "Captação de chuvas"]),

    # ---------------- impermeabilização
    ("Impermeabilização de laje com manta asfáltica", "m²",
     "Remoção da impermeabilização antiga, limpeza, regularização, manta asfáltica 4 mm e proteção mecânica.",
     ["Demolição da proteção e da impermeabilização antigas",
      "Limpeza da laje com jato de alta pressão",
      "Regularização com argamassa 1:4, 3 cm, sobre laje",
      "Impermeabilização com manta asfáltica 4 mm, com primer",
      "Proteção mecânica com argamassa 1:3, 3 cm"],
     ["Coberturas", "Estanqueidade"]),
    ("Impermeabilização com argamassa polimérica", "m²",
     "Argamassa polimérica em 3 demãos, para paredes e áreas molhadas.",
     ["Impermeabilização com argamassa polimérica, 3 demãos"],
     ["Estanqueidade", "Umidade nos ambientes", "Paredes"]),
    ("Tratamento de rodapé contra umidade", "m",
     "Reforço com véu de poliéster no encontro entre parede e piso.",
     ["Tratamento de rodapé com véu de poliéster"],
     ["Umidade nos ambientes", "Estanqueidade"]),

    # ---------------- paredes, revestimentos e pintura
    ("Recuperação de reboco interno", "m²",
     "Remoção do reboco danificado, chapisco e massa única de 10 mm.",
     ["Demolição de argamassas, manual",
      "Chapisco em alvenaria e estrutura internas, traço 1:3",
      "Massa única em paredes internas, e = 10 mm, ambientes > 10 m²"],
     ["Paredes", "Revestimentos"]),
    ("Recuperação de reboco de fachada", "m²",
     "Remoção do reboco danificado, chapisco e emboço de 25 mm na fachada.",
     ["Demolição de argamassas, manual",
      "Chapisco em alvenaria de fachada com vãos, traço 1:3",
      "Emboço/massa única em fachada com vãos, e = 25 mm"],
     ["Paredes", "Estética da edificação"]),
    ("Substituição de revestimento cerâmico de parede", "m²",
     "Remoção da cerâmica solta ou trincada e novo revestimento 20x20 cm.",
     ["Demolição de revestimento cerâmico, manual",
      "Revestimento cerâmico de parede 20x20 cm, altura inteira"],
     ["Revestimentos"]),
    ("Reconstrução de alvenaria", "m²",
     "Alvenaria de vedação em bloco cerâmico 9x19x19 cm.",
     ["Alvenaria de vedação, bloco cerâmico 9x19x19 cm"],
     ["Paredes", "Portões, grades e muros"]),
    ("Pintura texturizada de fachada", "m²",
     "Pintura com tinta texturizada acrílica em paredes externas, duas cores.",
     ["Aplicação manual de pintura com tinta texturizada acrílica em paredes externas de casas, duas cores. Af_03/2024"],
     ["Pintura de paredes", "Estética da edificação", "Sinais de depredação"]),

    # ---------------- forro e esquadrias
    ("Remoção de forro danificado", "m²",
     "Retirada de forro de drywall, PVC ou fibromineral.",
     ["Remoção de forros de drywall, PVC e fibromineral"],
     ["Forro"]),
    ("Remoção de portas danificadas", "m²",
     "Retirada de portas para substituição.",
     ["Remoção de portas"],
     ["Esquadrias (portas e janelas)", "Sinais de depredação"]),
    ("Remoção de janelas danificadas", "m²",
     "Retirada de janelas para substituição.",
     ["Remoção de janelas"],
     ["Esquadrias (portas e janelas)", "Sinais de depredação"]),

    # ---------------- acessibilidade
    ("Construção de rampa acessível", "m",
     "Rampa em concreto com inclinação de 8,33% e largura de 1,20 m.",
     ["Rampa de acessibilidade 8,33% em concreto, largura 1,20 m"],
     ["Rampas", "Acessibilidade (PMR)"]),
    ("Rampa em calçada existente", "m²",
     "Rebaixamento de calçada com rampa e piso tátil.",
     ["Rampa de acessibilidade em calçada existente (≥ 3 m), com piso tátil"],
     ["Acessibilidade (PMR)", "Estacionamento"]),
    ("Instalação de piso podotátil de borracha", "m",
     "Piso tátil de alerta ou direcional em borracha.",
     ["Piso podotátil de borracha, alerta ou direcional"],
     ["Acessibilidade (PMR)"]),
    ("Instalação de piso podotátil de concreto", "m²",
     "Piso tátil de alerta ou direcional em concreto.",
     ["Piso podotátil de concreto, alerta ou direcional"],
     ["Acessibilidade (PMR)"]),
    ("Instalação de corrimão simples", "m",
     "Corrimão em aço galvanizado Ø 1 1/2\".",
     ["Corrimão simples em aço galvanizado, Ø 1 1/2\""],
     ["Escadas", "Rampas"]),
    ("Instalação de corrimão duplo", "m",
     "Corrimão duplo em aço galvanizado Ø 1 1/2\", em duas alturas.",
     ["Corrimão duplo em aço galvanizado, Ø 1 1/2\""],
     ["Escadas", "Rampas", "Acessibilidade (PMR)"]),
    ("Instalação de barra de apoio reta", "UN",
     "Barra reta em aço inox, 80 cm, para sanitário acessível.",
     ["Barra de apoio reta em aço inox, 80 cm"],
     ["Acessibilidade (PMR)", "Louças"]),
    ("Instalação de barra de apoio articulada", "UN",
     "Barra lateral articulada em aço inox, para sanitário acessível.",
     ["Barra de apoio lateral articulada em aço inox"],
     ["Acessibilidade (PMR)", "Louças"]),

    # ---------------- instalações elétricas
    ("Substituição de quadro de distribuição", "UN",
     "Quadro de embutir para 24 disjuntores.",
     ["Quadro de distribuição de embutir, 24 disjuntores"],
     ["Instalações elétricas"]),
    ("Substituição de fiação em eletroduto", "m",
     "Novo eletroduto corrugado DN 25 e cabo de cobre 2,5 mm².",
     ["Eletroduto flexível corrugado PVC DN 25, em parede",
      "Cabo de cobre flexível 2,5 mm², 450/750 V"],
     ["Instalações elétricas"]),
    ("Instalação de tomada baixa", "UN",
     "Tomada 2P+T 10 A baixa, com suporte e placa.",
     ["Tomada baixa 2P+T 10 A, com suporte e placa"],
     ["Tomadas"]),
    ("Instalação de tomada média", "UN",
     "Tomada 2P+T 10 A média, com suporte e placa.",
     ["Tomada média 2P+T 10 A, com suporte e placa"],
     ["Tomadas"]),
    ("Instalação de interruptor", "UN",
     "Interruptor simples 10 A, com suporte e placa.",
     ["Interruptor simples 10 A, com suporte e placa"],
     ["Instalações elétricas", "Iluminação artificial"]),

    # ---------------- instalações hidrossanitárias
    ("Substituição de tubulação de água", "m",
     "Tubo PVC soldável 25 mm em ramal ou sub-ramal.",
     ["Tubo PVC soldável 25 mm, ramal ou sub-ramal de água"],
     ["Instalações de água"]),
    ("Substituição de tubulação de esgoto", "m",
     "Tubo PVC esgoto DN 100 em ramal.",
     ["Tubo PVC esgoto série normal DN 100, ramal"],
     ["Instalações de esgoto"]),
    ("Instalação de ralo sifonado", "UN",
     "Ralo sifonado PVC DN 100x40.",
     ["Ralo sifonado PVC DN 100x40"],
     ["Instalações de esgoto", "Estanqueidade"]),
    ("Substituição de torneira (padrão popular)", "UN",
     "Torneira cromada de mesa para lavatório, padrão popular.",
     ["Torneira cromada de mesa para lavatório, padrão popular"],
     ["Metais"]),
    ("Substituição de torneira monocomando", "UN",
     "Torneira cromada de mesa para lavatório, monocomando.",
     ["Torneira cromada de mesa para lavatório, monocomando"],
     ["Metais", "Eficiência energética"]),
    ("Remoção de louça danificada", "UN",
     "Retirada de bacia, pia ou mictório para substituição.",
     ["Remoção de louças"],
     ["Louças"]),

    # ---------------- segurança contra incêndio
    ("Instalação de extintor PQS 4 kg", "UN",
     "Extintor portátil de pó químico seco, classe BC.",
     ["Extintor portátil PQS 4 kg, classe BC"],
     ["Extintores"]),
    ("Instalação de extintor CO2 4 kg", "UN",
     "Extintor portátil de CO2, classe BC (indicado para quadros elétricos).",
     ["Extintor portátil CO2 4 kg, classe BC"],
     ["Extintores"]),
]


class Command(BaseCommand):
    help = "Cria os reparos a partir das atividades e liga cada reparo aos critérios da ficha."

    @transaction.atomic
    def handle(self, *args, **options):
        unidades = {}
        for sigla, nome in UNIDADES.items():
            unidade = Unidade.objects.filter(sigla__iexact=sigla).first()
            if unidade is None:
                unidade = Unidade.objects.create(nome=nome, sigla=sigla)
                self.stdout.write(f"  unidade criada: {unidade}")
            unidades[sigla] = unidade

        def atividade(nome):
            existentes = Atividade.objects.filter(nome=nome).order_by("pk")
            if existentes.count() > 1:
                self.stdout.write(self.style.WARNING(
                    f"  atenção: há {existentes.count()} atividades '{nome}'; usando a primeira."
                ))
            if existentes:
                return existentes.first(), False
            cod, sigla, custo = ATIVIDADES[nome]
            nova = Atividade.objects.create(
                nome=nome, cod_sicro=cod, unidade=unidades[sigla], custo=Decimal(custo),
            )
            return nova, True

        novos = atualizados = atividades_criadas = ligacoes = 0
        sem_criterio = set()

        for nome, sigla, descricao, nomes_atividades, nomes_criterios in REPAROS:
            reparo, novo = Reparo.objects.update_or_create(
                nome=nome, defaults={"unidade": unidades[sigla], "descricao": descricao},
            )
            novos += novo
            atualizados += not novo

            lista = []
            for n in nomes_atividades:
                a, criada = atividade(n)
                atividades_criadas += criada
                lista.append(a)
            reparo.atividades.set(lista)

            for nome_criterio in nomes_criterios:
                criterios = Criterio.objects.filter(nome=nome_criterio)
                if not criterios:
                    sem_criterio.add(nome_criterio)
                for c in criterios:
                    c.reparos.add(reparo)
                    ligacoes += 1

            self.stdout.write(f"  {reparo.nome}: R$ {reparo.custo_unitario} / {reparo.unidade.sigla}")

        self.stdout.write(self.style.SUCCESS(
            f"Reparos: {novos} novos, {atualizados} atualizados. "
            f"Atividades criadas: {atividades_criadas}. Ligações com critérios: {ligacoes}."
        ))
        if sem_criterio:
            self.stdout.write(self.style.WARNING(
                "Critérios não encontrados (confira o nome no admin): " + ", ".join(sorted(sem_criterio))
            ))
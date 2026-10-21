"""
Cadastra as categorias e os critérios de avaliação.

Uso:
    python manage.py carregar_criterios

Pode rodar quantas vezes quiser: o que já existe é atualizado, nada é duplicado.
Para incluir novos critérios, acrescente linhas na lista CRITERIOS.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from sge.models import Categoria, Criterio

# (categoria, critério, o que verificar)
CRITERIOS = [
    ("Instalações", "Coberturas", "Impermeabilidade, estrutura e telhas adequadas, sem manifestações patológicas"),
    ("Instalações", "Paredes", "Material adequado, sem fissuras, umidade ou descolamentos"),
    ("Instalações", "Quadras poliesportivas", "Estrutura adequada, sem defeitos"),
    ("Instalações", "Parquinho / pátio", "Sem defeitos, dimensionado para os alunos, piso não escorregadio"),
    ("Instalações", "Portões, grades e muros", "Sem defeitos, portões com trava, adequação ergonômica"),
    ("Instalações", "Áreas não pavimentadas", "Sem erosão, buracos ou empoçamento"),
    ("Instalações", "Mobiliário", "Sem defeitos, adequado à faixa etária, carteiras para todos"),
    ("Instalações", "Estruturas", "Desempenho estrutural, sem fissuras, armaduras expostas ou deformações"),
    ("Instalações", "Estacionamento", "Sem defeitos, vaga de carga e descarga, vaga acessível"),
    ("Instalações", "Escadas", "Seguras para uso, corrimão, sem defeitos"),
    ("Instalações", "Rampas", "Seguras para uso, sem defeitos"),
    ("Instalações", "Elevadores", "Em funcionamento, sem defeitos"),

    ("Acabamentos", "Pintura de paredes", "Sem defeitos; cor clara, lisa, lavável e impermeável"),
    ("Acabamentos", "Revestimentos", "Sem descolamento, trincas ou peças soltas"),
    ("Acabamentos", "Pisos", "Sem defeitos, material lavável"),
    ("Acabamentos", "Tomadas", "Ao menos uma por ambiente, sem defeitos"),
    ("Acabamentos", "Metais", "Torneiras e registros em quantidade adequada, sem vazamentos"),
    ("Acabamentos", "Esquadrias (portas e janelas)", "Adequadas ao ambiente, sem vidros quebrados ou ferragens soltas"),
    ("Acabamentos", "Forro", "Existe, sem manchas, quedas ou infiltração"),
    ("Acabamentos", "Louças", "Bacias, pias e mictórios em quantidade adequada, sem defeitos"),

    ("Segurança contra incêndio", "Extintores", "Existem, dentro da validade e sinalizados"),
    ("Segurança contra incêndio", "Rotas de fuga", "Existem e estão desobstruídas"),
    ("Segurança contra incêndio", "Sinalização e iluminação de emergência", "Placas e luminárias de emergência adequadas"),

    ("Conforto térmico", "Isolamento térmico de paredes", "Paredes com isolamento térmico"),
    ("Conforto térmico", "Isolamento térmico de coberturas", "Cobertura com isolamento térmico"),
    ("Conforto térmico", "Aberturas para ventilação", "Ventilação cruzada; aberturas ≥ 1/5 da área do piso"),
    ("Conforto térmico", "Umidade nos ambientes", "Ambientes sem umidade, mofo ou bolor"),

    ("Conforto acústico", "Isolamento acústico de paredes", "Paredes com isolamento acústico"),
    ("Conforto acústico", "Poluição sonora", "Sem ruído excessivo interno ou externo"),

    ("Conforto visual", "Iluminação natural", "Aberturas de iluminação > 1/10 da área do piso"),
    ("Conforto visual", "Iluminação artificial", "Luminárias suficientes e funcionando"),

    ("Infraestrutura", "Instalações de água", "Abastecimento, dimensionamento e materiais adequados, sem vazamentos"),
    ("Infraestrutura", "Instalações de esgoto", "Rede pública ou fossa, sem entupimentos ou odores"),
    ("Infraestrutura", "Águas pluviais", "Calhas e condutores com capacidade adequada e desobstruídos"),
    ("Infraestrutura", "Instalações elétricas", "Abastecimento e quadros adequados, sem fiação exposta"),
    ("Infraestrutura", "Telecomunicação", "Telefone, computadores e acesso à internet"),

    ("Sustentabilidade", "Eficiência energética", "Uso de iluminação e ventilação natural, energia alternativa"),
    ("Sustentabilidade", "Gestão ambiental", "Águas servidas vão à rede pública ou a sistema que evite contaminação"),
    ("Sustentabilidade", "Destinação de resíduos", "Coleta seletiva (separação e descarte)"),
    ("Sustentabilidade", "Captação de chuvas", "Existe gestão de captação de água de chuva"),

    ("Habitabilidade", "Pé-direito", "Igual ou maior que 2,60 m"),
    ("Habitabilidade", "Estanqueidade", "Paredes, pisos e áreas molhadas sem infiltração"),
    ("Habitabilidade", "Sinais de depredação", "Sem vidros quebrados, portas danificadas, lâmpadas estouradas"),
    ("Habitabilidade", "Poluentes internos", "Ar interno sem poluentes ou proliferação de microrganismos"),
    ("Habitabilidade", "Acessibilidade (PMR)", "Ambientes acessíveis conforme NBR 9050 — detalhar na seção 5A"),
    ("Habitabilidade", "Limpeza dos ambientes", "Ambientes e equipamentos limpos"),
    ("Habitabilidade", "Estética da edificação", "Identidade visual, layout funcional, acabamentos adequados"),

    ("Segurança", "Controle de entrada e saída de alunos", "Existe controle"),
    ("Segurança", "Controle de entrada de estranhos", "Existe controle"),
    ("Segurança", "Vigilância diurna", "Existe vigilância"),
    ("Segurança", "Vigilância noturna", "Existe vigilância ou monitoramento"),
    ("Segurança", "Vigilância em fins de semana e feriados", "Existe vigilância ou monitoramento"),
    ("Segurança", "Policiamento contra furtos e violência", "Existe esquema de policiamento"),
    ("Segurança", "Policiamento contra drogas na escola", "Existe esquema de policiamento"),
    ("Segurança", "Policiamento contra drogas no entorno", "Existe esquema de policiamento"),
    ("Segurança", "Iluminação externa", "Entorno da escola iluminado"),
    ("Segurança", "Proteção de equipamentos caros", "Guardados em sala segura ou com proteção"),
    ("Segurança", "Segurança no entorno imediato", "Muros, grades ou cercas garantem a segurança"),

    ("Fatores externos", "Localização", "Local adequado, sem riscos ambientais próximos"),
    ("Fatores externos", "Transporte público", "Acesso a transporte público próximo"),
]


class Command(BaseCommand):
    help = "Cadastra (ou atualiza) as categorias e os critérios de avaliação das escolas."

    @transaction.atomic
    def handle(self, *args, **options):
        cat_novas = crit_novos = crit_atualizados = 0
        categorias = {}

        for nome_cat, nome_crit, verificar in CRITERIOS:
            if nome_cat not in categorias:
                categorias[nome_cat], nova = Categoria.objects.get_or_create(nome=nome_cat)
                cat_novas += nova

            _, novo = Criterio.objects.update_or_create(
                categoria=categorias[nome_cat],
                nome=nome_crit,
                defaults={"o_que_verificar": verificar},
            )
            if novo:
                crit_novos += 1
            else:
                crit_atualizados += 1

        self.stdout.write(self.style.SUCCESS(
            f"Categorias: {cat_novas} novas ({len(categorias)} no total). "
            f"Critérios: {crit_novos} novos, {crit_atualizados} atualizados."
        ))
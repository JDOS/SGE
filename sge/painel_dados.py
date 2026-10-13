"""
Dados SIMULADOS para o Painel de Análise Integrada do SGE.

Tudo aqui é fictício (nomes das escolas, não conformidades e custos), exceto o
índice das escolas marcadas como "da tese", que vem da tese InfraEs (Machado, 2023).
Quando o sistema tiver dados reais, troque `gerar_painel()` por consultas aos models.

Os números batem com o PDF de demonstração:
30 escolas · 608 NC abertas (455 abertas + 153 em andamento) · 131 resolvidas
101 NC de acessibilidade · custo total R$ 7.022.317,89
"""
import random
from datetime import date, timedelta
from functools import lru_cache

# id, nome, bairro, índice, NC abertas, NC acessibilidade, alunos, prioridade, custo (R$)
ESCOLAS = [
    ("E16", "EM Sapucaia", "Centro", 0.442, 33, 7, 846, 2.814, 608054.37),
    ("E22", "EM Cambuí", "Estação", 0.475, 31, 7, 940, 2.785, 362843.04),
    ("E18", "EM Iguaçu", "Cachoeira", 0.536, 32, 5, 1027, 2.542, 467984.58),
    ("E10", "EM Canela", "Capela Velha", 0.486, 20, 1, 308, 2.282, 220230.14),
    ("E06", "EM Sabiá (Escola K da tese)", "Centro", 0.598, 29, 5, 535, 2.136, 301667.15),
    ("E28", "EM Araçá", "Costeira", 0.465, 23, 2, 264, 2.125, 229658.78),
    ("E24", "EM Uvaia", "Estação", 0.580, 21, 4, 755, 2.040, 187567.10),
    ("E12", "EM Tucano", "Estação", 0.650, 26, 4, 584, 1.910, 325708.59),
    ("E13", "EM Quaresmeira", "Campina da Barra", 0.690, 21, 4, 760, 1.850, 357506.66),
    ("E29", "EM Guapuruvu", "Boqueirão", 0.601, 19, 3, 338, 1.817, 192640.32),
    ("E17", "EM Capivari", "Capela Velha", 0.603, 24, 5, 514, 1.731, 202300.80),
    ("E07", "EM Imbuia (Escola L da tese)", "Thomaz Coelho", 0.626, 21, 3, 323, 1.712, 463930.03),
    ("E26", "EM Jacarandá", "Estação", 0.701, 22, 4, 775, 1.517, 174061.41),
    ("E08", "EM Cerejeira (Escola M da tese)", "Iguaçu", 0.762, 16, 3, 734, 1.504, 130537.32),
    ("E01", "EM Ipê Amarelo (Escola F da tese)", "Iguaçu", 0.590, 21, 1, 248, 1.480, 236235.04),
    ("E30", "EM Peroba", "Costeira", 0.646, 17, 5, 264, 1.462, 181645.36),
    ("E19", "EM Passaúna", "Centro", 0.611, 20, 2, 363, 1.437, 127762.66),
    ("E03", "EM Pinhão (Escola H da tese)", "Iguaçu", 0.696, 19, 1, 443, 1.432, 139579.02),
    ("E14", "EM Pitangueira", "Capela Velha", 0.786, 19, 3, 796, 1.422, 188043.40),
    ("E20", "EM Barigui", "Thomaz Coelho", 0.620, 20, 2, 215, 1.390, 213432.65),
    ("E25", "EM Aroeira", "Costeira", 0.668, 22, 3, 222, 1.386, 235798.51),
    ("E02", "EM Gralha Azul (Escola G da tese)", "Fazenda Velha", 0.706, 19, 4, 565, 1.382, 232083.38),
    ("E27", "EM Manacá", "Fazenda Velha", 0.703, 13, 7, 428, 1.241, 216057.98),
    ("E15", "EM Guabiroba", "Costeira", 0.668, 11, 1, 372, 1.206, 75215.11),
    ("E11", "EM Bracatinga", "Centro", 0.817, 19, 3, 888, 1.099, 170377.35),
    ("E23", "EM Butiá", "Tindiquera", 0.826, 15, 0, 507, 1.062, 181140.89),
    ("E05", "EM Bem-te-vi (Escola J da tese)", "Tindiquera", 0.821, 16, 2, 884, 1.027, 127901.85),
    ("E09", "EM Jabuticabeira", "Tindiquera", 0.796, 12, 4, 677, 0.972, 110892.20),
    ("E04", "EM Erva-Mate (Escola I da tese)", "Centro", 0.757, 14, 4, 293, 0.969, 89585.19),
    ("E21", "EM Tingui", "Campina da Barra", 0.852, 13, 2, 318, 0.794, 271877.01),
]

# NC abertas por categoria e custo aproximado por categoria (do PDF)
CATEGORIAS = {
    "Acabamentos": (123, 689_000),
    "Acessibilidade": (101, 2_000_000),
    "Instalações": (80, 1_800_000),
    "Infraestrutura": (69, 835_000),
    "Segurança contra incêndio": (59, 443_000),
    "Habitabilidade": (46, 199_000),
    "Conforto térmico": (39, 405_000),
    "Conforto visual": (27, 141_000),
    "Sustentabilidade": (22, 210_000),
    "Segurança da escola": (19, 116_000),
    "Conforto acústico": (15, 122_000),
    "Fatores externos": (8, 24_000),
}

GRAVIDADE_TOTAL = {"Alta": 95, "Média": 282, "Baixa": 231}
EM_ANDAMENTO_TOTAL = 153
RESOLVIDAS_TOTAL = 131

# posição aproximada dos bairros de Araucária (PR) — usada só para o mapa ilustrativo
BAIRROS = {
    "Centro": (-25.5930, -49.4100), "Estação": (-25.5815, -49.3985),
    "Cachoeira": (-25.5560, -49.3830), "Capela Velha": (-25.6060, -49.3860),
    "Costeira": (-25.5740, -49.3640), "Campina da Barra": (-25.6230, -49.4290),
    "Boqueirão": (-25.6150, -49.3960), "Thomaz Coelho": (-25.5450, -49.4060),
    "Iguaçu": (-25.5880, -49.3760), "Fazenda Velha": (-25.6020, -49.4330),
    "Tindiquera": (-25.5700, -49.4250),
}

SERVICOS = {
    "Acabamentos": ["Recuperação de reboco com fissuras", "Repintura de paredes internas",
                    "Troca de revestimento cerâmico solto", "Reparo de forro danificado"],
    "Acessibilidade": ["Construção de rampa de acesso", "Adequação de sanitário PCD",
                       "Instalação de piso tátil", "Instalação de corrimão duplo",
                       "Alargamento de porta para 80 cm"],
    "Instalações": ["Substituição de quadro elétrico", "Troca de tubulação com vazamento",
                    "Revisão de fiação exposta", "Reparo de calha e condutores"],
    "Infraestrutura": ["Recuperação de cobertura com infiltração", "Reparo de muro com trinca",
                       "Recuperação de piso do pátio", "Drenagem de área externa"],
    "Segurança contra incêndio": ["Recarga e instalação de extintores", "Sinalização de rota de fuga",
                                  "Instalação de iluminação de emergência", "Adequação de saída de emergência"],
    "Habitabilidade": ["Tratamento de umidade em parede", "Desobstrução de ventilação",
                       "Correção de odor de esgoto"],
    "Conforto térmico": ["Instalação de ventiladores", "Isolamento térmico da cobertura",
                         "Instalação de brises nas janelas"],
    "Conforto visual": ["Troca de luminárias", "Substituição de vidros foscos", "Instalação de cortinas"],
    "Sustentabilidade": ["Instalação de arejadores nas torneiras", "Implantação de coleta seletiva",
                         "Troca de lâmpadas por LED"],
    "Segurança da escola": ["Reparo de portão de acesso", "Instalação de câmeras",
                            "Reforço de grades nas janelas"],
    "Conforto acústico": ["Tratamento acústico do refeitório", "Vedação de esquadrias"],
    "Fatores externos": ["Sinalização de travessia escolar", "Poda de árvore próxima à cobertura"],
}
LOCAIS = ["Sala de aula 1", "Sala de aula 2", "Sala de aula 3", "Sala de aula 4", "Refeitório",
          "Cozinha", "Banheiro feminino", "Banheiro masculino", "Banheiro PCD", "Pátio coberto",
          "Quadra", "Secretaria", "Biblioteca", "Corredor principal", "Entrada", "Área externa"]

PESO_GRAVIDADE = {"Alta": 1.7, "Média": 1.0, "Baixa": 0.55}


def _escolher_altas(rng):
    """Escolhe nº de NC de gravidade alta e de alunos com deficiência por escola,
    de forma que o índice de prioridade do PDF se mantenha e o total de altas seja 95:
    prioridade = (1 − índice) × 3 + 0,08 × NC alta + 0,03 × alunos com deficiência."""
    opcoes = []
    for (_, _, _, ind, nc, _, _, prio, _) in ESCOLAS:
        resto = prio - (1 - ind) * 3
        opcoes.append([(a, d) for a in range(nc + 1) for d in range(80)
                       if abs(0.08 * a + 0.03 * d - resto) < 0.0006])
    pesos = [nc * (1 - ind) for (_, _, _, ind, nc, *_r) in ESCOLAS]
    alvo = [GRAVIDADE_TOTAL["Alta"] * p / sum(pesos) for p in pesos]

    # programação dinâmica: soma de altas = 95, o mais perto possível do alvo
    total = GRAVIDADE_TOTAL["Alta"]
    melhor = {0: (0.0, [])}
    for i, ops in enumerate(opcoes):
        novo = {}
        for s, (custo, escolha) in melhor.items():
            for a, d in ops:
                if s + a > total:
                    continue
                c = custo + (a - alvo[i]) ** 2
                if s + a not in novo or c < novo[s + a][0]:
                    novo[s + a] = (c, escolha + [(a, d)])
        melhor = novo
    return melhor[total][1]


@lru_cache(maxsize=1)
def gerar_painel():
    rng = random.Random(2026)
    altas = _escolher_altas(rng)

    escolas = []
    for i, (eid, nome, bairro, ind, nc, ac, alunos, prio, custo) in enumerate(ESCOLAS):
        lat, lng = BAIRROS[bairro]
        tese = "da tese" in nome
        curto = nome
        if tese:
            letra = nome.split("Escola ")[1][0]
            curto = nome.split(" (")[0] + f" ({letra}*)"
        escolas.append({
            "id": eid, "nome": nome, "curto": curto, "bairro": bairro, "tese": tese,
            "indice": ind, "faixa": "Mínimo" if ind < 0.5 else ("Médio" if ind < 0.75 else "Elevado"),
            "alunos": alunos, "deficiencia": altas[i][1], "prioridade": prio, "custo": custo,
            "lat": round(lat + rng.uniform(-0.007, 0.007), 5),
            "lng": round(lng + rng.uniform(-0.007, 0.007), 5),
        })

    # ---- categorias das NC abertas: acessibilidade pela tabela, o resto sorteado ----
    pool = []
    for cat, (qtd, _) in CATEGORIAS.items():
        if cat != "Acessibilidade":
            pool += [cat] * qtd
    rng.shuffle(pool)

    ncs = []
    for i, (eid, _, _, _, nc, ac, *_r) in enumerate(ESCOLAS):
        cats = ["Acessibilidade"] * ac + [pool.pop() for _ in range(nc - ac)]
        grav = ["Alta"] * altas[i][0] + [None] * (nc - altas[i][0])
        rng.shuffle(grav)
        for c, g in zip(cats, grav):
            ncs.append({"escola": eid, "categoria": c, "gravidade": g})

    # gravidade média/baixa nas restantes (282 / 231)
    resto = [n for n in ncs if n["gravidade"] is None]
    rng.shuffle(resto)
    for k, n in enumerate(resto):
        n["gravidade"] = "Média" if k < GRAVIDADE_TOTAL["Média"] else "Baixa"

    # status: 153 em andamento, demais abertas
    idx = list(range(len(ncs)))
    rng.shuffle(idx)
    andamento = set(idx[:EM_ANDAMENTO_TOTAL])
    for k, n in enumerate(ncs):
        n["status"] = "Em andamento" if k in andamento else "Aberta"

    # ---- custos: ajuste para bater o total por escola (exato) e ~ por categoria ----
    custo_cat = {c: v for c, (_, v) in CATEGORIAS.items()}
    for n in ncs:
        n["_c"] = PESO_GRAVIDADE[n["gravidade"]] * rng.lognormvariate(0, 0.45)
    custo_escola = {e["id"]: e["custo"] for e in escolas}
    for _ in range(25):
        for cat, alvo in custo_cat.items():
            itens = [n for n in ncs if n["categoria"] == cat]
            s = sum(n["_c"] for n in itens)
            for n in itens:
                n["_c"] *= alvo / s
        for eid, alvo in custo_escola.items():
            itens = [n for n in ncs if n["escola"] == eid]
            s = sum(n["_c"] for n in itens)
            for n in itens:
                n["_c"] *= alvo / s
    for eid, alvo in custo_escola.items():
        itens = [n for n in ncs if n["escola"] == eid]
        for n in itens:
            n["custo"] = round(n["_c"], 2)
        itens[-1]["custo"] = round(itens[-1]["custo"] + alvo - sum(n["custo"] for n in itens), 2)

    # ---- NC resolvidas (não entram no custo de recuperação) ----
    cats = list(CATEGORIAS)
    pesos = [q for q, _ in CATEGORIAS.values()]
    for _ in range(RESOLVIDAS_TOTAL):
        e = rng.choice(escolas)
        ncs.append({"escola": e["id"], "categoria": rng.choices(cats, pesos)[0],
                    "gravidade": rng.choices(["Alta", "Média", "Baixa"], [1, 3, 3])[0],
                    "status": "Resolvida", "custo": 0})

    # ---- detalhes para a lista da escola ----
    inicio = date(2025, 3, 1)
    for k, n in enumerate(ncs, start=1):
        n.pop("_c", None)
        n["id"] = f"NC-{k:04d}"
        n["servico"] = rng.choice(SERVICOS[n["categoria"]])
        n["local"] = rng.choice(LOCAIS)
        n["data"] = (inicio + timedelta(days=rng.randint(0, 520))).isoformat()

    return {
        "escolas": escolas,
        "ncs": ncs,
        "categorias": list(CATEGORIAS),
    }

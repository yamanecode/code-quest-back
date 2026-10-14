"""
Run once to populate the DB with challenges and badges.
Usage: python seed.py
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.database import SessionLocal
from app.models.models import Badge, Challenge, ChallengeCategory, ChallengeType

db = SessionLocal()

# ── Badges ────────────────────────────────────────────────────────────────────
badges = [
    Badge(
        name="Primeira Submissão",
        description="Submeteu um desafio pela primeira vez",
        icon="🎯",
        trigger_condition="first_submission",
    ),
    Badge(name="Nível 5", description="Alcançou o nível 5", icon="⭐", trigger_condition="level_5"),
    Badge(
        name="Nível 10", description="Alcançou o nível 10", icon="🌟", trigger_condition="level_10"
    ),
    Badge(
        name="Sequência de 3",
        description="3 dias seguidos resolvendo desafios",
        icon="🔥",
        trigger_condition="3_day_streak",
    ),
    Badge(
        name="Sequência de 7",
        description="7 dias seguidos!",
        icon="💎",
        trigger_condition="7_day_streak",
    ),
    Badge(name="100 XP", description="Acumulou 100 XP", icon="💯", trigger_condition="xp_100"),
    Badge(name="500 XP", description="Acumulou 500 XP", icon="🏆", trigger_condition="xp_500"),
]

# ── Challenges ────────────────────────────────────────────────────────────────
challenges = [
    # ── DECOMPOSITION (steps) ── 2 easy, 2 medium, 2 hard ────────────────────
    Challenge(
        title="Organizar Estudantes por Nota",
        description="Você precisa criar um sistema que ordena automaticamente estudantes por nota. Antes de codificar, decomponha o problema em entrada, processamento e saída.",
        difficulty=1,
        category=ChallengeCategory.decomposition,
        type=ChallengeType.steps,
        content={
            "steps": [
                {"label": "Quais são os dados de entrada do sistema?"},
                {"label": "Qual processamento o sistema deve realizar?"},
                {"label": "Qual deve ser a saída do sistema?"},
            ],
            "expected_keywords": [
                ["lista", "estudantes", "notas", "nomes", "alunos", "dados", "entrada"],
                ["ordenar", "comparar", "classificar", "organizar", "sort"],
                ["lista ordenada", "resultado", "saída", "classificação", "ranking", "ordem"],
            ],
        },
    ),
    Challenge(
        title="Calculadora Simples",
        description="Você vai construir uma calculadora básica. Decomponha o que ela precisa receber, o que precisa fazer e o que deve mostrar ao usuário.",
        difficulty=1,
        category=ChallengeCategory.decomposition,
        type=ChallengeType.steps,
        content={
            "steps": [
                {"label": "Quais dados o usuário precisa fornecer para a calculadora funcionar?"},
                {"label": "O que a calculadora processa internamente?"},
                {"label": "O que é exibido ao usuário no final?"},
            ],
            "expected_keywords": [
                ["números", "operação", "valores", "entrada", "operandos", "input"],
                [
                    "calcular",
                    "somar",
                    "subtrair",
                    "multiplicar",
                    "dividir",
                    "operação",
                    "processar",
                    "computar",
                ],
                ["resultado", "resposta", "saída", "valor", "exibir", "mostrar", "output"],
            ],
        },
    ),
    Challenge(
        title="Sistema de Login",
        description="Desenvolva o sistema de autenticação de um app web. Decomponha cada etapa do processo, incluindo quando a senha está certa e quando está errada.",
        difficulty=2,
        category=ChallengeCategory.decomposition,
        type=ChallengeType.steps,
        content={
            "steps": [
                {"label": "Quais dados o usuário precisa fornecer para iniciar o login?"},
                {"label": "O que o sistema verifica internamente após receber esses dados?"},
                {"label": "O que acontece se as credenciais estiverem corretas?"},
                {"label": "O que acontece se as credenciais estiverem incorretas?"},
            ],
            "expected_keywords": [
                ["email", "senha", "usuário", "credenciais", "login", "dados", "input"],
                ["verificar", "comparar", "banco", "validar", "autenticar", "hash", "criptografia"],
                ["acesso", "token", "sessão", "redirecionar", "dashboard", "sucesso"],
                ["erro", "negado", "inválido", "mensagem", "bloqueio", "falhou", "tentativas"],
            ],
        },
    ),
    Challenge(
        title="Busca em Catálogo de Produtos",
        description="Implemente a função de busca de um e-commerce. Quando o usuário digita 'tênis azul tamanho 42', o sistema precisa encontrar os produtos certos em milissegundos.",
        difficulty=2,
        category=ChallengeCategory.decomposition,
        type=ChallengeType.steps,
        content={
            "steps": [
                {"label": "O que o sistema recebe como entrada quando o usuário faz uma busca?"},
                {"label": "Como o sistema processa essa busca internamente?"},
                {"label": "O que é retornado ao usuário ao final?"},
            ],
            "expected_keywords": [
                ["texto", "query", "termo", "palavras", "filtro", "pesquisa", "string", "input"],
                ["comparar", "filtrar", "buscar", "índice", "algoritmo", "consulta", "pesquisar"],
                ["produtos", "resultado", "lista", "itens", "encontrados", "resposta"],
            ],
        },
    ),
    Challenge(
        title="Sistema de Recomendação",
        description="Plataformas como Netflix usam algoritmos de recomendação. Decomponha o processo completo: da coleta de dados até a entrega das recomendações, incluindo como o sistema aprende.",
        difficulty=3,
        category=ChallengeCategory.decomposition,
        type=ChallengeType.steps,
        content={
            "steps": [
                {"label": "Quais dados sobre o usuário o sistema precisa coletar?"},
                {"label": "Como o sistema processa esses dados para identificar preferências?"},
                {"label": "Como o algoritmo seleciona e ordena os itens a recomendar?"},
                {"label": "Como o sistema melhora com base no comportamento futuro do usuário?"},
            ],
            "expected_keywords": [
                [
                    "histórico",
                    "comportamento",
                    "cliques",
                    "visualizações",
                    "avaliações",
                    "dados",
                    "perfil",
                    "interações",
                ],
                [
                    "analisar",
                    "padrões",
                    "similaridade",
                    "modelo",
                    "filtro",
                    "colaborativo",
                    "correlação",
                    "comparar",
                ],
                [
                    "ordenar",
                    "pontuar",
                    "ranquear",
                    "relevância",
                    "selecionar",
                    "priorizar",
                    "score",
                ],
                [
                    "feedback",
                    "atualizar",
                    "aprender",
                    "ajustar",
                    "melhorar",
                    "adaptação",
                    "iteração",
                ],
            ],
        },
    ),
    Challenge(
        title="Pipeline de Dados em Tempo Real",
        description="Um sistema de monitoramento financeiro precisa processar milhões de transações por segundo. Decomponha a arquitetura completa desse pipeline, desde a ingestão até os alertas.",
        difficulty=3,
        category=ChallengeCategory.decomposition,
        type=ChallengeType.steps,
        content={
            "steps": [
                {"label": "Como os dados de transações chegam ao sistema?"},
                {"label": "Como o sistema processa e filtra os dados em tempo real?"},
                {"label": "Como anomalias e fraudes são detectadas?"},
                {"label": "Como os resultados são armazenados e os alertas disparados?"},
            ],
            "expected_keywords": [
                [
                    "stream",
                    "kafka",
                    "fila",
                    "mensagens",
                    "ingestão",
                    "entrada",
                    "api",
                    "eventos",
                    "fluxo",
                ],
                [
                    "processar",
                    "filtrar",
                    "transformar",
                    "pipeline",
                    "janela",
                    "tempo real",
                    "batch",
                    "streaming",
                ],
                [
                    "anomalia",
                    "fraude",
                    "padrão",
                    "modelo",
                    "threshold",
                    "regra",
                    "machine learning",
                    "detecção",
                ],
                [
                    "banco",
                    "armazenar",
                    "alerta",
                    "notificação",
                    "dashboard",
                    "log",
                    "saída",
                    "resposta",
                ],
            ],
        },
    ),
    # ── PATTERN ── 2 easy, 2 medium, 2 hard ──────────────────────────────────
    Challenge(
        title="Dobrando Sempre",
        description="Um vírus se replica dobrando sua quantidade a cada hora. Na primeira hora havia 2 vírus, depois 4, depois 8, depois 16... Qual o próximo?",
        difficulty=1,
        category=ChallengeCategory.pattern,
        type=ChallengeType.pattern,
        content={
            "sequence": "2, 4, 8, 16, ___",
            "answer": "32",
            "explanation": "Cada número é multiplicado por 2.",
        },
    ),
    Challenge(
        title="Quadrados Perfeitos",
        description="Em computação gráfica, texturas são dimensionadas em quadrados perfeitos. Observe: 1, 4, 9, 16, 25... Qual é o próximo?",
        difficulty=1,
        category=ChallengeCategory.pattern,
        type=ChallengeType.pattern,
        content={
            "sequence": "1, 4, 9, 16, 25, ___",
            "answer": "36",
            "explanation": "Quadrados perfeitos: 1², 2², 3², 4², 5², 6²=36.",
        },
    ),
    Challenge(
        title="A Sequência da Natureza",
        description="Essa sequência aparece em espirais de conchas e no design de interfaces. Observe e descubra a regra: qual é o próximo número?",
        difficulty=2,
        category=ChallengeCategory.pattern,
        type=ChallengeType.pattern,
        content={
            "sequence": "1, 1, 2, 3, 5, 8, ___",
            "answer": "13",
            "explanation": "Fibonacci: cada número é a soma dos dois anteriores.",
        },
    ),
    Challenge(
        title="Algoritmo de Desconto",
        description="Um e-commerce aplica desconto proporcional: R$100→R$90, R$200→R$180, R$300→R$270. Quanto custaria R$400 após o desconto?",
        difficulty=2,
        category=ChallengeCategory.pattern,
        type=ChallengeType.pattern,
        content={
            "sequence": "100→90, 200→180, 300→270, 400→___",
            "answer": "360",
            "explanation": "10% de desconto. R$400 × 0.9 = R$360.",
        },
    ),
    Challenge(
        title="Crescimento de Rede Social",
        description="Com 2 usuários há 1 conexão possível, com 3 há 3, com 4 há 6, com 5 há 10... Quantas conexões com 6 usuários?",
        difficulty=3,
        category=ChallengeCategory.pattern,
        type=ChallengeType.pattern,
        content={
            "sequence": "1, 3, 6, 10, ___",
            "answer": "15",
            "explanation": "Números triangulares: n×(n-1)/2. Com 6: 6×5/2=15.",
        },
    ),
    Challenge(
        title="Complexidade Algorítmica",
        description="Um algoritmo processa: 1 elemento em 1ms, 2 em 4ms, 3 em 9ms, 4 em 16ms. Quanto tempo para processar 5 elementos?",
        difficulty=3,
        category=ChallengeCategory.pattern,
        type=ChallengeType.pattern,
        content={
            "sequence": "1→1ms, 2→4ms, 3→9ms, 4→16ms, 5→___",
            "answer": "25ms",
            "explanation": "Complexidade O(n²): n² milissegundos. 5²=25ms.",
        },
    ),
    # ── ABSTRACTION (ordering) ── 2 easy, 2 medium, 2 hard ───────────────────
    Challenge(
        title="O que Importa num Perfil de Usuário?",
        description="Um app de delivery precisa armazenar dados do usuário. Ordene os dados do MAIS essencial para o MENOS essencial para o funcionamento do app.",
        difficulty=1,
        category=ChallengeCategory.abstraction,
        type=ChallengeType.ordering,
        content={
            "items": [
                "Endereço de entrega",
                "Nome do usuário",
                "Foto de perfil",
                "Cor favorita",
            ],
            "correct_order": [1, 0, 2, 3],
            "explanation": "Nome e endereço são essenciais. Foto é opcional. Cor favorita é irrelevante para o app.",
        },
    ),
    Challenge(
        title="Abstração de um Carro",
        description="Para um sistema de GPS, ordene os atributos de um carro do MAIS relevante para o MENOS relevante.",
        difficulty=1,
        category=ChallengeCategory.abstraction,
        type=ChallengeType.ordering,
        content={
            "items": [
                "Velocidade atual",
                "Posição GPS",
                "Cor do carro",
                "Destino",
            ],
            "correct_order": [1, 3, 0, 2],
            "explanation": "Posição e destino são fundamentais. Velocidade é útil. Cor é irrelevante para GPS.",
        },
    ),
    Challenge(
        title="Modelo de Dados de um Produto",
        description="Para um sistema de e-commerce, ordene os atributos de um produto do MAIS ao MENOS essencial para uma compra.",
        difficulty=2,
        category=ChallengeCategory.abstraction,
        type=ChallengeType.ordering,
        content={
            "items": [
                "Preço",
                "Disponibilidade em estoque",
                "Descrição detalhada",
                "História da marca",
                "ID do produto",
            ],
            "correct_order": [4, 1, 0, 2, 3],
            "explanation": "ID identifica unicamente. Estoque e preço são críticos. Descrição ajuda. História da marca é secundária.",
        },
    ),
    Challenge(
        title="Abstração de uma Rede Social",
        description="Para o algoritmo de feed de uma rede social, ordene os fatores do MAIS ao MENOS relevante para decidir o que mostrar ao usuário.",
        difficulty=2,
        category=ChallengeCategory.abstraction,
        type=ChallengeType.ordering,
        content={
            "items": [
                "Engajamento do post (likes, comentários)",
                "Relevância para o usuário",
                "Data de publicação",
                "Número de seguidores do autor",
                "Cor do tema do perfil do autor",
            ],
            "correct_order": [1, 0, 2, 3, 4],
            "explanation": "Relevância é primária. Engajamento indica qualidade. Data garante frescor. Seguidores têm peso menor. Tema visual é irrelevante.",
        },
    ),
    Challenge(
        title="Abstraindo um Sistema de Detecção de Fraudes",
        description="Para um modelo de ML detectar fraudes em transações bancárias, ordene os atributos do MAIS ao MENOS relevante.",
        difficulty=3,
        category=ChallengeCategory.abstraction,
        type=ChallengeType.ordering,
        content={
            "items": [
                "Valor da transação",
                "Localização geográfica",
                "Histórico de comportamento do usuário",
                "Hora da transação",
                "Nome do banco emissor",
                "Design do cartão",
            ],
            "correct_order": [2, 0, 1, 3, 4, 5],
            "explanation": "Histórico comportamental é o mais preditivo. Valor e localização são críticos. Hora é relevante. Banco emissor tem peso menor. Design é irrelevante.",
        },
    ),
    Challenge(
        title="Modelo de Dados para um Compilador",
        description="Um compilador precisa analisar código-fonte. Ordene as informações do MAIS ao MENOS essencial para gerar código executável correto.",
        difficulty=3,
        category=ChallengeCategory.abstraction,
        type=ChallengeType.ordering,
        content={
            "items": [
                "Tipos das variáveis",
                "Estrutura sintática do código",
                "Comentários do programador",
                "Nomes das variáveis",
                "Espaçamento e indentação",
                "Semântica das operações",
            ],
            "correct_order": [5, 1, 0, 3, 4, 2],
            "explanation": "Semântica e sintaxe são fundamentais. Tipos garantem operações válidas. Nomes identificam variáveis. Indentação é ignorada. Comentários são descartados.",
        },
    ),
    # ── ALGORITHM (ordering/drag-drop) ── 2 easy, 2 medium, 2 hard ───────────
    Challenge(
        title="Algoritmo de Busca Binária",
        description="Ordene os passos do algoritmo de busca binária para encontrar um número em uma lista ordenada.",
        difficulty=1,
        category=ChallengeCategory.algorithm,
        type=ChallengeType.ordering,
        content={
            "items": [
                "Comparar o elemento do meio com o alvo",
                "Definir os limites inicial e final da lista",
                "Se igual, retornar o índice",
                "Se menor, buscar na metade direita; se maior, na esquerda",
                "Calcular o índice do meio",
            ],
            "correct_order": [1, 4, 0, 2, 3],
            "explanation": "Definir limites → calcular meio → comparar → retornar se igual → ajustar metade.",
        },
    ),
    Challenge(
        title="Algoritmo de Bubble Sort",
        description="Ordene os passos do algoritmo Bubble Sort para ordenar uma lista de números em ordem crescente.",
        difficulty=1,
        category=ChallengeCategory.algorithm,
        type=ChallengeType.ordering,
        content={
            "items": [
                "Comparar elementos adjacentes",
                "Repetir até nenhuma troca ocorrer",
                "Iniciar do primeiro elemento da lista",
                "Trocar se o da esquerda for maior",
                "Avançar para o próximo par",
            ],
            "correct_order": [2, 0, 3, 4, 1],
            "explanation": "Iniciar → comparar adjacentes → trocar se necessário → avançar → repetir até ordenado.",
        },
    ),
    Challenge(
        title="Algoritmo de Autenticação JWT",
        description="Ordene os passos do fluxo completo de autenticação usando JWT, do login até o acesso ao recurso protegido.",
        difficulty=2,
        category=ChallengeCategory.algorithm,
        type=ChallengeType.ordering,
        content={
            "items": [
                "Validar o token no servidor",
                "Usuário envia credenciais",
                "Acessar o recurso protegido",
                "Servidor gera e retorna o JWT",
                "Cliente armazena o JWT",
                "Cliente envia requisição com JWT no header",
            ],
            "correct_order": [1, 3, 4, 5, 0, 2],
            "explanation": "Credenciais → JWT gerado → armazenado → enviado na requisição → validado → acesso liberado.",
        },
    ),
    Challenge(
        title="Pipeline de Machine Learning",
        description="Ordene as etapas de um pipeline de treinamento de modelo de machine learning, do dado bruto ao modelo em produção.",
        difficulty=2,
        category=ChallengeCategory.algorithm,
        type=ChallengeType.ordering,
        content={
            "items": [
                "Treinar o modelo",
                "Coletar e armazenar dados brutos",
                "Avaliar métricas de desempenho",
                "Fazer deploy em produção",
                "Pré-processar e limpar os dados",
                "Selecionar e engenheirar features",
            ],
            "correct_order": [1, 4, 5, 0, 2, 3],
            "explanation": "Coletar → limpar → engenheirar features → treinar → avaliar → deploy.",
        },
    ),
    Challenge(
        title="Algoritmo de Consenso em Blockchain",
        description="Ordene as etapas do algoritmo de consenso Proof of Work, desde a criação de uma transação até ela ser confirmada na blockchain.",
        difficulty=3,
        category=ChallengeCategory.algorithm,
        type=ChallengeType.ordering,
        content={
            "items": [
                "Nós validam a solução e o bloco",
                "Transação é transmitida para a rede",
                "Bloco é adicionado à cadeia",
                "Mineradores competem resolvendo o hash",
                "Transação entra no mempool",
                "Minerador vencedor propõe o bloco",
            ],
            "correct_order": [1, 4, 3, 5, 0, 2],
            "explanation": "Transmitir → mempool → mineradores competem → vencedor propõe → rede valida → bloco adicionado.",
        },
    ),
    Challenge(
        title="Garbage Collection em JVM",
        description="Ordene as fases do algoritmo de Garbage Collection Generacional da JVM, do objeto criado até a memória liberada.",
        difficulty=3,
        category=ChallengeCategory.algorithm,
        type=ChallengeType.ordering,
        content={
            "items": [
                "Objetos sobreviventes são promovidos para Old Generation",
                "Objeto é alocado em Eden Space",
                "GC verifica referências ativas",
                "Minor GC ocorre quando Eden está cheio",
                "Memória de objetos mortos é liberada",
                "Objetos vivos são movidos para Survivor Space",
            ],
            "correct_order": [1, 3, 2, 5, 0, 4],
            "explanation": "Alocação em Eden → Eden cheio → Minor GC → verificar referências → sobreviventes em Survivor → promoção para Old → liberação.",
        },
    ),
]

# ── Insert ────────────────────────────────────────────────────────────────────
existing_challenges = db.query(Challenge).count()
existing_badges = db.query(Badge).count()

if existing_badges == 0:
    db.add_all(badges)
    print(f"✅ Inserted {len(badges)} badges")
else:
    print("⏭️  Badges already seeded")

if existing_challenges == 0:
    db.add_all(challenges)
    print(f"✅ Inserted {len(challenges)} challenges")
else:
    print("⏭️  Challenges already seeded")

db.commit()
db.close()
print("Done.")

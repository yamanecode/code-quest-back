import httpx

from app.core.config import settings

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
)


async def _call_gemini(prompt: str) -> str:
    params = {"key": settings.GEMINI_API_KEY}
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(GEMINI_URL, params=params, json=body)
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]


async def feedback_agent(
    challenge_title: str, challenge_description: str, answer: dict, is_correct: bool
) -> str:
    correct_str = "correta" if is_correct else "incorreta"
    prompt = f"""Você é um tutor de Pensamento Computacional. Responda em português, de forma curta e pedagógica (máximo 4 frases).

Desafio: {challenge_title}
Descrição: {challenge_description}
Resposta do estudante: {answer}
A resposta foi: {correct_str}

Explique o que o estudante acertou ou errou e por quê. Não dê a resposta diretamente se estiver errado — incentive o raciocínio."""
    return await _call_gemini(prompt)


async def tutor_agent(
    challenge_title: str, challenge_description: str, current_answer: dict
) -> str:
    prompt = f"""Você é um tutor socrático de Pensamento Computacional. Responda em português, com no máximo 3 frases.

Desafio: {challenge_title}
Descrição: {challenge_description}
Resposta atual do estudante: {current_answer}

O estudante está travado. Faça UMA pergunta guia que o ajude a pensar melhor — não dê a resposta."""
    return await _call_gemini(prompt)


async def generate_challenge(topic: str, challenge_type: str, difficulty: int) -> str:
    prompt = f"""Você é um professor de Pensamento Computacional. Crie UM desafio educacional simples em português.

Tópico: {topic}
Tipo: {challenge_type}
Dificuldade: {difficulty} (1=fácil/cotidiano, 2=médio, 3=difícil)

REGRAS OBRIGATÓRIAS:
- Retorne APENAS JSON puro, sem markdown, sem texto antes ou depois
- Descrição: máximo 2 frases simples
- Tipo 'steps': exatamente 3 etapas, linguagem direta ("O que é a entrada?")
- expected_keywords: MESMO número de listas que steps, palavras simples em minúsculo que o aluno naturalmente escreveria
- Tipo 'pattern': sequência numérica ou do cotidiano, resposta direta
- O problema deve ter conexão clara com tecnologia ou sistemas do mundo real (apps, sites, jogos, robôs, algoritmos)
- Evite problemas domésticos genéricos (organizar geladeira, limpar quarto)
- A descrição deve deixar claro POR QUE pensar computacionalmente resolve o problema
- Prefira contextos que estudantes de computação reconheceriam como relevantes
FORMATO:
{{"title":"...","description":"...","difficulty":{difficulty},"content":{{}}}}

Para 'steps': content={{"steps":[{{"label":"..."}}],"expected_keywords":[["palavra1","palavra2"]]}}
Para 'pattern': content={{"sequence":"...","answer":"...","explanation":"..."}}
"""
    return await _call_gemini(prompt)


async def generate_daily_challenge() -> str:
    prompt = """Você é um especialista em Pensamento Computacional criando um desafio educacional avançado para estudantes de computação. Sua tarefa é criar UM desafio mestre que integre os 4 pilares do Pensamento Computacional em um problema único e coeso.

Os 4 pilares são:
1. Decomposição - quebrar um problema complexo em partes menores
2. Reconhecimento de Padrões - identificar repetições, regularidades ou tendências
3. Abstração - focar no essencial, ignorar detalhes irrelevantes
4. Construção de Algoritmos - criar uma sequência lógica de passos para resolver

CONTEXTO DO PROBLEMA: O desafio deve ser sobre um sistema computacional real e relevante (ex: algoritmo de recomendação, sistema de detecção de fraudes, compressão de dados, roteamento de rede, sistema de busca). Deve ser desafiador mas solucionável por estudantes dedicados.

ESTRUTURA OBRIGATÓRIA — 4 etapas, uma por pilar, sobre o MESMO problema central:
- Etapa 1 (Decomposição): pedir ao aluno para identificar e separar os componentes/subproblemas
- Etapa 2 (Padrões): pedir para identificar padrões, repetições ou regularidades no problema
- Etapa 3 (Abstração): pedir para definir o que é essencial e o que pode ser ignorado
- Etapa 4 (Algoritmo): pedir para descrever os passos lógicos da solução

REGRAS PARA expected_keywords:
- Use palavras que um estudante naturalmente escreveria em português
- Se a etapa tem muitas respostas válidas (ex: decomposição com 6+ componentes possíveis), inclua 6-8 keywords
- Se a etapa é mais específica e tem resposta mais direta, inclua 3-4 keywords precisas
- Todas as keywords em minúsculo
- Inclua sinônimos e variações aceitáveis (ex: ["entrada", "input", "dados de entrada"])

REGRAS DE FORMATO:
- Retorne APENAS JSON puro, zero markdown, zero texto fora do JSON
- Descrição: 2-3 frases que contextualizem o problema claramente
- Labels das etapas: diretas e sem ambiguidade, começando com verbo (ex: "Identifique...", "Descreva...", "Liste...")

FORMATO EXATO:
{"title":"...","description":"...","difficulty":4,"category":"algorithm","type":"steps","is_daily":true,"content":{"steps":[{"label":"..."},{"label":"..."},{"label":"..."},{"label":"..."}],"expected_keywords":[["kw1","kw2","kw3"],["kw1","kw2"],["kw1","kw2","kw3","kw4"],["kw1","kw2","kw3"]]}}"""
    return await _call_gemini(prompt)

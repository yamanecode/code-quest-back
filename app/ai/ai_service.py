import httpx
from app.core.config import settings

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash:generateContent"
)


async def _call_gemini(prompt: str) -> str:
    params = {"key": settings.GEMINI_API_KEY}
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(GEMINI_URL, params=params, json=body)
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]


async def feedback_agent(challenge_title: str, challenge_description: str, answer: dict, is_correct: bool) -> str:
    correct_str = "correta" if is_correct else "incorreta"
    prompt = f"""Você é um tutor de Pensamento Computacional. Responda em português, de forma curta e pedagógica (máximo 4 frases).

Desafio: {challenge_title}
Descrição: {challenge_description}
Resposta do estudante: {answer}
A resposta foi: {correct_str}

Explique o que o estudante acertou ou errou e por quê. Não dê a resposta diretamente se estiver errado — incentive o raciocínio."""
    return await _call_gemini(prompt)


async def tutor_agent(challenge_title: str, challenge_description: str, current_answer: dict) -> str:
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
import os
import sys
import asyncio
import json
import logging
from dotenv import load_dotenv

# Configurar loop de eventos no Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

load_dotenv()

logging.basicConfig(level=logging.WARNING)  # Reduz verbosidade no terminal

# Usa o ChatOpenAI do LangChain (já instalado no venv)
from langchain_openai import ChatOpenAI
from pydantic import Field
from browser_use import Agent, Browser, BrowserProfile


# O browser-use v0.11.4 exige 'provider' e também faz setattr('ainvoke') no llm.
# extra='allow' permite que o Pydantic aceite qualquer atributo extra dinamicamente.
from pydantic import Field, ConfigDict

class ChatOpenAIWithProvider(ChatOpenAI):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra='allow')
    provider: str = Field(default="openai")


async def search_dimensions(query: str) -> list[dict]:
    email = os.getenv("DIMENSIONS_EMAIL")
    password = os.getenv("DIMENSIONS_PASSWORD")

    llm = ChatOpenAIWithProvider(
        model="gpt-4o",
        api_key=os.getenv("OPENAI_API_KEY"),
        temperature=0,
    )

    browser = Browser(
        browser_profile=BrowserProfile(
            headless=False,
        )
    )

    task = f"""
    Você é um assistente que vai navegar no site Dimensions.ai para buscar publicações científicas.

    PASSO 1 - NAVEGAÇÃO:
    - Acesse https://app.dimensions.ai/discover/publication
    - AGUARDE completamente o carregamento da página (pode levar até 20 segundos).

    PASSO 2 - LOGIN:
    - Procure e clique no botão "Sign in" ou "Login" ou "Entrar" que aparecer na página.
    - Se aparecer um campo de Email, digite: {email}
    - Clique em "Continue" ou "Next" ou "Próximo" após digitar o email.
    - Se aparecer um campo de Password/Senha, digite: {password}
    - Clique em "Sign in" ou "Log in" ou "Entrar" para confirmar.
    - AGUARDE o login completar e a página de pesquisa carregar.

    PASSO 3 - BUSCA:
    - Após estar logado, encontre a barra de pesquisa principal no topo da página.
    - Clique na barra de pesquisa.
    - Digite: {query}
    - Pressione Enter ou clique no botão de busca.
    - AGUARDE os resultados carregarem.

    PASSO 4 - EXTRAÇÃO:
    - Colete os dados dos 10 primeiros resultados visíveis.
    - Para cada resultado, extraia: Título, Autores, Ano e Fonte/Revista.

    PASSO 5 - RESULTADO:
    - Retorne APENAS um JSON válido, sem nenhum texto adicional:
    [{{"title": "...", "authors": "...", "year": "...", "source": "..."}}]
    """

    print(f"\n🤖 Agente iniciando busca por: '{query}'")
    print("📂 Abrindo navegador... (aguarde, o site é lento)\n")

    agent = Agent(
        task=task,
        llm=llm,
        browser=browser,
        max_failures=20,
        max_actions_per_step=10,
    )

    result = await agent.run()

    try:
        result_text = result.final_result()
        if not result_text:
            return []

        result_text = result_text.strip()
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0]
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0]

        return json.loads(result_text)
    except Exception as e:
        print(f"⚠️  Erro ao processar resultado: {e}")
        return []


async def main_cli():
    print("\n" + "="*45)
    print(" 🔬 Dimensions AI Scraper - v3")
    print("="*45 + "\n")

    while True:
        try:
            query = input("🔍 Termo de busca (ou 'sair'): ").strip()
        except EOFError:
            break

        if query.lower() in ['sair', 'exit', 'q', '']:
            print("👋 Encerrando.")
            break

        results = await search_dimensions(query)

        if results:
            print(f"\n✅ {len(results)} resultado(s) para '{query}':\n")
            for i, pub in enumerate(results, 1):
                print(f"  {i}. {pub.get('title', 'N/A')}")
                print(f"     👥 {pub.get('authors', 'N/A')} | 📅 {pub.get('year', 'N/A')} | 📰 {pub.get('source', 'N/A')}")
            print()
        else:
            print("\n❌ Nenhum resultado encontrado.\n")


if __name__ == "__main__":
    asyncio.run(main_cli())

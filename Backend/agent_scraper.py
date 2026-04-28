import os
import sys
import asyncio
import json
import logging
import re
from pathlib import Path
from dotenv import load_dotenv

# Configurar loop de eventos e codificação no Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv()

# Log para ver as ações do agente
logging.basicConfig(level=logging.INFO) 

from langchain_openai import ChatOpenAI
from pydantic import ConfigDict
from browser_use import Agent, Browser, BrowserProfile

class ChatOpenAIWithProvider(ChatOpenAI):
    model_config = ConfigDict(extra='allow')
    provider: str = "openai"
    model: str = "gpt-4o"

async def search_dimensions(query: str) -> list[dict]:
    email = os.getenv("DIMENSIONS_EMAIL")
    password = os.getenv("DIMENSIONS_PASSWORD")

    # Hack necessário para browser-use 0.12.6 reconhecer o provider
    llm = ChatOpenAIWithProvider(
        model="gpt-4o",
        api_key=os.getenv("OPENAI_API_KEY"),
        temperature=0,
    )

    # Configuração do Browser
    browser = Browser(
        headless=False,
        disable_security=True,
        highlight_elements=True,
        keep_alive=True
    )

    task = f"""
    Objetivo: Extrair publicações de Dimensions.ai sobre '{query}'.
    
    FLUXO OBRIGATÓRIO:
    1. Vá para: https://app.dimensions.ai/discover/publication
    2. LOGIN: Procure o botão 'Sign in'. 
       Use Email: {email}
       Use Senha: {password}
    3. PESQUISA: Busque por '{query}'.
    4. EXTRAÇÃO: Pegue Título, Autores e Resumo (se disponível) dos 5 primeiros resultados.
    5. FINALIZAÇÃO: Retorne os dados em formato JSON estruturado: {{"results": [{{"title": "...", "authors": "...", "snippet": "..."}}]}}
    """

    print(f"\n🚀 Agente [v3.5] iniciando busca por: '{query}'")

    agent = Agent(
        task=task,
        llm=llm,
        browser=browser
    )

    history = await agent.run(max_steps=25)

    try:
        final_text = history.final_result()
        print(f"📄 Resultado Bruto: {final_text}")
        
        # Tenta capturar JSON
        json_pattern = r'\{.*\}'
        match = re.search(json_pattern, final_text, re.DOTALL)
        if match:
            data = json.loads(match.group())
            results = data.get("results", [data])
            if isinstance(results, dict) and "results" not in results:
                results = [results]
            
            # Salva os resultados para uso posterior
            with open("scraped_data.json", "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            
            return results
        
        return [{"info": final_text}] if final_text else []

    except Exception as e:
        print(f"⚠️  Erro no processamento: {e}")
        return []

async def main_cli():
    print("\n" + "="*45)
    print(" 🔬 Dimensions AI Scraper - v3.5 (0.12.6)")
    print("="*45 + "\n")

    while True:
        try:
            query = input("🔍 Termo de busca (ou 'sair'): ").strip()
        except EOFError: break

        if query.lower() in ['sair', 'exit', 'q', '']: break

        results = await search_dimensions(query)

        if results:
            print(f"\n✅ Resultados salvos em 'scraped_data.json'")
            print(json.dumps(results[:2], indent=2, ensure_ascii=False))
        else:
            print("\n❌ Sem resultados.")

if __name__ == "__main__":
    asyncio.run(main_cli())

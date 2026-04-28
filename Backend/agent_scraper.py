import os
import sys
import asyncio
import json
import logging
import re
from dotenv import load_dotenv

# Configurar loop de eventos e codificação no Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv()

# ─────────────────────────────────────────────
#  MOTOR 1 — PLAYWRIGHT
# ─────────────────────────────────────────────
async def search_with_playwright(query: str) -> list[dict]:
    from playwright.async_api import async_playwright

    email = os.getenv("DIMENSIONS_EMAIL")
    password = os.getenv("DIMENSIONS_PASSWORD")
    base_url = "https://app.dimensions.ai/discover/publication"
    auth_file = "auth_state.json"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/119.0.0.0 Safari/537.36"
        )

        if os.path.exists(auth_file):
            context = await browser.new_context(storage_state=auth_file, user_agent=user_agent)
        else:
            context = await browser.new_context(user_agent=user_agent)

        page = await context.new_page()

        try:
            print(f"  🌐 Navegando para {base_url}...")
            await page.goto(base_url, wait_until="domcontentloaded", timeout=100000)
            # Verifica se precisamos de login
            is_login = "login" in page.url or "auth" in page.url
            user_field_visible = await page.locator("input[name='username'], input#username").is_visible()

            if is_login or user_field_visible:
                print("  🔐 Login necessário. Preenchendo credenciais...")
                user_field = page.locator("input[name='username'], input#username").first
                await user_field.fill(email)

                btn_next = page.locator("button:has-text('Continue'), button:has-text('Next'), button[type='submit']").first
                await btn_next.click()
                await asyncio.sleep(2)

                await page.wait_for_selector("input[name='password'], input#password", timeout=15000)
                await page.locator("input[name='password'], input#password").first.fill(password)

                btn_login = page.locator("button:has-text('Log in'), button:has-text('Sign in'), button[type='submit']").first
                await btn_login.click()

                # Aguarda redirecionamento final (SSO pode fechar/reabrir páginas)
                await asyncio.sleep(5)
                pages = context.pages
                page = pages[-1]  # Pega a página mais recente após o redirecionamento
                await page.wait_for_load_state("domcontentloaded", timeout=45000)
                await page.context.storage_state(path=auth_file)
                print("  ✅ Login bem-sucedido!")
            else:
                print("  ✅ Já autenticado.")

            if "discover" not in page.url:
                await page.goto(base_url, wait_until="domcontentloaded")

            print(f"  🔍 Buscando por: '{query}'...")
            search_bar = page.locator("textarea[aria-label='Type the query'], input[placeholder*='Search']").first
            await search_bar.fill(query)
            await search_bar.press("Enter")

            await page.wait_for_selector(".results-list, .publication-row", timeout=20000)
            await asyncio.sleep(2)

            results = []
            rows = await page.locator(".publication-row").all()
            for row in rows[:10]:
                title_elem = row.locator("h3.title, .title")
                authors_elem = row.locator(".authors")
                title = await title_elem.inner_text() if await title_elem.count() > 0 else "N/A"
                authors = await authors_elem.inner_text() if await authors_elem.count() > 0 else "N/A"
                results.append({"title": title.strip(), "authors": authors.strip()})

            return results

        except Exception as e:
            print(f"  ❌ Erro Playwright: {e}")
            return []
        finally:
            await context.close()


# ─────────────────────────────────────────────
#  MOTOR 2 — BROWSER-USE (IA)
# ─────────────────────────────────────────────
async def search_with_browser_use(query: str) -> list[dict]:
    logging.basicConfig(level=logging.INFO)

    from langchain_openai import ChatOpenAI
    from pydantic import ConfigDict, Field
    from browser_use import Agent, Browser, BrowserProfile

    class ChatOpenAIWithProvider(ChatOpenAI):
        model_config = ConfigDict(extra='allow')
        provider: str = "openai"
        # Declara 'model' explicitamente para o browser-use acessar via llm.model
        model: str = Field(default="gpt-4o")

    email = os.getenv("DIMENSIONS_EMAIL")
    password = os.getenv("DIMENSIONS_PASSWORD")

    llm = ChatOpenAIWithProvider(
        model="gpt-4o",
        api_key=os.getenv("OPENAI_API_KEY"),
        temperature=0,
    )

    browser = Browser(
        browser_profile=BrowserProfile(headless=False)
    )

    task = f"""
    Objetivo: Extrair publicações científicas do site Dimensions.ai.

    PASSO 1 - Acesse: https://app.dimensions.ai/discover/publication
              Aguarde a página carregar completamente.

    PASSO 2 - Faça login:
              - Clique no botão "Sign in".
              - Digite o Email: {email}
              - Clique em "Continue" ou "Next".
              - Digite a Senha: {password}
              - Clique em "Sign in" / "Log in".
              - Aguarde redirecionar para a página de pesquisa.

    PASSO 3 - Pesquise por: "{query}"
              - Clique na barra de busca e digite o termo.
              - Pressione Enter.
              - Aguarde os resultados carregarem.

    PASSO 4 - Extraia Título, Autores, Ano e Fonte dos 10 primeiros resultados.

    PASSO 5 - Retorne APENAS JSON válido:
    [{{"title": "...", "authors": "...", "year": "...", "source": "..."}}]
    """

    print(f"  🤖 Agente IA iniciando busca por: '{query}'")

    agent = Agent(
        task=task,
        llm=llm,
        browser=browser,
        max_failures=5,
        max_actions_per_step=5,
    )

    history = await agent.run(max_steps=30)

    try:
        final_text = history.final_result()
        if not final_text:
            return []

        final_text = final_text.strip()
        if "```json" in final_text:
            final_text = final_text.split("```json")[1].split("```")[0]
        elif "```" in final_text:
            final_text = final_text.split("```")[1].split("```")[0]

        # Tenta parsear como lista diretamente
        if final_text.strip().startswith("["):
            return json.loads(final_text)

        # Tenta extrair JSON com regex
        match = re.search(r'\[.*\]', final_text, re.DOTALL)
        if match:
            return json.loads(match.group())

        return []

    except Exception as e:
        print(f"  ⚠️  Erro ao processar resultado: {e}")
        return []


# ─────────────────────────────────────────────
#  CLI PRINCIPAL COM MENU DE SELEÇÃO
# ─────────────────────────────────────────────
def selecionar_motor() -> str:
    print("\n" + "═"*50)
    print("  🔬 Dimensions AI Scraper")
    print("═"*50)
    print("\n  Selecione a ferramenta de scraping:\n")
    print("  1. Playwright  (rápido, determinístico)")
    print("  2. Browser-Use (IA, contorna CAPTCHAs)")
    print()

    while True:
        try:
            escolha = input("  Opção (1 ou 2): ").strip()
        except EOFError:
            return "1"

        if escolha == "1":
            print("\n  ✅ Motor selecionado: Playwright\n" + "─"*50)
            return "playwright"
        elif escolha == "2":
            print("\n  ✅ Motor selecionado: Browser-Use (IA)\n" + "─"*50)
            return "browser_use"
        else:
            print("  ⚠️  Opção inválida. Digite 1 ou 2.")


async def main_cli():
    motor = selecionar_motor()

    while True:
        try:
            query = input("\n🔍 Termo de busca (ou 'sair'): ").strip()
        except EOFError:
            break

        if query.lower() in ['sair', 'exit', 'q', '']:
            print("👋 Encerrando.")
            break

        print()
        if motor == "playwright":
            results = await search_with_playwright(query)
        else:
            results = await search_with_browser_use(query)

        if results:
            # Salva JSON
            with open("scraped_data.json", "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)

            print(f"\n✅ {len(results)} resultado(s) para '{query}':\n")
            for i, pub in enumerate(results, 1):
                print(f"  {i}. {pub.get('title', 'N/A')}")
                authors = pub.get('authors', pub.get('author', 'N/A'))
                year = pub.get('year', '')
                source = pub.get('source', '')
                details = " | ".join(filter(None, [authors, year, source]))
                print(f"     {details}")
            print(f"\n  💾 Resultados salvos em 'scraped_data.json'")
        else:
            print("\n❌ Nenhum resultado encontrado.")


if __name__ == "__main__":
    asyncio.run(main_cli())

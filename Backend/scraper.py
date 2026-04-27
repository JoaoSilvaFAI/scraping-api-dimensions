import os
import asyncio
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Page, BrowserContext
from dotenv import load_dotenv

load_dotenv()

class DimensionsScraper:
    def __init__(self):
        self.email = os.getenv("DIMENSIONS_EMAIL")
        self.password = os.getenv("DIMENSIONS_PASSWORD")
        self.base_url = "https://app.dimensions.ai/discover/publication"
        self.auth_file = "auth_state.json"

    async def get_browser_context(self, playwright) -> BrowserContext:
        browser = await playwright.chromium.launch(headless=False)
        # User-Agent real para evitar bloqueios
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        
        # Use storage state if it exists to stay logged in
        if os.path.exists(self.auth_file):
            context = await browser.new_context(
                storage_state=self.auth_file,
                user_agent=user_agent
            )
        else:
            context = await browser.new_context(user_agent=user_agent)
        return context

    async def login_if_needed(self, page: Page):
        print(f"Navegando para {self.base_url}...")
        try:
            # Usamos domcontentloaded para ser mais rápido e evitar timeouts de scripts de terceiros
            await page.goto(self.base_url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(2) # Pequena pausa para carregar elementos dinâmicos
        except Exception as e:
            print(f"Aviso na navegação inicial: {str(e)}")

        # Verifica se precisamos de login
        is_login_page = "login" in page.url or "auth" in page.url
        user_field_visible = await page.locator("input[name='username'], input#username").is_visible()

        if is_login_page or user_field_visible:
            print("Login necessário. Preenchendo credenciais...")
            
            # Tenta preencher o usuário
            user_field = page.locator("input[name='username'], input#username").first
            await user_field.fill(self.email)
            
            # Clica em Continuar/Next
            btn_next = page.locator("button:has-text('Continue'), button:has-text('Next'), button[type='submit']").first
            await btn_next.click()
            await asyncio.sleep(2)
            
            # Aguarda e preenche a senha
            print("Aguardando campo de senha...")
            await page.wait_for_selector("input[name='password'], input#password", timeout=15000)
            await page.locator("input[name='password'], input#password").first.fill(self.password)
            
            # Clique final no login
            btn_login = page.locator("button:has-text('Log in'), button:has-text('Sign in'), button[type='submit']").first
            await btn_login.click()
            
            # Aguarda o redirecionamento de volta
            print("Finalizando autenticação...")
            await page.wait_for_url(lambda url: "discover" in url or "publication" in url, timeout=45000)
            
            # Salva o estado para futuras sessões
            await page.context.storage_state(path=self.auth_file)
            print("Login bem-sucedido! Estado salvo.")
        else:
            print("Já autenticado ou página de login não detectada.")

    async def search(self, query: str, search_type: str = "publication") -> List[Dict]:
        print(f"\n--- Iniciando busca para: {query} ---")
        async with async_playwright() as p:
            context = await self.get_browser_context(p)
            try:
                page = await context.new_page()
                await self.login_if_needed(page)
                
                print(f"Executando pesquisa no site...")
                if "discover" not in page.url:
                    await page.goto(self.base_url, wait_until="domcontentloaded")

                # Preenche a barra de busca
                search_bar = page.locator("textarea[aria-label='Type the query'], input[placeholder*='Search']").first
                await search_bar.fill(query)
                await search_bar.press("Enter")
                
                print("Aguardando resultados (pode levar alguns segundos)...")
                await page.wait_for_selector(".results-list, .publication-row", timeout=20000)
                await asyncio.sleep(2) # Garante que a lista renderizou
                
                # Extração
                results = []
                rows = await page.locator(".publication-row").all()
                
                for row in rows[:10]:
                    title_elem = row.locator("h3.title, .title")
                    authors_elem = row.locator(".authors")
                    
                    title = await title_elem.inner_text() if await title_elem.count() > 0 else "Sem título"
                    authors = await authors_elem.inner_text() if await authors_elem.count() > 0 else "Sem autores"
                    
                    results.append({
                        "title": title.strip(),
                        "authors": authors.strip()
                    })
                
                return results

            except Exception as e:
                print(f"ERRO: {str(e)}")
                return []
            finally:
                await context.close()

async def main_cli():
    import sys
    # Configura o loop para Windows se rodar direto
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    scraper = DimensionsScraper()
    print("\n=== Dimensions.ai Scraper CLI ===")
    
    while True:
        query = input("\nDigite o termo de busca (ou 'sair' para encerrar): ")
        if query.lower() in ['sair', 'exit', 'q']:
            break
            
        results = await scraper.search(query)
        
        if results:
            print(f"\nEncontrados {len(results)} resultados:")
            for i, res in enumerate(results, 1):
                print(f"{i}. {res['title']}")
                print(f"   Autores: {res['authors']}\n")
        else:
            print("\nNenhum resultado encontrado ou erro na busca.")

if __name__ == "__main__":
    asyncio.run(main_cli())

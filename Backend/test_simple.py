import os
import sys
import asyncio
import logging
from dotenv import load_dotenv

# Configurar loop de eventos e codificação no Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv()
logging.basicConfig(level=logging.INFO) 

from langchain_openai import ChatOpenAI
from browser_use import Agent, Browser

async def test_agent():
    llm = ChatOpenAI(model="gpt-4o", api_key=os.getenv("OPENAI_API_KEY"))
    # Browser-use expects a provider attribute
    llm.provider = "openai" 
    
    browser = Browser(headless=False)
    agent = Agent(
        task="Acesse google.com e me diga o título da página.",
        llm=llm,
        browser=browser
    )
    await agent.run()

if __name__ == "__main__":
    asyncio.run(test_agent())

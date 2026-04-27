import os
import sys
import asyncio

# CRÍTICO: Deve ser definido antes de qualquer outra importação no Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    print("--- Loop Policy set to Proactor (Windows) ---")

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from scraper import DimensionsScraper
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="Dimensions.ai Scraper API")

# Configuração de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, especifique a URL do frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

scraper = DimensionsScraper()

class SearchRequest(BaseModel):
    query: str
    search_type: Optional[str] = "publication"

class SearchResult(BaseModel):
    title: str
    authors: str
    source: str
    date: str

@app.get("/")
async def root():
    return {"message": "Dimensions.ai Scraper API is running"}

@app.post("/search", response_model=List[SearchResult])
async def perform_search(request: SearchRequest):
    try:
        results = await scraper.search(request.query, request.search_type)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status")
async def status():
    return {"status": "ok", "scraper": "ready"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.bot import router as bot_router
from api.routes.campaigns import router as campaigns_router
from api.routes.dm_prep import router as dm_prep_router
from api.routes.link import router as link_router
from api.routes.sessions import router as sessions_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title="Tavern Recap Bot API",
    description="REST API for the D&D Session Bot — serves data to the Lovable web dashboard",
    version="1.0.0",
)

# Allow Lovable frontend to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://tavernrecap.com",
        "https://www.tavernrecap.com",
        "https://api.tavernrecap.com",
        "https://kowjiumihltsgebyzgox.supabase.co",
        "http://localhost:5173",  # Local Vite dev
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
)

app.include_router(bot_router, prefix="/api/bot", tags=["Bot"])
app.include_router(campaigns_router, prefix="/api/campaigns", tags=["Campaigns"])
app.include_router(dm_prep_router, prefix="/api/dm-prep", tags=["DM Prep"])
app.include_router(link_router, prefix="/api/link", tags=["Account Linking"])
app.include_router(sessions_router, prefix="/api/sessions", tags=["Sessions"])


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "tavern-recap-bot-api"}


def run():
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    run()

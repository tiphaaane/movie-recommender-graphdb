"""Run Apolline's AI endpoints as a standalone FastAPI app."""

from fastapi import FastAPI

from app.agent.api import router as agent_router

app = FastAPI(
    title="Movie Recommender — AI Assistant",
    description="Standalone development application for the AI component.",
    version="0.1.0",
)

app.include_router(agent_router)
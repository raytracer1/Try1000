"""Try1000 Backend — FastAPI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, teams, tactics, simulation, analytics, agent

app = FastAPI(title="Try1000 API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(teams.router, prefix="/api/v1/teams", tags=["teams"])
app.include_router(tactics.router, prefix="/api/v1/tactics", tags=["tactics"])
app.include_router(simulation.router, prefix="/api/v1", tags=["simulation"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["analytics"])
app.include_router(agent.router, prefix="/api/v1/agent", tags=["agent"])


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}

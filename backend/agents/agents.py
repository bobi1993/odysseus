"""Agent registry — list, create, manage AI agents."""

from fastapi import APIRouter

router = APIRouter()

AGENTS = [
    {
        "id": "hermes-main",
        "name": "Luna",
        "role": "Primary Agent",
        "personality": "Direct, security-conscious, comprehensive.",
        "specialty": "General-purpose AI orchestration",
        "status": "active",
        "icon": "🌙",
        "color": "#58a6ff",
    },
    {
        "id": "researcher",
        "name": "Scout",
        "role": "Research Agent",
        "personality": "Thorough, analytical, source-driven.",
        "specialty": "Deep research, web search, arXiv",
        "status": "idle",
        "icon": "🔍",
        "color": "#3fb950",
    },
    {
        "id": "vr-curator",
        "name": "Curator",
        "role": "VR Video Agent",
        "personality": "Organized, detail-oriented.",
        "specialty": "Video library management, face recognition, tagging",
        "status": "idle",
        "icon": "🎬",
        "color": "#f78166",
    },
]


@router.get("/")
async def list_agents():
    """List all registered agents."""
    return {"agents": AGENTS}


@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    """Get agent details."""
    for agent in AGENTS:
        if agent["id"] == agent_id:
            return agent
    return {"error": "Agent not found"}

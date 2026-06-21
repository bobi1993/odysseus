"""
Odysseus Orchestra Routes — REST API for the multi-agent crew system.

Provides:
  - GET /api/orchestra — list all crew members
  - GET /api/orchestra/crew/<crew_id> — get specific crew member
  - POST /api/orchestra/chat — route message to a crew member
"""

from fastapi import APIRouter


def setup_orchestra_routes() -> APIRouter:
    router = APIRouter()

    @router.get("/api/orchestra")
    def list_crew():
        """List all orchestra crew members."""
        from core.database import CrewMember, SessionLocal
        db = SessionLocal()
        try:
            members = db.query(CrewMember).filter(
                CrewMember.is_active == True  # noqa: E712
            ).order_by(CrewMember.sort_order).all()

            return {
                "crew": [
                    {
                        "id": m.id,
                        "name": m.name,
                        "user_name": m.user_name,
                        "model": m.model,
                        "endpoint_url": m.endpoint_url,
                        "is_default_assistant": m.is_default_assistant,
                        "sort_order": m.sort_order,
                        "personality_preview": (m.personality or "")[:100] + "...",
                    }
                    for m in members
                ],
                "total": len(members),
            }
        finally:
            db.close()

    @router.get("/api/orchestra/crew/{crew_id}")
    def get_crew_member(crew_id: str):
        """Get details of a specific crew member."""
        import json
        from core.database import CrewMember, SessionLocal
        db = SessionLocal()
        try:
            member = db.query(CrewMember).filter(CrewMember.id == crew_id).first()
            if not member:
                return {"error": "Crew member not found"}
            return {
                "id": member.id,
                "name": member.name,
                "user_name": member.user_name,
                "model": member.model,
                "endpoint_url": member.endpoint_url,
                "personality": member.personality,
                "enabled_tools": json.loads(member.enabled_tools) if member.enabled_tools else [],
                "is_default_assistant": member.is_default_assistant,
                "sort_order": member.sort_order,
            }
        finally:
            db.close()

    @router.post("/api/orchestra/chat")
    def chat_with_crew(body: dict):
        """Route a message to a specific crew member."""
        from core.database import CrewMember, SessionLocal
        db = SessionLocal()
        try:
            crew_id = body.get("crew_id")
            message = body.get("message", "")

            if not crew_id or not message:
                return {"error": "crew_id and message required"}

            member = db.query(CrewMember).filter(CrewMember.id == crew_id).first()
            if not member:
                return {"error": "Crew member not found"}

            return {
                "crew_id": member.id,
                "name": member.name,
                "model": member.model,
                "endpoint_url": member.endpoint_url,
                "personality": member.personality,
                "message": message,
                "status": "routed",
            }
        finally:
            db.close()

    return router

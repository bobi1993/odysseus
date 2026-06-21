#!/usr/bin/env python3
"""
Odysseus Orchestra API — REST endpoints for the crew system.

Provides:
  - GET /api/orchestra — list all crew members and their status
  - POST /api/orchestra/chat — route a message to the appropriate crew member
  - GET /api/orchestra/crew/<id> — get a specific crew member's details
"""

import os
import sys
import json

from dotenv import load_dotenv

ODYSSEUS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ODYSSEUS_DIR)
load_dotenv(os.path.join(ODYSSEUS_DIR, ".env"))


def create_orchestra_routes(app, db):
    """Register orchestra routes on the Flask/FastAPI app."""

    @app.get("/api/orchestra")
    def list_crew():
        """List all orchestra crew members."""
        from core.database import CrewMember
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

    @app.get("/api/orchestra/crew/{crew_id}")
    def get_crew_member(crew_id: str):
        """Get details of a specific crew member."""
        from core.database import CrewMember
        member = db.query(CrewMember).filter(CrewMember.id == crew_id).first()
        if not member:
            return {"error": "Crew member not found"}, 404
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

    @app.post("/api/orchestra/chat")
    def chat_with_crew(body: dict):
        """Route a message to a specific crew member."""
        from core.database import CrewMember

        crew_id = body.get("crew_id")
        message = body.get("message", "")

        if not crew_id or not message:
            return {"error": "crew_id and message required"}, 400

        member = db.query(CrewMember).filter(CrewMember.id == crew_id).first()
        if not member:
            return {"error": "Crew member not found"}, 404

        return {
            "crew_id": member.id,
            "name": member.name,
            "model": member.model,
            "endpoint_url": member.endpoint_url,
            "personality": member.personality,
            "message": message,
            "status": "routed",
        }

    return app

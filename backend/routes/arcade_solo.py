"""routes.arcade_solo — single-player arcade high scores."""
from datetime import datetime, timezone
from typing import Any, Callable, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

GAMES = {"freight-runner", "load-stacker", "dock-breaker"}


class ScoreIn(BaseModel):
    game: str = Field(..., max_length=40)
    score: int = Field(..., ge=0, le=10_000_000)


def build_arcade_solo_router(*, db, get_current_user: Callable) -> APIRouter:
    router = APIRouter(prefix="/arcade/solo", tags=["arcade-solo"])

    @router.post("/score")
    async def post_score(payload: ScoreIn, user=Depends(get_current_user)) -> Dict[str, Any]:
        if payload.game not in GAMES:
            raise HTTPException(status_code=400, detail="Unknown game")
        key = {"game": payload.game, "user_id": user.user_id}
        existing = await db.arcade_solo_scores.find_one(key, {"_id": 0})
        best = max(payload.score, (existing or {}).get("score", 0))
        await db.arcade_solo_scores.update_one(key, {"$set": {
            "score": best, "name": user.name,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }}, upsert=True)
        return {"ok": True, "best": best, "is_new_best": best == payload.score and payload.score > (existing or {}).get("score", -1)}

    @router.get("/highscores")
    async def highscores(game: str, user=Depends(get_current_user)) -> Dict[str, Any]:
        if game not in GAMES:
            raise HTTPException(status_code=400, detail="Unknown game")
        top = await db.arcade_solo_scores.find({"game": game}, {"_id": 0}).sort("score", -1).to_list(10)
        mine = await db.arcade_solo_scores.find_one({"game": game, "user_id": user.user_id}, {"_id": 0})
        return {"top": top, "my_best": (mine or {}).get("score", 0)}

    return router

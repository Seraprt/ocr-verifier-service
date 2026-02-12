from pydantic import BaseModel
from typing import Optional, Dict, List

class SideStats(BaseModel):
    userName: str
    goals: Optional[int] = None
    shotsOnTarget: Optional[int] = None
    possession: Optional[int] = None
    penalties: Optional[int] = None  # PK goals if present
    raw: Dict[str, str] = {}

class ParsedResult(BaseModel):
    game: str
    teamSize: int
    sideA: SideStats
    sideB: SideStats
    meta: Dict[str, str]
    coherence: Dict[str, List[str]]
    winner: Optional[str] = None
    tieBreak: Optional[str] = None
    confidence: float

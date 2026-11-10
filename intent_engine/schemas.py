from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

@dataclass
class UnderstandingResult:
    intent: str
    intents: List[str]
    entities: Dict[str, Any]
    is_off_topic: bool
    is_complete: bool
    is_vague: bool
    missing_fields: List[str] = field(default_factory=list)
    follow_up_question: Optional[str] = None
    confidence: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class Reminder:
    user_id: int
    channel_id: int
    remind_at: str
    message: str
    repeat: Optional[bool] = False
    doc_id: Optional[int] = None
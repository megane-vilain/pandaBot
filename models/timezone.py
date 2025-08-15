from dataclasses import dataclass
from typing import Optional


@dataclass
class Timezone:
    user_id: int
    timezone: str
    doc_id: Optional[int] = None
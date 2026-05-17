from dataclasses import dataclass
from io import BytesIO
from typing import Optional

@dataclass
class GatheringReminder:
    user_id: int
    channel_id: int
    item_id: int
    item_name: str
    et_hours: set[int]
    duration_et_hours: int
    alert_before_minutes: int
    enable: bool
    last_notification_ts: str
    doc_id: Optional[int] = None

@dataclass()
class GatheringNode:
    id: int
    name: str
    coordinates: list[int]
    type: int
    node_duration: int
    time: set[int]
    time_formatted: str
    map_output: Optional[BytesIO] = None

@dataclass
class GatheringItem:
    id: int
    name: str
    name_lower: str
    description: str
    map:str
    zone: str
    node: GatheringNode
    icon_id: int
    alert: Optional[GatheringReminder] = None
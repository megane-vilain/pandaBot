from dataclasses import dataclass
from typing import Optional

@dataclass()
class GatheringNode:
    id: int
    name: str
    coordinates: set[int]
    type: int
    node_duration: int
    time: set[int]
    time_formatted: str

@dataclass
class GatheringItem:
    id: int
    name: str
    description: str
    map:str
    zone: str
    node: Optional[GatheringNode]
    icon: int

@dataclass
class GatheringItemConfig:
    id: int
    name: str
    name_lower:str
    map:str

    def __init__(self, item_id: int, name: str, zone_map: str):
        self.id = item_id
        self.name = name
        self.name_lower = name.lower()
        self.map = zone_map

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




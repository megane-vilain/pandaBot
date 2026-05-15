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





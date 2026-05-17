from utils.et_time import format_et_hours
from models import GatheringItem, GatheringNode
import json

GATHERING_ITEMS_PATH = "gathering_items.json"

def load_gathering_items(
    path: str = GATHERING_ITEMS_PATH,
) -> tuple[list[GatheringItem], dict[int, GatheringItem]]:
    """
    Load gathering items from JSON file.

    Returns:
        (items_list, items_by_id)
    """
    with open(path, encoding="utf-8") as f:
        raw: list[dict] = json.load(f)

    items = []
    for entry in raw:
        et_times = entry["et_times"]

        node = GatheringNode(
            id=entry["node_id"],
            name=entry["node_name"],
            coordinates=entry["node_coordinates"],
            type=entry["node_type"],
            node_duration=entry["duration_et_hours"],
            time=et_times,
            time_formatted=format_et_hours(et_times),
        )

        item = GatheringItem(
            id=entry["item_id"],
            name=entry["name"],
            name_lower=entry["name"].lower(),
            description=entry["description"],
            map=entry["zone_map"],
            zone=entry["zone_name"],
            node=node,
            icon_id=entry["icon_id"],
        )

        items.append(item)

    items_by_id = {item.id: item for item in items}
    return items, items_by_id
from garlandtools import GarlandTools
from et_time import format_et_hours
from models import GatheringItem, GatheringNode
import json

GATHERING_ITEMS_PATH = "gathering_items.json"

def get_gathering_item(api: GarlandTools, item_id: int, map_path: str):
    item_response = api.item(item_id)
    item_json = item_response.json()
    map_name = map_path.split("/", 1)[1]

    node_partial = next(
        p for p in item_json["partials"]
        if p["type"] == "node"
    )
    node_type = node_partial["obj"]["lt"]

    node_response = api.node(node_partial['id'])
    node_json = node_response.json()

    gathering_node = node_json["node"]

    if "Ephemeral" == node_type:
        node_duration = 4
    else:
        node_duration = 2

    gathering_times = gathering_node["time"]
    gathering_times = sorted(gathering_times)

    if len(gathering_times) == 1:
        time_formatted = f"{gathering_times[0]} ET"
    else:
        time_formatted = f"{gathering_times[0]} - {gathering_times[1]} ET"

    gathering_node = GatheringNode(
        name = gathering_node["name"],
        id = gathering_node["id"],
        coordinates = gathering_node["coords"],
        type = gathering_node['type'],
        time = gathering_node["time"],
        time_formatted = time_formatted,
        node_duration = node_duration

    )

    item = item_json["item"]
    gathering_item = GatheringItem(
        id = item["id"],
        name = item["name"],
        description = item["description"],
        icon_id= item["icon"],
        map = map_path,
        zone = map_name,
        node = gathering_node
    )

    return gathering_item

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
            time=set(et_times),
            time_formatted=format_et_hours(et_times),
        )

        item = GatheringItem(
            id=entry["item_id"],
            name=entry["name"],
            description=entry["description"],
            map=entry["zone_map"],
            zone=entry["zone_name"],
            node=node,
            icon_id=entry["icon_id"],
        )

        items.append(item)

    items_by_id = {item.id: item for item in items}
    return items, items_by_id
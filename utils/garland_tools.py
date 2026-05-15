from garlandtools import GarlandTools
from models import GatheringItem, GatheringNode

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
        icon = item["icon"],
        map = map_path,
        zone = map_name,
        node = gathering_node
    )

    return gathering_item
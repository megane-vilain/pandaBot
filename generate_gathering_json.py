import json
import time
from garlandtools import GarlandTools

gt = GarlandTools()


def resolve_map_path(zone_id: int, location_index: dict) -> str | None:
    zone = location_index.get(str(zone_id))
    if zone is None:
        return None

    parent_id = zone.get("parentId")
    if parent_id is None or parent_id == zone_id:
        return zone["name"]

    parent = location_index.get(str(parent_id))
    if parent is None:
        return zone["name"]

    return f"{parent['name']}/{zone['name']}"


def main():
    print("Fetching data.json...")
    data = gt.data().json()
    location_index = data["locationIndex"]

    print("Fetching all nodes...")
    all_nodes = gt.nodes().json()

    timed_nodes = [n for n in all_nodes["browse"] if "ti" in n]
    print(f"Found {len(timed_nodes)} timed nodes out of {len(all_nodes['browse'])} total")

    results = []
    seen_item_ids: set[int] = set()
    duplicate_item_ids: set[int] = set()

    for i, partial in enumerate(timed_nodes):
        node_id = partial["i"]
        zone_id = partial.get("z")
        map_path = resolve_map_path(zone_id, location_index) if zone_id else None

        print(f"[{i+1}/{len(timed_nodes)}] Fetching node {node_id}...")
        node_data = gt.node(node_id).json()
        node = node_data["node"]

        for item_entry in node.get("items", []):
            item_id = item_entry["id"]

            if item_id in seen_item_ids:
                duplicate_item_ids.add(item_id)
            else:
                seen_item_ids.add(item_id)

            print(f"  Fetching item {item_id}...")
            item_data = gt.item(item_id).json()["item"]
            time.sleep(0.5)

            results.append({
                "item_id": item_id,
                "name": item_data.get("name", f"Unknown ({item_id})"),
                "description": item_data.get("description", ""),
                "icon_id": item_data.get("icon"),
                "node_id": node_id,
                "node_name": node.get("name"),
                "node_type": node.get("type"),
                "node_coordinates": node.get("coords", []),
                "zone_id": zone_id,
                "zone_map": map_path,
                "zone_name": location_index.get(str(zone_id), {}).get("name"),
                "et_times": node.get("time", []),
                "duration_et_hours": node.get("uptime", 120) // 60,
                "limit_type": node.get("limitType"),
            })

        time.sleep(0.5)

    # Strip duplicates from results
    results = [r for r in results if r["item_id"] not in duplicate_item_ids]

    print(f"\nRemoved {len(duplicate_item_ids)} items found on multiple nodes:")
    for item_id in sorted(duplicate_item_ids):
        # Find the name from any result before stripping (already removed, so check seen)
        print(f"  - item {item_id}")

    with open("gathering_items.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nDone. {len(results)} items written to gathering_items.json")


if __name__ == "__main__":
    main()
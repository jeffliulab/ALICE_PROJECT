"""Patch Tiled JSON tileset image paths for our directory structure."""
import json

d = json.load(open("frontend/public/assets/maps/the_ville_jan7.json"))
remap = {
    "map_assets/cute_rpg_word_VXAce/tilesets/": "../tilesets/cute_rpg/",
    "map_assets/v1/": "../tilesets/v1/",
    "map_assets/blocks/": "../tilesets/blocks/",
}
for ts in d["tilesets"]:
    img = ts.get("image", "")
    for old, new in remap.items():
        if old in img:
            ts["image"] = img.replace(old, new)
            break
with open("frontend/public/assets/maps/the_ville_jan7.json", "w") as f:
    json.dump(d, f)
print("Patched tileset paths in Tiled JSON")

import json
import os
import sys
from concurrent import futures
import grpc

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(BASE_DIR), "generated", "catalog"))

import catalog_pb2
import catalog_pb2_grpc

DATA_PATH = os.path.join(BASE_DIR, "data", "objects.json")
FAVORITES_PATH = os.path.join(BASE_DIR, "data", "favorites.json")

METRICS = [
    ("mass_kg", "mass_kg"),
    ("diameter_km", "diameter_km"),
    ("gravity_ms2", "gravity_ms2"),
    ("orbital_period_days", "orbital_period_days"),
    ("mean_temp_c", "mean_temp_c"),
]


def load_objects():
    with open(DATA_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_favorites():
    if not os.path.exists(FAVORITES_PATH):
        return []
    with open(FAVORITES_PATH, "r", encoding="utf-8") as handle:
        try:
            data = json.load(handle)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []


def save_favorites(favorites):
    with open(FAVORITES_PATH, "w", encoding="utf-8") as handle:
        json.dump(favorites, handle, ensure_ascii=False, indent=2)


def to_message(item):
    return catalog_pb2.CelestialObject(
        id=item.get("id", ""),
        type=item.get("type", ""),
        name=item.get("name", ""),
        description_es=item.get("description_es", ""),
        distance_ly=float(item.get("distance_ly", 0.0)),
        mass_kg=float(item.get("mass_kg", 0.0)),
        diameter_km=float(item.get("diameter_km", 0.0)),
        gravity_ms2=float(item.get("gravity_ms2", 0.0)),
        orbital_period_days=float(item.get("orbital_period_days", 0.0)),
        mean_temp_c=float(item.get("mean_temp_c", 0.0)),
        habitable=bool(item.get("habitable", False)),
        image_url=item.get("image_url", ""),
    )


def build_diff(metric, value_a, value_b, id_a, id_b):
    if value_a == value_b:
        winner = ""
        ratio = 1.0
    elif abs(value_a) >= abs(value_b):
        winner = id_a
        ratio = (value_a / value_b) if value_b != 0 else 0.0
    else:
        winner = id_b
        ratio = (value_b / value_a) if value_a != 0 else 0.0
    return catalog_pb2.MetricDiff(
        metric=metric,
        value_a=float(value_a),
        value_b=float(value_b),
        winner_id=winner,
        ratio=float(abs(ratio) if ratio == ratio else 0.0),
    )


class CatalogHandler(catalog_pb2_grpc.CatalogServiceServicer):
    def ListObjects(self, request, context):
        objects = load_objects()
        type_filter = (request.type_filter or "").strip().upper()
        search = (request.search or "").strip().lower()
        result = []
        for item in objects:
            if type_filter and item.get("type", "").upper() != type_filter:
                continue
            if request.habitable_only and not item.get("habitable", False):
                continue
            if search and search not in item.get("name", "").lower() and search not in item.get("description_es", "").lower():
                continue
            result.append(to_message(item))
        return catalog_pb2.ListResponse(objects=result)

    def GetObject(self, request, context):
        objects = load_objects()
        for item in objects:
            if item.get("id") == request.id:
                return to_message(item)
        context.set_code(grpc.StatusCode.NOT_FOUND)
        context.set_details("Object not found")
        return catalog_pb2.CelestialObject()

    def ComparePlanets(self, request, context):
        objects = {item.get("id"): item for item in load_objects()}
        planet_a = objects.get(request.planet_a_id)
        planet_b = objects.get(request.planet_b_id)
        if planet_a is None or planet_b is None:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Planet not found")
            return catalog_pb2.CompareResponse()
        diffs = []
        for metric, key in METRICS:
            diffs.append(build_diff(metric, float(planet_a.get(key, 0.0)), float(planet_b.get(key, 0.0)), planet_a.get("id", ""), planet_b.get("id", "")))
        return catalog_pb2.CompareResponse(
            planet_a=to_message(planet_a),
            planet_b=to_message(planet_b),
            diffs=diffs,
        )

    def ToggleFavorite(self, request, context):
        objects = {item.get("id") for item in load_objects()}
        if request.id not in objects:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Object not found")
            return catalog_pb2.FavoriteResponse()
        favorites = load_favorites()
        if request.id in favorites:
            favorites.remove(request.id)
            is_favorite = False
        else:
            favorites.append(request.id)
            is_favorite = True
        save_favorites(favorites)
        return catalog_pb2.FavoriteResponse(id=request.id, is_favorite=is_favorite)

    def ListFavorites(self, request, context):
        objects = {item.get("id"): item for item in load_objects()}
        favorites = load_favorites()
        result = [to_message(objects[item_id]) for item_id in favorites if item_id in objects]
        return catalog_pb2.ListResponse(objects=result)


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    catalog_pb2_grpc.add_CatalogServiceServicer_to_server(CatalogHandler(), server)
    server.add_insecure_port("0.0.0.0:50051")
    server.start()
    print("CatalogService listening on 50051")
    server.wait_for_termination()


if __name__ == "__main__":
    serve()

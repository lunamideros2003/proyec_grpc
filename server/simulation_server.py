import json
import os
import sys
from concurrent import futures
import grpc

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(BASE_DIR), "generated", "simulation"))

import simulation_pb2
import simulation_pb2_grpc

DATA_PATH = os.path.join(BASE_DIR, "data", "objects.json")
AU_KM = 149597870.7
LY_KM = 9.4607e12

AU_TABLE = {
    "mercury": 0.39,
    "venus": 0.72,
    "earth": 1.0,
    "mars": 1.52,
    "jupiter": 5.2,
    "saturn": 9.58,
    "uranus": 19.2,
    "neptune": 30.1,
    "sun": 0.0,
}

SPACECRAFTS = ["Explorer-I", "Voyager-X", "Aurora", "Titan-Heavy"]


def load_objects():
    with open(DATA_PATH, "r", encoding="utf-8") as handle:
        return {item.get("id"): item for item in json.load(handle)}


def resolve_distance_km(origin, destination):
    origin_ly = float(origin.get("distance_ly", 0.0))
    destination_ly = float(destination.get("distance_ly", 0.0))
    if origin_ly > 0 or destination_ly > 0:
        gap_ly = abs(origin_ly - destination_ly)
        if gap_ly == 0:
            gap_ly = max(origin_ly, destination_ly)
        return gap_ly * LY_KM
    au_origin = AU_TABLE.get(origin.get("id", ""), 1.0)
    au_destination = AU_TABLE.get(destination.get("id", ""), 1.0)
    gap_au = abs(au_origin - au_destination)
    if gap_au == 0:
        gap_au = 0.5
    return gap_au * AU_KM


def build_difficulty(travel_years):
    if travel_years < 1:
        return "Fácil"
    if travel_years < 5:
        return "Moderada"
    if travel_years < 50:
        return "Difícil"
    return "Extrema"


def build_success(distance_km, crew_size, payload_kg, speed_kms):
    base = 96.0
    base -= min(40.0, (distance_km / AU_KM) * 0.4)
    base -= max(0, crew_size - 2) * 3.0
    base -= min(15.0, payload_kg / 2000.0)
    if speed_kms > 60:
        base -= 8.0
    if speed_kms < 10:
        base -= 4.0
    return max(5.0, min(99.0, base))


class SimulationHandler(simulation_pb2_grpc.SimulationServiceServicer):
    def ListPresets(self, request, context):
        return simulation_pb2.PresetList(spacecrafts=SPACECRAFTS)

    def SimulateMission(self, request, context):
        objects = load_objects()
        origin = objects.get(request.origin_id)
        destination = objects.get(request.destination_id)
        if origin is None or destination is None:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Origin or destination not found")
            return simulation_pb2.MissionResult()
        speed = float(request.speed_kms) if request.speed_kms > 0 else 20.0
        payload = float(request.payload_kg) if request.payload_kg >= 0 else 1000.0
        crew = int(request.crew_size) if request.crew_size >= 0 else 0
        spacecraft = request.spacecraft if request.spacecraft else SPACECRAFTS[0]
        distance_km = resolve_distance_km(origin, destination)
        travel_days = distance_km / speed / 86400.0
        travel_years = travel_days / 365.25
        fuel_tons = distance_km * (0.00000012 + payload * 1.2e-13 + crew * 2.0e-10)
        fuel_tons = max(1.5, fuel_tons)
        success_rate = build_success(distance_km, crew, payload, speed)
        difficulty = build_difficulty(travel_years)
        stages = [
            simulation_pb2.MissionStage(name_es="Despegue", duration_days=travel_days * 0.01, fuel_tons=fuel_tons * 0.35, status="OK"),
            simulation_pb2.MissionStage(name_es="Crucero interplanetario", duration_days=travel_days * 0.85, fuel_tons=fuel_tons * 0.40, status="OK"),
            simulation_pb2.MissionStage(name_es="Aproximación orbital", duration_days=travel_days * 0.10, fuel_tons=fuel_tons * 0.15, status="OK"),
            simulation_pb2.MissionStage(name_es="Aterrizaje", duration_days=travel_days * 0.04, fuel_tons=fuel_tons * 0.10, status="OK" if success_rate >= 50 else "RIESGO"),
        ]
        summary = "Misión de " + origin.get("name", "") + " a " + destination.get("name", "") + " con " + spacecraft + ": " + str(round(travel_days, 1)) + " días, " + str(round(fuel_tons, 1)) + " toneladas de combustible, éxito estimado " + str(round(success_rate, 1)) + "%."
        return simulation_pb2.MissionResult(
            origin_id=origin.get("id", ""),
            destination_id=destination.get("id", ""),
            distance_km=float(distance_km),
            travel_days=float(travel_days),
            travel_years=float(travel_years),
            fuel_tons=float(fuel_tons),
            success_rate=float(success_rate),
            difficulty_es=difficulty,
            stages=stages,
            summary_es=summary,
        )


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    simulation_pb2_grpc.add_SimulationServiceServicer_to_server(SimulationHandler(), server)
    server.add_insecure_port("0.0.0.0:50052")
    server.start()
    print("SimulationService listening on 50052")
    server.wait_for_termination()


if __name__ == "__main__":
    serve()

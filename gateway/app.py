import json
import os
import sys
import grpc
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "generated", "catalog"))
sys.path.insert(0, os.path.join(ROOT, "generated", "simulation"))
sys.path.insert(0, os.path.join(ROOT, "generated", "quiz"))

import catalog_pb2
import catalog_pb2_grpc
import simulation_pb2
import simulation_pb2_grpc
import quiz_pb2
import quiz_pb2_grpc

CATALOG_TARGET = os.environ.get("CATALOG_TARGET", "localhost:50051")
SIMULATION_TARGET = os.environ.get("SIMULATION_TARGET", "localhost:50052")
QUIZ_TARGET = os.environ.get("QUIZ_TARGET", "localhost:50053")
USE_GRPC = os.environ.get("USE_GRPC", "true").lower() == "true"
GRPC_TIMEOUT = float(os.environ.get("GRPC_TIMEOUT", "4"))

DATA_DIR = os.path.join(ROOT, "server", "data")
OBJECTS_PATH = os.path.join(DATA_DIR, "objects.json")
QUESTIONS_PATH = os.path.join(DATA_DIR, "questions.json")

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
COMPARE_KEYS = ["mass_kg", "diameter_km", "gravity_ms2", "orbital_period_days", "mean_temp_c"]

app = Flask(__name__)
CORS(app)

catalog_stub = None
simulation_stub = None
quiz_stub = None

if USE_GRPC:
    try:
        catalog_stub = catalog_pb2_grpc.CatalogServiceStub(grpc.insecure_channel(CATALOG_TARGET))
        simulation_stub = simulation_pb2_grpc.SimulationServiceStub(grpc.insecure_channel(SIMULATION_TARGET))
        quiz_stub = quiz_pb2_grpc.QuizServiceStub(grpc.insecure_channel(QUIZ_TARGET))
    except Exception:
        catalog_stub = None
        simulation_stub = None
        quiz_stub = None

memory_favorites = set()
memory_progress = {}


def load_local_objects():
    with open(OBJECTS_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_local_questions():
    with open(QUESTIONS_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def filter_local_objects(objects, type_filter, search, habitable_only):
    result = []
    for item in objects:
        if type_filter and item.get("type", "").upper() != type_filter:
            continue
        if habitable_only and not item.get("habitable", False):
            continue
        if search and search not in item.get("name", "").lower() and search not in item.get("description_es", "").lower():
            continue
        result.append(item)
    return result


def local_compare(item_a, item_b):
    diffs = []
    for key in COMPARE_KEYS:
        value_a = float(item_a.get(key, 0.0))
        value_b = float(item_b.get(key, 0.0))
        if value_a == value_b:
            winner = ""
            ratio = 1.0
        elif abs(value_a) >= abs(value_b):
            winner = item_a.get("id", "")
            ratio = (value_a / value_b) if value_b != 0 else 0.0
        else:
            winner = item_b.get("id", "")
            ratio = (value_b / value_a) if value_a != 0 else 0.0
        diffs.append({"metric": key, "value_a": value_a, "value_b": value_b, "winner_id": winner, "ratio": float(abs(ratio))})
    return diffs


def local_distance_km(origin, destination):
    origin_ly = float(origin.get("distance_ly", 0.0))
    destination_ly = float(destination.get("distance_ly", 0.0))
    if origin_ly > 0 or destination_ly > 0:
        gap_ly = abs(origin_ly - destination_ly)
        if gap_ly == 0:
            gap_ly = max(origin_ly, destination_ly)
        return gap_ly * LY_KM
    gap_au = abs(AU_TABLE.get(origin.get("id", ""), 1.0) - AU_TABLE.get(destination.get("id", ""), 1.0))
    if gap_au == 0:
        gap_au = 0.5
    return gap_au * AU_KM


def local_simulate(origin, destination, spacecraft, speed, payload, crew):
    distance_km = local_distance_km(origin, destination)
    travel_days = distance_km / speed / 86400.0
    travel_years = travel_days / 365.25
    fuel_tons = max(1.5, distance_km * (0.00000012 + payload * 1.2e-13 + crew * 2.0e-10))
    success_rate = 96.0 - min(40.0, (distance_km / AU_KM) * 0.4) - max(0, crew - 2) * 3.0 - min(15.0, payload / 2000.0)
    if speed > 60:
        success_rate -= 8.0
    if speed < 10:
        success_rate -= 4.0
    success_rate = max(5.0, min(99.0, success_rate))
    if travel_years < 1:
        difficulty = "Fácil"
    elif travel_years < 5:
        difficulty = "Moderada"
    elif travel_years < 50:
        difficulty = "Difícil"
    else:
        difficulty = "Extrema"
    stages = [
        {"name_es": "Despegue", "duration_days": travel_days * 0.01, "fuel_tons": fuel_tons * 0.35, "status": "OK"},
        {"name_es": "Crucero interplanetario", "duration_days": travel_days * 0.85, "fuel_tons": fuel_tons * 0.40, "status": "OK"},
        {"name_es": "Aproximación orbital", "duration_days": travel_days * 0.10, "fuel_tons": fuel_tons * 0.15, "status": "OK"},
        {"name_es": "Aterrizaje", "duration_days": travel_days * 0.04, "fuel_tons": fuel_tons * 0.10, "status": "OK" if success_rate >= 50 else "RIESGO"},
    ]
    summary = "Misión de " + origin.get("name", "") + " a " + destination.get("name", "") + " con " + spacecraft + ": " + str(round(travel_days, 1)) + " días, " + str(round(fuel_tons, 1)) + " toneladas de combustible, éxito estimado " + str(round(success_rate, 1)) + "%."
    return {
        "origin_id": origin.get("id", ""),
        "destination_id": destination.get("id", ""),
        "distance_km": distance_km,
        "travel_days": travel_days,
        "travel_years": travel_years,
        "fuel_tons": fuel_tons,
        "success_rate": success_rate,
        "difficulty_es": difficulty,
        "summary_es": summary,
        "stages": stages,
    }


def local_level(best_percent):
    if best_percent >= 90:
        return "Comandante"
    if best_percent >= 70:
        return "Experto"
    if best_percent >= 40:
        return "Explorador"
    return "Principiante"


def local_submit(user_id, answers):
    questions = {item.get("id"): item for item in load_local_questions()}
    total = len(answers)
    correct = 0
    feedback = []
    for answer in answers:
        item = questions.get(answer.get("question_id", ""))
        if item is None:
            continue
        expected = int(item.get("correct_index", 0))
        is_correct = int(answer.get("selected_index", -1)) == expected
        if is_correct:
            correct += 1
        feedback.append({"question_id": answer.get("question_id", ""), "is_correct": is_correct, "correct_index": expected, "explanation_es": item.get("explanation_es", "")})
    score = (correct / total * 100.0) if total > 0 else 0.0
    entry = memory_progress.get(user_id, {"attempts": 0, "best_score": 0, "best_percent": 0.0, "total_answered": 0, "total_correct": 0})
    entry["attempts"] += 1
    entry["total_answered"] += total
    entry["total_correct"] += correct
    if score >= entry["best_percent"]:
        entry["best_percent"] = score
        entry["best_score"] = correct
    entry["level_es"] = local_level(entry["best_percent"])
    memory_progress[user_id] = entry
    return {
        "total": total,
        "correct": correct,
        "score": score,
        "feedback": feedback,
        "progress": {"user_id": user_id, **entry},
    }


def object_to_dict(item):
    return {
        "id": item.id,
        "type": item.type,
        "name": item.name,
        "description_es": item.description_es,
        "distance_ly": item.distance_ly,
        "mass_kg": item.mass_kg,
        "diameter_km": item.diameter_km,
        "gravity_ms2": item.gravity_ms2,
        "orbital_period_days": item.orbital_period_days,
        "mean_temp_c": item.mean_temp_c,
        "habitable": item.habitable,
        "image_url": item.image_url,
    }


def question_to_dict(item, hide_answer=False):
    data = {
        "id": item.id,
        "text_es": item.text_es,
        "options_es": list(item.options_es),
        "difficulty": item.difficulty,
        "category": item.category,
        "explanation_es": item.explanation_es,
    }
    if not hide_answer:
        data["correct_index"] = item.correct_index
    return data


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/objects")
def list_objects():
    type_filter = (request.args.get("type_filter", "") or "").strip().upper()
    search = (request.args.get("search", "") or "").strip().lower()
    habitable_only = request.args.get("habitable_only", "false").lower() == "true"
    if catalog_stub is not None:
        try:
            response = catalog_stub.ListObjects(catalog_pb2.ListRequest(
                type_filter=request.args.get("type_filter", ""),
                search=request.args.get("search", ""),
                habitable_only=habitable_only,
            ), timeout=GRPC_TIMEOUT)
            return jsonify([object_to_dict(item) for item in response.objects])
        except Exception:
            pass
    return jsonify(filter_local_objects(load_local_objects(), type_filter, search, habitable_only))


@app.route("/api/objects/<object_id>")
def get_object(object_id):
    if catalog_stub is not None:
        try:
            item = catalog_stub.GetObject(catalog_pb2.GetRequest(id=object_id), timeout=GRPC_TIMEOUT)
            if item.id:
                return jsonify(object_to_dict(item))
        except Exception:
            pass
    for item in load_local_objects():
        if item.get("id") == object_id:
            return jsonify(item)
    return jsonify({"error": "Objeto no encontrado"}), 404


@app.route("/api/compare", methods=["POST"])
def compare_planets():
    payload = request.get_json(force=True)
    if catalog_stub is not None:
        try:
            result = catalog_stub.ComparePlanets(catalog_pb2.CompareRequest(
                planet_a_id=payload.get("planet_a_id", ""),
                planet_b_id=payload.get("planet_b_id", ""),
            ), timeout=GRPC_TIMEOUT)
            return jsonify({
                "planet_a": object_to_dict(result.planet_a),
                "planet_b": object_to_dict(result.planet_b),
                "diffs": [
                    {"metric": diff.metric, "value_a": diff.value_a, "value_b": diff.value_b, "winner_id": diff.winner_id, "ratio": diff.ratio}
                    for diff in result.diffs
                ],
            })
        except Exception:
            pass
    objects = {item.get("id"): item for item in load_local_objects()}
    planet_a = objects.get(payload.get("planet_a_id", ""))
    planet_b = objects.get(payload.get("planet_b_id", ""))
    if planet_a is None or planet_b is None:
        return jsonify({"error": "No se pudo comparar, verifica los identificadores"}), 404
    return jsonify({"planet_a": planet_a, "planet_b": planet_b, "diffs": local_compare(planet_a, planet_b)})


@app.route("/api/favorites", methods=["GET"])
def list_favorites():
    if catalog_stub is not None:
        try:
            response = catalog_stub.ListFavorites(catalog_pb2.Empty(), timeout=GRPC_TIMEOUT)
            return jsonify([object_to_dict(item) for item in response.objects])
        except Exception:
            pass
    objects = {item.get("id"): item for item in load_local_objects()}
    return jsonify([objects[item_id] for item_id in list(memory_favorites) if item_id in objects])


@app.route("/api/favorites/toggle", methods=["POST"])
def toggle_favorite():
    payload = request.get_json(force=True)
    if catalog_stub is not None:
        try:
            result = catalog_stub.ToggleFavorite(catalog_pb2.FavoriteRequest(id=payload.get("id", "")), timeout=GRPC_TIMEOUT)
            return jsonify({"id": result.id, "is_favorite": result.is_favorite})
        except Exception:
            pass
    target = payload.get("id", "")
    known = {item.get("id") for item in load_local_objects()}
    if target not in known:
        return jsonify({"error": "Objeto no encontrado"}), 404
    if target in memory_favorites:
        memory_favorites.remove(target)
        is_favorite = False
    else:
        memory_favorites.add(target)
        is_favorite = True
    return jsonify({"id": target, "is_favorite": is_favorite})


@app.route("/api/presets")
def list_presets():
    if simulation_stub is not None:
        try:
            response = simulation_stub.ListPresets(simulation_pb2.Empty(), timeout=GRPC_TIMEOUT)
            return jsonify(list(response.spacecrafts))
        except Exception:
            pass
    return jsonify(SPACECRAFTS)


@app.route("/api/simulate", methods=["POST"])
def simulate_mission():
    payload = request.get_json(force=True)
    if simulation_stub is not None:
        try:
            result = simulation_stub.SimulateMission(simulation_pb2.MissionRequest(
                origin_id=payload.get("origin_id", ""),
                destination_id=payload.get("destination_id", ""),
                spacecraft=payload.get("spacecraft", ""),
                speed_kms=float(payload.get("speed_kms", 20)),
                payload_kg=float(payload.get("payload_kg", 1000)),
                crew_size=int(payload.get("crew_size", 0)),
            ), timeout=GRPC_TIMEOUT)
            return jsonify({
                "origin_id": result.origin_id,
                "destination_id": result.destination_id,
                "distance_km": result.distance_km,
                "travel_days": result.travel_days,
                "travel_years": result.travel_years,
                "fuel_tons": result.fuel_tons,
                "success_rate": result.success_rate,
                "difficulty_es": result.difficulty_es,
                "summary_es": result.summary_es,
                "stages": [
                    {"name_es": stage.name_es, "duration_days": stage.duration_days, "fuel_tons": stage.fuel_tons, "status": stage.status}
                    for stage in result.stages
                ],
            })
        except Exception:
            pass
    objects = {item.get("id"): item for item in load_local_objects()}
    origin = objects.get(payload.get("origin_id", ""))
    destination = objects.get(payload.get("destination_id", ""))
    if origin is None or destination is None:
        return jsonify({"error": "No se pudo simular, verifica origen y destino"}), 404
    speed = float(payload.get("speed_kms", 20) or 20)
    return jsonify(local_simulate(origin, destination, payload.get("spacecraft", "") or SPACECRAFTS[0], speed, float(payload.get("payload_kg", 1000) or 0), int(payload.get("crew_size", 0) or 0)))


@app.route("/api/questions")
def list_questions():
    difficulty = (request.args.get("difficulty", "") or "").strip().lower()
    try:
        limit = int(request.args.get("limit", 10))
    except ValueError:
        limit = 10
    if quiz_stub is not None:
        try:
            response = quiz_stub.ListQuestions(quiz_pb2.ListQuestionsRequest(
                difficulty=request.args.get("difficulty", ""),
                limit=limit,
            ), timeout=GRPC_TIMEOUT)
            return jsonify([question_to_dict(item, hide_answer=True) for item in response.questions])
        except Exception:
            pass
    questions = load_local_questions()
    filtered = [item for item in questions if not difficulty or item.get("difficulty", "").lower() == difficulty]
    visible = [{key: item[key] for key in ("id", "text_es", "options_es", "difficulty", "category", "explanation_es")} for item in filtered[:limit if limit > 0 else len(filtered)]]
    return jsonify(visible)


@app.route("/api/quiz/submit", methods=["POST"])
def submit_quiz():
    payload = request.get_json(force=True)
    if quiz_stub is not None:
        try:
            answers = [quiz_pb2.Answer(question_id=item.get("question_id", ""), selected_index=int(item.get("selected_index", 0))) for item in payload.get("answers", [])]
            result = quiz_stub.SubmitAnswers(quiz_pb2.SubmitRequest(user_id=payload.get("user_id", "guest"), answers=answers), timeout=GRPC_TIMEOUT)
            return jsonify({
                "total": result.total,
                "correct": result.correct,
                "score": result.score,
                "feedback": [
                    {"question_id": item.question_id, "is_correct": item.is_correct, "correct_index": item.correct_index, "explanation_es": item.explanation_es}
                    for item in result.feedback
                ],
                "progress": {
                    "user_id": result.progress.user_id,
                    "attempts": result.progress.attempts,
                    "best_score": result.progress.best_score,
                    "best_percent": result.progress.best_percent,
                    "total_answered": result.progress.total_answered,
                    "total_correct": result.progress.total_correct,
                    "level_es": result.progress.level_es,
                },
            })
        except Exception:
            pass
    return jsonify(local_submit(payload.get("user_id", "guest") or "guest", payload.get("answers", [])))


@app.route("/api/progress/<user_id>")
def get_progress(user_id):
    if quiz_stub is not None:
        try:
            result = quiz_stub.GetProgress(quiz_pb2.ProgressRequest(user_id=user_id), timeout=GRPC_TIMEOUT)
            return jsonify({
                "user_id": result.user_id,
                "attempts": result.attempts,
                "best_score": result.best_score,
                "best_percent": result.best_percent,
                "total_answered": result.total_answered,
                "total_correct": result.total_correct,
                "level_es": result.level_es,
            })
        except Exception:
            pass
    entry = memory_progress.get(user_id, {"attempts": 0, "best_score": 0, "best_percent": 0.0, "total_answered": 0, "total_correct": 0, "level_es": "Principiante"})
    return jsonify({"user_id": user_id, **entry})


@app.route("/api/progress/<user_id>/reset", methods=["POST"])
def reset_progress(user_id):
    if quiz_stub is not None:
        try:
            result = quiz_stub.ResetProgress(quiz_pb2.ProgressRequest(user_id=user_id), timeout=GRPC_TIMEOUT)
            return jsonify({
                "user_id": result.user_id,
                "attempts": result.attempts,
                "best_score": result.best_score,
                "best_percent": result.best_percent,
                "total_answered": result.total_answered,
                "total_correct": result.total_correct,
                "level_es": result.level_es,
            })
        except Exception:
            pass
    entry = {"attempts": 0, "best_score": 0, "best_percent": 0.0, "total_answered": 0, "total_correct": 0, "level_es": "Principiante"}
    memory_progress[user_id] = entry
    return jsonify({"user_id": user_id, **entry})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)

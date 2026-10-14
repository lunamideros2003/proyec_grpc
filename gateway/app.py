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

app = Flask(__name__)
CORS(app)

catalog_channel = grpc.insecure_channel(CATALOG_TARGET)
simulation_channel = grpc.insecure_channel(SIMULATION_TARGET)
quiz_channel = grpc.insecure_channel(QUIZ_TARGET)

catalog_stub = catalog_pb2_grpc.CatalogServiceStub(catalog_channel)
simulation_stub = simulation_pb2_grpc.SimulationServiceStub(simulation_channel)
quiz_stub = quiz_pb2_grpc.QuizServiceStub(quiz_channel)


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
    response = catalog_stub.ListObjects(catalog_pb2.ListRequest(
        type_filter=request.args.get("type_filter", ""),
        search=request.args.get("search", ""),
        habitable_only=request.args.get("habitable_only", "false").lower() == "true",
    ))
    return jsonify([object_to_dict(item) for item in response.objects])


@app.route("/api/objects/<object_id>")
def get_object(object_id):
    try:
        item = catalog_stub.GetObject(catalog_pb2.GetRequest(id=object_id))
        return jsonify(object_to_dict(item))
    except grpc.RpcError as error:
        return jsonify({"error": "Objeto no encontrado"}), 404


@app.route("/api/compare", methods=["POST"])
def compare_planets():
    payload = request.get_json(force=True)
    try:
        result = catalog_stub.ComparePlanets(catalog_pb2.CompareRequest(
            planet_a_id=payload.get("planet_a_id", ""),
            planet_b_id=payload.get("planet_b_id", ""),
        ))
    except grpc.RpcError:
        return jsonify({"error": "No se pudo comparar, verifica los identificadores"}), 404
    return jsonify({
        "planet_a": object_to_dict(result.planet_a),
        "planet_b": object_to_dict(result.planet_b),
        "diffs": [
            {"metric": diff.metric, "value_a": diff.value_a, "value_b": diff.value_b, "winner_id": diff.winner_id, "ratio": diff.ratio}
            for diff in result.diffs
        ],
    })


@app.route("/api/favorites", methods=["GET"])
def list_favorites():
    response = catalog_stub.ListFavorites(catalog_pb2.Empty())
    return jsonify([object_to_dict(item) for item in response.objects])


@app.route("/api/favorites/toggle", methods=["POST"])
def toggle_favorite():
    payload = request.get_json(force=True)
    try:
        result = catalog_stub.ToggleFavorite(catalog_pb2.FavoriteRequest(id=payload.get("id", "")))
        return jsonify({"id": result.id, "is_favorite": result.is_favorite})
    except grpc.RpcError:
        return jsonify({"error": "Objeto no encontrado"}), 404


@app.route("/api/presets")
def list_presets():
    response = simulation_stub.ListPresets(simulation_pb2.Empty())
    return jsonify(list(response.spacecrafts))


@app.route("/api/simulate", methods=["POST"])
def simulate_mission():
    payload = request.get_json(force=True)
    try:
        result = simulation_stub.SimulateMission(simulation_pb2.MissionRequest(
            origin_id=payload.get("origin_id", ""),
            destination_id=payload.get("destination_id", ""),
            spacecraft=payload.get("spacecraft", ""),
            speed_kms=float(payload.get("speed_kms", 20)),
            payload_kg=float(payload.get("payload_kg", 1000)),
            crew_size=int(payload.get("crew_size", 0)),
        ))
    except grpc.RpcError:
        return jsonify({"error": "No se pudo simular, verifica origen y destino"}), 404
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


@app.route("/api/questions")
def list_questions():
    response = quiz_stub.ListQuestions(quiz_pb2.ListQuestionsRequest(
        difficulty=request.args.get("difficulty", ""),
        limit=int(request.args.get("limit", 10)),
    ))
    return jsonify([question_to_dict(item, hide_answer=True) for item in response.questions])


@app.route("/api/quiz/submit", methods=["POST"])
def submit_quiz():
    payload = request.get_json(force=True)
    answers = [quiz_pb2.Answer(question_id=item.get("question_id", ""), selected_index=int(item.get("selected_index", 0))) for item in payload.get("answers", [])]
    result = quiz_stub.SubmitAnswers(quiz_pb2.SubmitRequest(user_id=payload.get("user_id", "guest"), answers=answers))
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


@app.route("/api/progress/<user_id>")
def get_progress(user_id):
    result = quiz_stub.GetProgress(quiz_pb2.ProgressRequest(user_id=user_id))
    return jsonify({
        "user_id": result.user_id,
        "attempts": result.attempts,
        "best_score": result.best_score,
        "best_percent": result.best_percent,
        "total_answered": result.total_answered,
        "total_correct": result.total_correct,
        "level_es": result.level_es,
    })


@app.route("/api/progress/<user_id>/reset", methods=["POST"])
def reset_progress(user_id):
    result = quiz_stub.ResetProgress(quiz_pb2.ProgressRequest(user_id=user_id))
    return jsonify({
        "user_id": result.user_id,
        "attempts": result.attempts,
        "best_score": result.best_score,
        "best_percent": result.best_percent,
        "total_answered": result.total_answered,
        "total_correct": result.total_correct,
        "level_es": result.level_es,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)

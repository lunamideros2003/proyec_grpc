import json
import os
import sys
from concurrent import futures
import grpc

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(BASE_DIR), "generated", "quiz"))

import quiz_pb2
import quiz_pb2_grpc

QUESTIONS_PATH = os.path.join(BASE_DIR, "data", "questions.json")
PROGRESS_PATH = os.path.join(BASE_DIR, "data", "progress.json")


def load_questions():
    with open(QUESTIONS_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_progress():
    if not os.path.exists(PROGRESS_PATH):
        return {}
    with open(PROGRESS_PATH, "r", encoding="utf-8") as handle:
        try:
            data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}


def save_progress(data):
    with open(PROGRESS_PATH, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def to_message(item):
    return quiz_pb2.Question(
        id=item.get("id", ""),
        text_es=item.get("text_es", ""),
        options_es=item.get("options_es", []),
        correct_index=int(item.get("correct_index", 0)),
        explanation_es=item.get("explanation_es", ""),
        difficulty=item.get("difficulty", ""),
        category=item.get("category", ""),
    )


def build_level(best_percent):
    if best_percent >= 90:
        return "Comandante"
    if best_percent >= 70:
        return "Experto"
    if best_percent >= 40:
        return "Explorador"
    return "Principiante"


def to_progress_message(user_id, entry):
    return quiz_pb2.UserProgress(
        user_id=user_id,
        attempts=int(entry.get("attempts", 0)),
        best_score=int(entry.get("best_score", 0)),
        best_percent=float(entry.get("best_percent", 0.0)),
        total_answered=int(entry.get("total_answered", 0)),
        total_correct=int(entry.get("total_correct", 0)),
        level_es=entry.get("level_es", "Principiante"),
    )


class QuizHandler(quiz_pb2_grpc.QuizServiceServicer):
    def ListQuestions(self, request, context):
        questions = load_questions()
        difficulty = (request.difficulty or "").strip().lower()
        filtered = [item for item in questions if not difficulty or item.get("difficulty", "").lower() == difficulty]
        limit = int(request.limit) if request.limit and request.limit > 0 else len(filtered)
        return quiz_pb2.ListQuestionsResponse(questions=[to_message(item) for item in filtered[:limit]])

    def SubmitAnswers(self, request, context):
        questions = {item.get("id"): item for item in load_questions()}
        user_id = request.user_id.strip() if request.user_id else "guest"
        total = len(request.answers)
        correct = 0
        feedback = []
        for answer in request.answers:
            item = questions.get(answer.question_id)
            if item is None:
                continue
            expected = int(item.get("correct_index", 0))
            is_correct = int(answer.selected_index) == expected
            if is_correct:
                correct += 1
            feedback.append(quiz_pb2.AnswerFeedback(
                question_id=answer.question_id,
                is_correct=is_correct,
                correct_index=expected,
                explanation_es=item.get("explanation_es", ""),
            ))
        score = (correct / total * 100.0) if total > 0 else 0.0
        store = load_progress()
        entry = store.get(user_id, {"attempts": 0, "best_score": 0, "best_percent": 0.0, "total_answered": 0, "total_correct": 0, "level_es": "Principiante"})
        entry["attempts"] = int(entry.get("attempts", 0)) + 1
        entry["total_answered"] = int(entry.get("total_answered", 0)) + total
        entry["total_correct"] = int(entry.get("total_correct", 0)) + correct
        if score >= float(entry.get("best_percent", 0.0)):
            entry["best_percent"] = float(score)
            entry["best_score"] = int(correct)
        entry["level_es"] = build_level(float(entry.get("best_percent", 0.0)))
        store[user_id] = entry
        save_progress(store)
        return quiz_pb2.SubmitResponse(
            total=int(total),
            correct=int(correct),
            score=float(score),
            feedback=feedback,
            progress=to_progress_message(user_id, entry),
        )

    def GetProgress(self, request, context):
        user_id = request.user_id.strip() if request.user_id else "guest"
        store = load_progress()
        entry = store.get(user_id, {"attempts": 0, "best_score": 0, "best_percent": 0.0, "total_answered": 0, "total_correct": 0, "level_es": "Principiante"})
        return to_progress_message(user_id, entry)

    def ResetProgress(self, request, context):
        user_id = request.user_id.strip() if request.user_id else "guest"
        store = load_progress()
        entry = {"attempts": 0, "best_score": 0, "best_percent": 0.0, "total_answered": 0, "total_correct": 0, "level_es": "Principiante"}
        store[user_id] = entry
        save_progress(store)
        return to_progress_message(user_id, entry)


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    quiz_pb2_grpc.add_QuizServiceServicer_to_server(QuizHandler(), server)
    server.add_insecure_port("0.0.0.0:50053")
    server.start()
    print("QuizService listening on 50053")
    server.wait_for_termination()


if __name__ == "__main__":
    serve()

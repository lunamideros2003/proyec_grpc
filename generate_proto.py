import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PROTOS = os.path.join(ROOT, "protos")

JOBS = [
    ("catalog.proto", os.path.join(ROOT, "generated", "catalog")),
    ("simulation.proto", os.path.join(ROOT, "generated", "simulation")),
    ("quiz.proto", os.path.join(ROOT, "generated", "quiz")),
]

for proto_file, out_dir in JOBS:
    os.makedirs(out_dir, exist_ok=True)
    result = subprocess.run(
        [sys.executable, "-m", "grpc_tools.protoc", "-I", PROTOS, "--python_out=" + out_dir, "--grpc_python_out=" + out_dir, os.path.join(PROTOS, proto_file)]
    )
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    print("Generated " + proto_file)

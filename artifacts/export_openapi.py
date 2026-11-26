import os
import sys
import json

os.environ["DB_NAME"] = "flashcore_test"
sys.path.insert(0, "backend")

from main import app

spec = app.openapi()

with open("artifacts/openapi.json", "w", encoding="utf-8") as f:
    json.dump(spec, f, indent=2)

os.makedirs("artifacts/FLASHCORE-FINAL-SUBMISSION/02_ARCHITECTURE", exist_ok=True)
with open("artifacts/FLASHCORE-FINAL-SUBMISSION/02_ARCHITECTURE/openapi.json", "w", encoding="utf-8") as f:
    json.dump(spec, f, indent=2)

print(f"Successfully exported openapi.json: {len(spec['paths'])} paths registered.")

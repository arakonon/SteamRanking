import os
import sys

PROJECT_DIR = os.environ.get(
    "PROJECT_DIR",
    os.path.dirname(os.path.abspath(__file__)),
)
sys.path.insert(0, PROJECT_DIR)
os.chdir(PROJECT_DIR)

from app import app

with app.app_context():
    from services.snapshot import run_snapshot
    result = run_snapshot()
    print(result)

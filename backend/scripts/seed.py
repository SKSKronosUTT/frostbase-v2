import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import init_db
from app.services.seed import seed_database

parser = argparse.ArgumentParser(description="Create the schema and seed Frostbase data")
parser.add_argument("--force", action="store_true", help="Delete existing data first")
args = parser.parse_args()

init_db()
result = seed_database(force=args.force)
print(result)

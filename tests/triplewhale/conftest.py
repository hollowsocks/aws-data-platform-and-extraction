import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2] / 'data-ingestion' / 'triplewhale' / 'src'
if SRC_ROOT.exists():
    sys.path.insert(0, str(SRC_ROOT))

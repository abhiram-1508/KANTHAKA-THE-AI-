"""Append a dated entry to LOGBOOK.txt.   Usage: python log.py "Fixed wake word bug" [STAGE 2]"""
import sys
from datetime import date
from pathlib import Path

if len(sys.argv) < 2:
    sys.exit('Usage: python log.py "what changed" [stage label]')
stage = f" {sys.argv[2]}" if len(sys.argv) > 2 else ""
with open(Path(__file__).with_name("LOGBOOK.txt"), "a", encoding="utf-8") as f:
    f.write(f"\n[{date.today()}]{stage}\n  + {sys.argv[1]}\n")
print("Logbook updated.")

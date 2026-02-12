import os, requests, re
from Levenshtein import distance as lev
import re
from math import floor

def parse_score(text: str):
    # e.g., "1 - 3" or "3-1"
    m = re.search(r"(\d+)\s*[-:\u2013]\s*(\d+)", text or "")
    if not m: return None, None
    return int(m.group(1)), int(m.group(2))

def parse_pair_numbers(left_text: str, right_text: str):
    # given two ROIs that contain just numbers, return ints
    def _int(s):
        m = re.search(r"\d+", s or "")
        return int(m.group()) if m else None
    return _int(left_text), _int(right_text)



def translate_to_english(text: str) -> str:
  api_key = os.getenv("GOOGLE_TRANSLATE_KEY")
  if not api_key or not text:
    return text
  try:
    url = f"https://translation.googleapis.com/language/translate/v2?key={api_key}"
    payload = {"q": text, "target": "en", "format": "text"}
    res = requests.post(url, json=payload, timeout=4)
    data = res.json()
    return data["data"]["translations"][0]["translatedText"]
  except Exception:
    return text

def normalize_label(raw_text: str, dictionary: dict) -> str:
  rt = raw_text.lower()
  for key, variants in dictionary.items():
    for v in variants:
      if v.lower() in rt:
        return key
  translated = translate_to_english(raw_text).lower()
  for key, variants in dictionary.items():
    if key in translated:
      return key
  return rt

def normalize_username(name: str):
  return re.sub(r"[^a-zA-Z0-9 ]", "", name or "").strip().lower()

def fuzzy_match(a: str, b: str, max_edits: int = 2):
  return lev(normalize_username(a), normalize_username(b)) <= max_edits

def parse_int_safe(s: str):
  m = re.search(r"\d+", s or "")
  return int(m.group()) if m else None

def parse_percent_safe(s: str):
  m = re.search(r"(\d+)", s or "")
  return int(m.group()) if m else None

def validate_coherence_sports(a, b):
  ok = True
  notes = []

  if a.get("possession") is not None and b.get("possession") is not None:
    total = a["possession"] + b["possession"]
    if abs(100 - total) > 3:
      ok = False
      notes.append("Possession does not sum to ~100")

  for side in (a, b):
    if side.get("shotsOnTarget") is not None and side.get("goals") is not None:
      if side["shotsOnTarget"] < side["goals"]:
        ok = False
        notes.append("Shots on target less than goals")

  return ok, notes

def timestamps_close(tsA: str, tsB: str, max_minutes: int = 5):
  # As a fallback, this compares server-side upload times (passed in meta) if EXIF unavailable
  from datetime import datetime
  try:
    a = datetime.fromisoformat(tsA.replace("Z",""))
    b = datetime.fromisoformat(tsB.replace("Z",""))
    delta = abs((a - b).total_seconds()) / 60.0
    return delta <= max_minutes
  except Exception:
    return False

def pick_better_submission(metaA, metaB):
  # Prefer full-time; else prefer later timestamp
  if metaA.get("isFullTime") and not metaB.get("isFullTime"):
    return "A"
  if metaB.get("isFullTime") and not metaA.get("isFullTime"):
    return "B"
  # Compare timestamps if available
  tsA = metaA.get("timestamp")
  tsB = metaB.get("timestamp")
  if tsA and tsB:
    from datetime import datetime
    try:
      a = datetime.fromisoformat(tsA.replace("Z",""))
      b = datetime.fromisoformat(tsB.replace("Z",""))
      return "A" if a > b else "B"
    except Exception:
      pass
  return "A"  # default



def parse_score(text: str):
    m = re.search(r"(\d+)\s*[-:\u2013]\s*(\d+)", text or "")
    if not m: return None, None
    return int(m.group(1)), int(m.group(2))

def parse_int_safe(s: str):
    m = re.search(r"\d+", s or "")
    return int(m.group()) if m else None

def parse_percent_safe(s: str):
    m = re.search(r"(\d+)", s or "")
    return int(m.group()) if m else None

def estimate_sot(shots: int, shot_accuracy_percent: int):
    if shots is None or shot_accuracy_percent is None:
        return None
    return round(shots * (shot_accuracy_percent / 100.0))

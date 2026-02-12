from fastapi import FastAPI, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
import json
from .models import ParsedResult, SideStats
from .ocr import load_image_bytes, crop_roi, ocr_text, bytes_hash, parse_penalties, parse_clock
from .validators import parse_int_safe, parse_percent_safe, validate_coherence_sports, normalize_label, translate_to_english, timestamps_close, pick_better_submission
from .winner import compute_winner_sports
from .ocr import load_image_bytes, crop_roi, ocr_text, bytes_hash
from .validators import parse_int_safe, parse_percent_safe, normalize_label, translate_to_english, parse_score, parse_pair_numbers
from .winner import compute_winner_fcm

from .ocr import load_image_bytes, crop_roi, ocr_text, bytes_hash
from .validators import parse_int_safe, fuzzy_match
from .winner import compute_winner_freefire


app = FastAPI()
app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)

def load_profile():
  with open("app/profiles/efootball_1v1.json", "r", encoding="utf-8") as f:
    return json.load(f)

@app.post("/ocr/efootball/verify")
async def efootball_verify(
  matchId: str = Form(...),
  userId: str = Form(...),
  layoutVersion: str = Form("v1"),
  image: UploadFile = UploadFile(...)
):
  profile = load_profile()
  img, raw_bytes, exif_time = load_image_bytes(image)

  roi = profile["roi"]
  labels = profile.get("labels", {})

  # Read full-time/in-progress banner ROI text and normalize
  banner_txt = ocr_text(crop_roi(img, roi["title_full_time"]))
  banner_label = normalize_label(banner_txt, { "full_time": labels.get("full_time", []), "in_progress": labels.get("in_progress", []) })
  is_full_time = (banner_label == "full_time")

  # If banner shows time format (e.g., 54:34), capture clock seconds
  in_progress_clock = parse_clock(banner_txt)

  # Extract usernames and stats
  teamA_user_raw = ocr_text(crop_roi(img, roi["teamA_user"]))
  teamB_user_raw = ocr_text(crop_roi(img, roi["teamB_user"]))

  teamA_goals = parse_int_safe(ocr_text(crop_roi(img, roi["teamA_goals"])))
  teamB_goals = parse_int_safe(ocr_text(crop_roi(img, roi["teamB_goals"])))

  teamA_sot = parse_int_safe(ocr_text(crop_roi(img, roi["teamA_shots_on_target"])))
  teamB_sot = parse_int_safe(ocr_text(crop_roi(img, roi["teamB_shots_on_target"])))

  teamA_pos = parse_percent_safe(ocr_text(crop_roi(img, roi["teamA_possession"])))
  teamB_pos = parse_percent_safe(ocr_text(crop_roi(img, roi["teamB_possession"])))

  # Penalties block
  penaltiesA, penaltiesB = parse_penalties(ocr_text(crop_roi(img, roi["penalties_block"])))

  sideA = { "userName": teamA_user_raw, "goals": teamA_goals, "shotsOnTarget": teamA_sot, "possession": teamA_pos, "penalties": penaltiesA, "raw": {} }
  sideB = { "userName": teamB_user_raw, "goals": teamB_goals, "shotsOnTarget": teamB_sot, "possession": teamB_pos, "penalties": penaltiesB, "raw": {} }

  coh_ok, notes = validate_coherence_sports(sideA, sideB)

  winner, tieBreak = compute_winner_sports(sideA, sideB, "efootball", allow_penalties=True, penaltiesA=penaltiesA, penaltiesB=penaltiesB)

  bytes_hash_hex = bytes_hash(raw_bytes)
  resolution = f"{img.shape[1]}x{img.shape[0]}"
  orientation = "landscape" if img.shape[1] >= img.shape[0] else "portrait"

  # Confidence heuristic
  filled = sum([1 for v in [teamA_goals, teamB_goals, teamA_sot, teamB_sot, teamA_pos, teamB_pos] if v is not None])
  confidence = min(0.99, 0.6 + filled * 0.06)
  if not is_full_time and in_progress_clock is None:
    confidence -= 0.15

  return {
    "game": "efootball",
    "teamSize": 1,
    "sideA": sideA,
    "sideB": sideB,
    "meta": {
      "matchId": matchId,
      "bytesHash": bytes_hash_hex,
      "resolution": resolution,
      "orientation": orientation,
      "isFullTime": is_full_time,
      "bannerText": banner_txt,
      "clockSeconds": in_progress_clock,
      "timestamp": exif_time  # may be None
    },
    "coherence": { "ok": coh_ok, "notes": notes },
    "winner": winner,
    "tieBreak": tieBreak,
    "confidence": round(confidence, 2)
  }

@app.post("/ocr/efootball/compare")
async def efootball_compare(payload: dict):
  # payload: { submissions: [ParsedResultA, ParsedResultB], serverTimestamps: [isoA, isoB] }
  subA, subB = payload["submissions"][0], payload["submissions"][1]
  tsA = subA["meta"].get("timestamp") or payload.get("serverTimestamps", [None, None])[0]
  tsB = subB["meta"].get("timestamp") or payload.get("serverTimestamps", [None, None])[1]

  # Prefer full-time submission; else prefer later timestamp
  preferred = pick_better_submission(subA["meta"], subB["meta"])

  # Timestamp alignment check (if both timestamps exist)
  aligned = (tsA and tsB and timestamps_close(tsA, tsB)) or False

  # Winner consistency (if both computed)
  winA, winB = subA.get("winner"), subB.get("winner")
  final_winner = winA if winA == winB and winA is not None else (winA if preferred == "A" else winB)

  confidence = round((subA.get("confidence", 0.6) + subB.get("confidence", 0.6)) / 2.0, 2)
  if preferred == "A" and subA["meta"].get("isFullTime"): confidence += 0.05
  if preferred == "B" and subB["meta"].get("isFullTime"): confidence += 0.05
  if aligned: confidence += 0.04

  return {
    "aligned": aligned,
    "preferred": preferred,
    "winner": final_winner,
    "tieBreak": subA.get("tieBreak") if preferred == "A" else subB.get("tieBreak"),
    "confidence": min(0.99, confidence)
  }





def load_profile_fcm():
    with open("app/profiles/fcm_1v1.json", "r", encoding="utf-8") as f:
        return json.load(f)

@app.post("/ocr/fcm/verify")
async def fcm_verify(
    matchId: str = Form(...),
    userId: str = Form(...),
    layoutVersion: str = Form("v1"),
    image: UploadFile = UploadFile(...)
):
    profile = load_profile_fcm()
    roi = profile["roi"]
    labels = profile.get("labels", {})
    img, raw_bytes, exif_time = load_image_bytes(image)

    # Usernames
    uploader_user = ocr_text(crop_roi(img, roi["uploader_user"]))
    opponent_user = ocr_text(crop_roi(img, roi["opponent_user"]))

    # Score + full time clock
    score_txt = ocr_text(crop_roi(img, roi["score_block"]))
    goals_opponent, goals_uploader = parse_score(score_txt)
    clock_txt = ocr_text(crop_roi(img, roi["clock_full_time"]))
    clock_norm = normalize_label(clock_txt, { "full_time": labels.get("full_time", []) })
    is_full_time = (clock_norm == "full_time") or ("90" in clock_txt)

    # Shots / Shots on Target / Possession
    opp_shots_txt = ocr_text(crop_roi(img, roi["opponent_shots"]))
    up_shots_txt = ocr_text(crop_roi(img, roi["uploader_shots"]))
    shots_opponent, shots_uploader = parse_pair_numbers(opp_shots_txt, up_shots_txt)

    opp_sot_txt = ocr_text(crop_roi(img, roi["opponent_sot"]))
    up_sot_txt = ocr_text(crop_roi(img, roi["uploader_sot"]))
    sot_opponent, sot_uploader = parse_pair_numbers(opp_sot_txt, up_sot_txt)

    opp_pos_txt = ocr_text(crop_roi(img, roi["opponent_possession"]))
    up_pos_txt = ocr_text(crop_roi(img, roi["uploader_possession"]))
    pos_opponent = parse_percent_safe(opp_pos_txt)
    pos_uploader = parse_percent_safe(up_pos_txt)

    # Build sides normalized to platform: SideA = uploader, SideB = opponent
    sideA = {
        "userName": uploader_user,
        "goals": goals_uploader,
        "shotsOnTarget": sot_uploader,
        "possession": pos_uploader,
        "raw": {}
    }
    sideB = {
        "userName": opponent_user,
        "goals": goals_opponent,
        "shotsOnTarget": sot_opponent,
        "possession": pos_opponent,
        "raw": {}
    }

    # Winner and confidence
    winner, tieBreak = compute_winner_fcm(sideA, sideB)

    notes = []
    if sot_uploader and shots_uploader and sot_uploader > shots_uploader:
        notes.append("Uploader shots on goal > shots")
    if sot_opponent and shots_opponent and sot_opponent > shots_opponent:
        notes.append("Opponent shots on goal > shots")
    if pos_uploader and pos_opponent:
        total = pos_uploader + pos_opponent
        if abs(100 - total) > 3:
            notes.append("Possession does not sum to ~100")

    filled = sum([1 for v in [goals_uploader, goals_opponent, sot_uploader, sot_opponent, pos_uploader, pos_opponent] if v is not None])
    confidence = min(0.99, 0.6 + filled * 0.06)
    if not is_full_time:
        confidence -= 0.08

    return {
        "game": "fcm",
        "teamSize": 1,
        "sideA": sideA,
        "sideB": sideB,
        "meta": {
            "matchId": matchId,
            "bytesHash": bytes_hash(raw_bytes),
            "resolution": f"{img.shape[1]}x{img.shape[0]}",
            "orientation": "landscape" if img.shape[1] >= img.shape[0] else "portrait",
            "isFullTime": is_full_time,
            "clockText": clock_txt,
            "timestamp": exif_time
        },
        "coherence": { "ok": len(notes) == 0, "notes": notes },
        "winner": winner,
        "tieBreak": tieBreak,
        "confidence": round(confidence, 2)
    }

@app.post("/ocr/fcm/compare")
async def fcm_compare(payload: dict):
    # payload: { submissions: [A, B], serverTimestamps: [isoA, isoB] }
    subA, subB = payload["submissions"][0], payload["submissions"][1]
    tsA = subA["meta"].get("timestamp") or (payload.get("serverTimestamps") or [None])[0]
    tsB = subB["meta"].get("timestamp") or (payload.get("serverTimestamps") or [None])[1]

    # Prefer full-time; else later timestamp
    preferred = "A"
    if subA["meta"].get("isFullTime") and not subB["meta"].get("isFullTime"):
        preferred = "A"
    elif subB["meta"].get("isFullTime") and not subA["meta"].get("isFullTime"):
        preferred = "B"
    else:
        try:
            from datetime import datetime
            a = datetime.fromisoformat((tsA or "").replace("Z",""))
            b = datetime.fromisoformat((tsB or "").replace("Z",""))
            preferred = "A" if a > b else "B"
        except Exception:
            preferred = "A"

    # Winner consistency
    winA, winB = subA.get("winner"), subB.get("winner")
    final_winner = winA if winA == winB and winA is not None else (winA if preferred == "A" else winB)

    # Confidence heuristic
    confidence = round((subA.get("confidence", 0.6) + subB.get("confidence", 0.6)) / 2.0, 2)
    if (preferred == "A" and subA["meta"].get("isFullTime")) or (preferred == "B" and subB["meta"].get("isFullTime")):
        confidence = min(0.99, confidence + 0.05)

    return {
        "aligned": bool(tsA and tsB),
        "preferred": preferred,
        "winner": final_winner,
        "tieBreak": subA.get("tieBreak") if preferred == "A" else subB.get("tieBreak"),
        "confidence": confidence
    }


from .ocr import load_image_bytes, crop_roi, ocr_text, bytes_hash
from .validators import parse_int_safe, parse_percent_safe, normalize_label, parse_score, estimate_sot, fuzzy_match
from .winner import compute_winner_dls

app = FastAPI()
app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)

def load_profile_dls():
    with open("app/profiles/dls_1v1.json", "r", encoding="utf-8") as f:
        return json.load(f)

@app.post("/ocr/dls/verify")
async def dls_verify(
    matchId: str = Form(...),
    userId: str = Form(...),
    uploaderGameUser: str = Form(...),   # registered DLS username for uploader
    opponentGameUser: str = Form(...),   # registered DLS username for opponent
    layoutVersion: str = Form("v1"),
    image: UploadFile = UploadFile(...)
):
    profile = load_profile_dls()
    roi = profile["roi"]; labels = profile.get("labels", {})
    img, raw_bytes, exif_time = load_image_bytes(image)

    # OCR usernames (left/right)
    left_user = ocr_text(crop_roi(img, roi["left_user"]))
    right_user = ocr_text(crop_roi(img, roi["right_user"]))

    # Decide which side is uploader/opponent via fuzzy match to registered names
    left_is_uploader = fuzzy_match(left_user, uploaderGameUser)
    right_is_uploader = fuzzy_match(right_user, uploaderGameUser)

    if left_is_uploader and not right_is_uploader:
        uploader_side = "left"; opponent_side = "right"
        uploader_user = left_user; opponent_user = right_user
    elif right_is_uploader and not left_is_uploader:
        uploader_side = "right"; opponent_side = "left"
        uploader_user = right_user; opponent_user = left_user
    else:
        # Ambiguous—fallback to exact match first, else mark for review
        if left_user.strip().lower() == uploaderGameUser.strip().lower():
            uploader_side = "left"; opponent_side = "right"
            uploader_user = left_user; opponent_user = right_user
        elif right_user.strip().lower() == uploaderGameUser.strip().lower():
            uploader_side = "right"; opponent_side = "left"
            uploader_user = right_user; opponent_user = left_user
        else:
            uploader_side = None; opponent_side = None
            uploader_user = left_user; opponent_user = right_user  # still return OCR values

    # Score + full time
    score_txt = ocr_text(crop_roi(img, roi["score_block"]))
    goals_left, goals_right = parse_score(score_txt)
    clock_txt = ocr_text(crop_roi(img, roi["clock_full_time"]))
    clock_norm = normalize_label(clock_txt, { "full_time": labels.get("full_time", []) })
    is_full_time = (clock_norm == "full_time") or ("90" in clock_txt)

    # Stats per side
    shots_left = parse_int_safe(ocr_text(crop_roi(img, roi["left_shots"])))
    shots_right = parse_int_safe(ocr_text(crop_roi(img, roi["right_shots"])))

    acc_left = parse_percent_safe(ocr_text(crop_roi(img, roi["left_shot_accuracy"])))
    acc_right = parse_percent_safe(ocr_text(crop_roi(img, roi["right_shot_accuracy"])))

    pos_left = parse_percent_safe(ocr_text(crop_roi(img, roi["left_possession"])))
    pos_right = parse_percent_safe(ocr_text(crop_roi(img, roi["right_possession"])))

    # Estimated SOT
    sot_left = estimate_sot(shots_left, acc_left)
    sot_right = estimate_sot(shots_right, acc_right)

    # Map to platform sides: SideA = uploader, SideB = opponent
    def pick(side):
        if side == "left":
            return {
                "userName": left_user,
                "goals": goals_left,
                "shotsOnTarget": sot_left,
                "possession": pos_left,
                "raw": { "shots": shots_left, "shotAccuracy": acc_left }
            }
        else:
            return {
                "userName": right_user,
                "goals": goals_right,
                "shotsOnTarget": sot_right,
                "possession": pos_right,
                "raw": { "shots": shots_right, "shotAccuracy": acc_right }
            }

    if uploader_side and opponent_side:
        sideA = pick(uploader_side)
        sideB = pick(opponent_side)
    else:
        # Ambiguous identity—return both sides but mark low confidence
        sideA = pick("left")
        sideB = pick("right")

    winner, tieBreak = compute_winner_dls(sideA, sideB)

    notes = []
    if sideA["raw"]["shots"] is not None and sideA["shotsOnTarget"] is not None and sideA["shotsOnTarget"] > sideA["raw"]["shots"]:
        notes.append("Uploader estimated SOT > shots")
    if sideB["raw"]["shots"] is not None and sideB["shotsOnTarget"] is not None and sideB["shotsOnTarget"] > sideB["raw"]["shots"]:
        notes.append("Opponent estimated SOT > shots")
    if sideA["possession"] is not None and sideB["possession"] is not None:
        total = sideA["possession"] + sideB["possession"]
        if abs(100 - total) > 3:
            notes.append("Possession does not sum to ~100")
    if not (left_is_uploader or right_is_uploader):
        notes.append("Username match ambiguous—manual review may be required")

    filled = sum([1 for v in [
        sideA["goals"], sideB["goals"],
        sideA["shotsOnTarget"], sideB["shotsOnTarget"],
        sideA["possession"], sideB["possession"]
    ] if v is not None])
    confidence = min(0.99, 0.6 + filled * 0.06)
    if not is_full_time:
        confidence -= 0.08
    if not (left_is_uploader or right_is_uploader):
        confidence -= 0.10

    return {
        "game": "dls",
        "teamSize": 1,
        "sideA": sideA,
        "sideB": sideB,
        "meta": {
            "matchId": matchId,
            "bytesHash": bytes_hash(raw_bytes),
            "resolution": f"{img.shape[1]}x{img.shape[0]}",
            "orientation": "landscape" if img.shape[1] >= img.shape[0] else "portrait",
            "isFullTime": is_full_time,
            "clockText": clock_txt,
            "timestamp": exif_time,
            "identity": {
                "leftUserOCR": left_user,
                "rightUserOCR": right_user,
                "uploaderGameUser": uploaderGameUser,
                "opponentGameUser": opponentGameUser,
                "uploaderSide": uploader_side
            }
        },
        "coherence": { "ok": len(notes) == 0, "notes": notes },
        "winner": winner,
        "tieBreak": tieBreak,
        "confidence": round(confidence, 2)
    }


@app.post("/ocr/dls/compare")
async def dls_compare(payload: dict):
    subA, subB = payload["submissions"][0], payload["submissions"][1]
    tsA = subA["meta"].get("timestamp") or (payload.get("serverTimestamps") or [None])[0]
    tsB = subB["meta"].get("timestamp") or (payload.get("serverTimestamps") or [None])[1]

    preferred = "A"
    if subA["meta"].get("isFullTime") and not subB["meta"].get("isFullTime"):
        preferred = "A"
    elif subB["meta"].get("isFullTime") and not subA["meta"].get("isFullTime"):
        preferred = "B"
    else:
        try:
            from datetime import datetime
            a = datetime.fromisoformat((tsA or "").replace("Z",""))
            b = datetime.fromisoformat((tsB or "").replace("Z",""))
            preferred = "A" if a > b else "B"
        except Exception:
            preferred = "A"

    winA, winB = subA.get("winner"), subB.get("winner")
    final_winner = winA if winA == winB and winA is not None else (winA if preferred == "A" else winB)

    confidence = round((subA.get("confidence", 0.6) + subB.get("confidence", 0.6)) / 2.0, 2)
    if (preferred == "A" and subA["meta"].get("isFullTime")) or (preferred == "B" and subB["meta"].get("isFullTime")):
        confidence = min(0.99, confidence + 0.05)

    return {
        "aligned": bool(tsA and tsB),
        "preferred": preferred,
        "winner": final_winner,
        "tieBreak": subA.get("tieBreak") if preferred == "A" else subB.get("tieBreak"),
        "confidence": confidence
    }




app = FastAPI()
app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)

def load_profile_freefire():
    with open("app/profiles/freefire_4v4.json", "r", encoding="utf-8") as f:
        return json.load(f)

@app.post("/ocr/freefire/verify")
async def freefire_verify(
    matchId: str = Form(...),
    userId: str = Form(...),
    uploaderGameUser: str = Form(...),
    opponentGameUser: str = Form(...),
    layoutVersion: str = Form("v1"),
    image: UploadFile = UploadFile(...)
):
    profile = load_profile_freefire()
    roi = profile["roi"]
    img, raw_bytes, exif_time = load_image_bytes(image)

    # OCR usernames + stats
    left_users, right_users = [], []
    left_kills, right_kills = [], []
    left_damage, right_damage = [], []

    for i in range(4):
        left_users.append(ocr_text(crop_roi(img, roi["left_usernames"][i])))
        right_users.append(ocr_text(crop_roi(img, roi["right_usernames"][i])))

        left_kills.append(parse_int_safe(ocr_text(crop_roi(img, roi["left_kills"][i]))))
        right_kills.append(parse_int_safe(ocr_text(crop_roi(img, roi["right_kills"][i]))))

        left_damage.append(parse_int_safe(ocr_text(crop_roi(img, roi["left_damage"][i]))))
        right_damage.append(parse_int_safe(ocr_text(crop_roi(img, roi["right_damage"][i]))))

    # Aggregate team stats
    total_left_kills = sum([k for k in left_kills if k is not None])
    total_right_kills = sum([k for k in right_kills if k is not None])
    total_left_damage = sum([d for d in left_damage if d is not None])
    total_right_damage = sum([d for d in right_damage if d is not None])

    sideA = {
        "userNames": left_users,
        "kills": left_kills,
        "damage": left_damage,
        "totalKills": total_left_kills,
        "totalDamage": total_left_damage,
        "mvp": left_users[0] if left_users else None
    }
    sideB = {
        "userNames": right_users,
        "kills": right_kills,
        "damage": right_damage,
        "totalKills": total_right_kills,
        "totalDamage": total_right_damage,
        "mvp": right_users[0] if right_users else None
    }

    winner, tieBreak = compute_winner_freefire(sideA, sideB)

    notes = []
    if not fuzzy_match(uploaderGameUser, " ".join(sideA["userNames"])):
        notes.append("Uploader username mismatch")
    if not fuzzy_match(opponentGameUser, " ".join(sideB["userNames"])):
        notes.append("Opponent username mismatch")

    confidence = 0.95
    if notes:
        confidence -= 0.15

    return {
        "game": "freefire",
        "teamSize": 4,
        "sideA": sideA,
        "sideB": sideB,
        "winner": winner,
        "tieBreak": tieBreak,
        "confidence": round(confidence, 2),
        "meta": {
            "matchId": matchId,
            "bytesHash": bytes_hash(raw_bytes),
            "resolution": f"{img.shape[1]}x{img.shape[0]}",
            "orientation": "landscape" if img.shape[1] >= img.shape[0] else "portrait",
            "timestamp": exif_time
        },
        "coherence": { "ok": len(notes) == 0, "notes": notes }
    }

@app.post("/ocr/freefire/compare")
async def freefire_compare(payload: dict):
    subA, subB = payload["submissions"][0], payload["submissions"][1]
    tsA = subA["meta"].get("timestamp") or (payload.get("serverTimestamps") or [None])[0]
    tsB = subB["meta"].get("timestamp") or (payload.get("serverTimestamps") or [None])[1]

    preferred = "A"
    try:
        from datetime import datetime
        a = datetime.fromisoformat((tsA or "").replace("Z",""))
        b = datetime.fromisoformat((tsB or "").replace("Z",""))
        preferred = "A" if a > b else "B"
    except Exception:
        preferred = "A"

    winA, winB = subA.get("winner"), subB.get("winner")
    final_winner = winA if winA == winB and winA is not None else (winA if preferred == "A" else winB)

    confidence = round((subA.get("confidence", 0.6) + subB.get("confidence", 0.6)) / 2.0, 2)
    if preferred == "A" and winA is not None:
        confidence = min(0.99, confidence + 0.05)
    elif preferred == "B" and winB is not None:
        confidence = min(0.99, confidence + 0.05)

    return {
        "aligned": bool(tsA and tsB),
        "preferred": preferred,
        "winner": final_winner,
        "tieBreak": subA.get("tieBreak") if preferred == "A" else subB.get("tieBreak"),
        "confidence": confidence
    }



from .ocr import load_image_bytes, crop_roi, ocr_text, bytes_hash
from .validators import parse_int_safe, fuzzy_match
from .winner import compute_winner_freefire

app = FastAPI()

# Utility: load profile by team size
def load_profile_freefire(team_size: int):
    path = f"app/profiles/freefire_{team_size}v{team_size}.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# ---------- VERIFY ROUTES ----------

@app.post("/ocr/freefire/verify/1")
async def freefire_verify_1v1(
    matchId: str = Form(...),
    userId: str = Form(...),
    uploaderGameUser: str = Form(...),
    opponentGameUser: str = Form(...),
    image: UploadFile = UploadFile(...)
):
    return await freefire_verify_generic(1, matchId, userId, uploaderGameUser, opponentGameUser, image)

@app.post("/ocr/freefire/verify/2")
async def freefire_verify_2v2(
    matchId: str = Form(...),
    userId: str = Form(...),
    uploaderGameUser: str = Form(...),
    opponentGameUser: str = Form(...),
    image: UploadFile = UploadFile(...)
):
    return await freefire_verify_generic(2, matchId, userId, uploaderGameUser, opponentGameUser, image)

# ---------- COMPARE ROUTES ----------

@app.post("/ocr/freefire/compare/1")
async def freefire_compare_1v1(payload: dict):
    return freefire_compare_generic(1, payload)

@app.post("/ocr/freefire/compare/2")
async def freefire_compare_2v2(payload: dict):
    return freefire_compare_generic(2, payload)

# ---------- GENERIC VERIFY FUNCTION ----------

async def freefire_verify_generic(team_size, matchId, userId, uploaderGameUser, opponentGameUser, image):
    profile = load_profile_freefire(team_size)
    roi = profile["roi"]
    img, raw_bytes, exif_time = load_image_bytes(image)

    left_users, right_users = [], []
    left_kills, right_kills = [], []
    left_damage, right_damage = [], []

    for i in range(team_size):
        left_users.append(ocr_text(crop_roi(img, roi["left_usernames"][i])))
        right_users.append(ocr_text(crop_roi(img, roi["right_usernames"][i])))

        left_kills.append(parse_int_safe(ocr_text(crop_roi(img, roi["left_kills"][i]))))
        right_kills.append(parse_int_safe(ocr_text(crop_roi(img, roi["right_kills"][i]))))

        left_damage.append(parse_int_safe(ocr_text(crop_roi(img, roi["left_damage"][i]))))
        right_damage.append(parse_int_safe(ocr_text(crop_roi(img, roi["right_damage"][i]))))

    sideA = {
        "userNames": left_users,
        "kills": left_kills,
        "damage": left_damage,
        "totalKills": sum([k for k in left_kills if k is not None]),
        "totalDamage": sum([d for d in left_damage if d is not None]),
        "mvp": left_users[0] if left_users else None
    }
    sideB = {
        "userNames": right_users,
        "kills": right_kills,
        "damage": right_damage,
        "totalKills": sum([k for k in right_kills if k is not None]),
        "totalDamage": sum([d for d in right_damage if d is not None]),
        "mvp": right_users[0] if right_users else None
    }

    winner, tieBreak = compute_winner_freefire(sideA, sideB)

    notes = []
    if not fuzzy_match(uploaderGameUser, " ".join(sideA["userNames"])):
        notes.append("Uploader username mismatch")
    if not fuzzy_match(opponentGameUser, " ".join(sideB["userNames"])):
        notes.append("Opponent username mismatch")

    confidence = 0.95
    if notes:
        confidence -= 0.15

    return {
        "game": "freefire",
        "teamSize": team_size,
        "sideA": sideA,
        "sideB": sideB,
        "winner": winner,
        "tieBreak": tieBreak,
        "confidence": round(confidence, 2),
        "meta": {
            "matchId": matchId,
            "bytesHash": bytes_hash(raw_bytes),
            "resolution": f"{img.shape[1]}x{img.shape[0]}",
            "orientation": "landscape" if img.shape[1] >= img.shape[0] else "portrait",
            "timestamp": exif_time
        },
        "coherence": { "ok": len(notes) == 0, "notes": notes }
    }

# ---------- GENERIC COMPARE FUNCTION ----------

def freefire_compare_generic(team_size, payload: dict):
    subA, subB = payload["submissions"][0], payload["submissions"][1]
    tsA = subA["meta"].get("timestamp")
    tsB = subB["meta"].get("timestamp")

    preferred = "A"
    try:
        from datetime import datetime
        a = datetime.fromisoformat((tsA or "").replace("Z",""))
        b = datetime.fromisoformat((tsB or "").replace("Z",""))
        preferred = "A" if a > b else "B"
    except Exception:
        preferred = "A"

    winA, winB = subA.get("winner"), subB.get("winner")
    final_winner = winA if winA == winB and winA is not None else (winA if preferred == "A" else winB)

    confidence = round((subA.get("confidence", 0.6) + subB.get("confidence", 0.6)) / 2.0, 2)
    if preferred == "A" and winA is not None:
        confidence = min(0.99, confidence + 0.05)
    elif preferred == "B" and winB is not None:
        confidence = min(0.99, confidence + 0.05)

    return {
        "aligned": bool(tsA and tsB),
        "preferred": preferred,
        "winner": final_winner,
        "tieBreak": subA.get("tieBreak") if preferred == "A" else subB.get("tieBreak"),
        "confidence": confidence
    }

# ---------- VERIFY ROUTES ----------

@app.post("/ocr/freefire/verify/3")
async def freefire_verify_3v3(
    matchId: str = Form(...),
    userId: str = Form(...),
    uploaderGameUser: str = Form(...),
    opponentGameUser: str = Form(...),
    image: UploadFile = UploadFile(...)
):
    return await freefire_verify_generic(3, matchId, userId, uploaderGameUser, opponentGameUser, image)

# ---------- COMPARE ROUTES ----------

@app.post("/ocr/freefire/compare/3")
async def freefire_compare_3v3(payload: dict):
    return freefire_compare_generic(3, payload)

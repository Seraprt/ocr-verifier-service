def compute_winner_sports(a, b, game, allow_penalties=False, penaltiesA=None, penaltiesB=None):
  # Primary: goals
  if a["goals"] is not None and b["goals"] is not None:
    if a["goals"] > b["goals"]: return "A", "goals"
    if b["goals"] > a["goals"]: return "B", "goals"

  # Draw logic
  if allow_penalties and penaltiesA is not None and penaltiesB is not None:
    if penaltiesA > penaltiesB: return "A", "penalties"
    if penaltiesB > penaltiesA: return "B", "penalties"

  if allow_penalties and game == "efootball" and penaltiesA is None and penaltiesB is None:
    return None, "penalties_required"

  # Percent scoring (fcm/dls only)
  if game in ["fcm", "dls"]:
    shots_weight = 2
    a_score = (a.get("shotsOnTarget") or 0) * shots_weight + (1 if (a.get("possession") or 0) > (b.get("possession") or 0) else 0)
    b_score = (b.get("shotsOnTarget") or 0) * shots_weight + (1 if (b.get("possession") or 0) > (a.get("possession") or 0) else 0)
    if a_score > b_score: return "A", "percent_scoring"
    if b_score > a_score: return "B", "percent_scoring"
    return None, "second_leg_required"

def compute_winner_fcm(a, b):
    # Primary: goals
    if a["goals"] is not None and b["goals"] is not None:
        if a["goals"] > b["goals"]: return "A", "goals"
        if b["goals"] > a["goals"]: return "B", "goals"

    # Draw -> percent scoring
    shots_weight = 2
    a_score = (a.get("shotsOnTarget") or 0) * shots_weight + (1 if (a.get("possession") or 0) > (b.get("possession") or 0) else 0)
    b_score = (b.get("shotsOnTarget") or 0) * shots_weight + (1 if (b.get("possession") or 0) > (a.get("possession") or 0) else 0)

    if a_score > b_score: return "A", "percent_scoring"
    if b_score > a_score: return "B", "percent_scoring"

    return None, "second_leg_required"





def compute_winner_dls(a, b):
    # Primary: goals
    if a["goals"] is not None and b["goals"] is not None:
        if a["goals"] > b["goals"]: return "A", "goals"
        if b["goals"] > a["goals"]: return "B", "goals"

    # Draw -> percent scoring
    shots_weight = 2
    a_score = (a.get("shotsOnTarget") or 0) * shots_weight + (1 if (a.get("possession") or 0) > (b.get("possession") or 0) else 0)
    b_score = (b.get("shotsOnTarget") or 0) * shots_weight + (1 if (b.get("possession") or 0) > (a.get("possession") or 0) else 0)

    if a_score > b_score: return "A", "percent_scoring"
    if b_score > a_score: return "B", "percent_scoring"

    return None, "second_leg_required"

def compute_winner_freefire(sideA, sideB):
    if sideA["totalKills"] > sideB["totalKills"]:
        return "A", "kills"
    elif sideB["totalKills"] > sideA["totalKills"]:
        return "B", "kills"
    else:
        # tie-breaker: damage
        if sideA["totalDamage"] > sideB["totalDamage"]:
            return "A", "damage"
        elif sideB["totalDamage"] > sideA["totalDamage"]:
            return "B", "damage"
        else:
            return None, "ambiguous"


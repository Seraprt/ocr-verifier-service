def efootball_profile(version="v1"):
  # normalized ROIs, adjustable after more samples
  return {
    "roi": {
      "title_full_time": [0.40, 0.18, 0.60, 0.24],
      "teamA_user": [0.08, 0.08, 0.32, 0.14],
      "teamB_user": [0.68, 0.08, 0.92, 0.14],
      "teamA_goals": [0.45, 0.08, 0.48, 0.14],
      "teamB_goals": [0.52, 0.08, 0.55, 0.14],
      "teamA_possession": [0.20, 0.26, 0.28, 0.30],
      "teamB_possession": [0.72, 0.26, 0.80, 0.30],
      "teamA_shots_on_target": [0.20, 0.34, 0.28, 0.38],
      "teamB_shots_on_target": [0.72, 0.34, 0.80, 0.38]
    }
  }

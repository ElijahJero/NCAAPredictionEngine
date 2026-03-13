import random
from collections import defaultdict


def compute_strength(stats: dict, weights: dict) -> float:
    """
    weights: {label: (stat_key, weight_value, positive_bool)}
    positive=True  → higher is better (adds to score)
    positive=False → lower is better  (subtracts from score)
    """
    score = 0.0
    for _label, (key, w, positive) in weights.items():
        val = stats.get(key, 0.0)
        score += w * val if positive else -w * val
    return score


def simulate_game(teamA: dict, teamB: dict, weights: dict, noise: float = 1.0) -> dict:
    sA = compute_strength(teamA["stats"], weights)
    sB = compute_strength(teamB["stats"], weights)
    denom = max(noise, 0.1)
    probA = 1 / (1 + 10 ** ((sB - sA) / (10 * denom)))
    return teamA if random.random() < probA else teamB


def simulate_round(teams: list, weights: dict, noise: float) -> list:
    winners = []
    for i in range(0, len(teams) - 1, 2):
        winners.append(simulate_game(teams[i], teams[i + 1], weights, noise))
    if len(teams) % 2 == 1:
        winners.append(teams[-1])
    return winners


def simulate_tournament(teams: list, weights: dict, noise: float) -> dict:
    current = teams[:]
    while len(current) > 1:
        current = simulate_round(current, weights, noise)
    return current[0]


def monte_carlo(teams: list, weights: dict, runs: int = 1000,
                noise: float = 1.0, progress_cb=None) -> dict[str, int]:
    champions: dict[str, int] = defaultdict(int)
    for i in range(runs):
        champ = simulate_tournament(teams, weights, noise)
        champions[champ["name"]] += 1
        if progress_cb and (i + 1) % max(1, runs // 100) == 0:
            progress_cb((i + 1) / runs)
    return dict(champions)

# ─────────────────────────────────────────────────────────────────────────────
# MAIN APPLICATION
# ─────────────────────────────────────────────────────────────────────────────

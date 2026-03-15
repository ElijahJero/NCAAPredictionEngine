import requests

from constants import TEAM_LIST_URL


def get_teams(limit: int = 64) -> list[dict]:
    """
    Fetch the complete list of NCAA men's basketball teams by paginating
    through ESPN's teams endpoint.  The API limits results per page, so we
    keep requesting incremental pages until one returns an empty team list.

    Args:
        limit: Maximum number of teams to return.  Pass a large value (e.g.
               500) to retrieve every available team.

    Returns:
        A list of team dicts, each with keys: id, name, abbreviation, color.
    """
    seen_ids: set[str] = set()
    out: list[dict] = []
    page = 1

    while True:
        r = requests.get(TEAM_LIST_URL, params={"page": page}, timeout=15)
        r.raise_for_status()
        teams_raw = r.json()["sports"][0]["leagues"][0]["teams"]

        if not teams_raw:
            break

        for t in teams_raw:
            team = t["team"]
            team_id = team["id"]
            if team_id in seen_ids:
                continue
            seen_ids.add(team_id)
            out.append({
                "id":           team_id,
                "name":         team["displayName"],
                "abbreviation": team.get("abbreviation", ""),
                "color":        f"#{team.get('color', '888888')}",
            })
            if len(out) >= limit:
                return out

        page += 1

    return out


def get_team_stats(team_id: str) -> dict:
    """
    Fetch team statistics from ESPN and return a flat {stat_name: value} dict.

    The ESPN endpoint returns nested categories, each with a `stats` list of
    objects that look like:
        {"name": "avgPoints", "value": 78.59, ...}

    We flatten all categories into one dict keyed by `name`.

    NOTE: Percentage stats such as `fieldGoalPct`, `freeThrowPct`, and
    `threePointFieldGoalPct` are returned as 0–100 values (e.g. 45.4, not 0.454).
    The display layer must format them accordingly (divide by 100 before using
    Python's `:.1%` formatter, or display as plain numbers with a `%` suffix).
    """
    url = (
        "https://site.api.espn.com/apis/site/v2/sports/basketball/"
        f"mens-college-basketball/teams/{team_id}/statistics"
    )
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    data = r.json()

    stats: dict[str, float] = {}

    # The response shape is: data["results"]["stats"]["categories"][*]["stats"][*]
    # Defensively handle both the wrapped and unwrapped variants.
    root = data.get("results", data)
    stats_root = root.get("stats", {})
    categories = stats_root.get("categories", [])

    for category in categories:
        for s in category.get("stats", []):
            try:
                stats[s["name"]] = float(s["value"])
            except (KeyError, TypeError, ValueError):
                pass

    # ESPN does not expose opponent PPG directly in the team stats endpoint.
    # We leave "avgPointsAllowed" absent; compute_strength handles missing keys
    # gracefully (defaults to 0.0).  Users can disable that weight or it will
    # simply not contribute.

    return stats

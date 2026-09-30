"""Learn relative ordering only from changes since a verified playlist write.

These are proposed state changes. The caller commits them only after Spotify
readback, just like the rest of rotation history. No artist/genre extrapolation
or assertion about who dragged which song is made from an ambiguous reorder.
"""
from datetime import datetime, timedelta


def observe_order(state, current_order, now):
    previous = state.get("verified_order")
    if previous is None:
        return []
    # Compare shared members: an insertion or deletion shifts absolute ranks
    # without providing evidence about relative taste.
    shared = set(previous) & set(current_order)
    before = [u for u in previous if u in shared]
    after = [u for u in current_order if u in shared]
    if before == after:
        return []
    positions = {u: i for i, u in enumerate(before)}
    relevant = set(previous[:10]) | set(current_order[:10])
    events = []
    for i, winner in enumerate(after):
        for loser in after[i + 1:]:
            if (winner in relevant or loser in relevant) and positions[winner] > positions[loser]:
                events.append({"preferred": winner, "over": loser, "at": now.isoformat()})
    recent = [e for e in state.get("order_preferences", [])
              if now - datetime.fromisoformat(e["at"]) < timedelta(days=180)]
    state["order_preferences"] = (recent + events)[-500:]
    return events


def preference_scores(state, now):
    scores = {}
    for e in state.get("order_preferences", []):
        age = max(0, (now - datetime.fromisoformat(e["at"])).total_seconds() / 86400)
        if age >= 180:
            continue
        weight = 0.5 ** (age / 42)
        scores[e["preferred"]] = scores.get(e["preferred"], 0) + weight
        scores[e["over"]] = scores.get(e["over"], 0) - weight
    # Moving one song across many others must not overwhelm listening evidence.
    return {uri: max(-1.0, min(1.0, value / 5)) for uri, value in scores.items()}


def feature_top_ten(tracks, live_order, state, signals, now, *, rotate):
    """Choose a fresh opening from already-selected tracks; never add membership.

    Listening is primary, release freshness a tie-breaker, and relative manual
    edits a bounded bonus. No popularity, trend, or unseen-listening claims.
    """
    by_uri = {t.uri: t for t in tracks}
    if not rotate:
        # Preserve manual edits on repeat/midweek runs, including their top ten.
        ordered = [by_uri[u] for u in live_order if u in by_uri]
        ordered += [t for t in tracks if t.uri not in set(live_order)]
        return ordered
    preferences = preference_scores(state, now)
    history = state.setdefault("featured_weeks", {})
    monday = (now - timedelta(days=now.weekday())).date().isoformat()
    last_monday = (now - timedelta(days=now.weekday()+7)).date().isoformat()

    def resting(t):
        h = history.get(t.uri, {})
        return h.get("week") == last_monday and h.get("streak", 0) >= 2

    def score(t):
        tid = t.uri.rsplit(":", 1)[-1]
        rank = signals.top_track_ranks.get(tid)
        listening = (4 * (51 - min(50, max(1, rank))) / 50 if rank else
                     2 if tid in signals.top_track_ids else 0)
        recent = 0.5 if tid in signals.recently_played_ids else 0
        try:
            released = datetime.fromisoformat(t.release_date).replace(tzinfo=now.tzinfo)
            freshness = max(0, 1 - max(0, (now-released).days) / 90) * 0.5
        except ValueError:
            freshness = 0
        return listening + recent + preferences.get(t.uri, 0) + freshness

    candidates = sorted(tracks, key=lambda t: (
        resting(t), -score(t), history.get(t.uri, {}).get("week", ""), t.uri))
    front, artists = [], set()
    for t in candidates:
        artist = t.artists.split(", ")[0].casefold()
        if resting(t) or artist in artists:
            continue
        front.append(t)
        artists.add(artist)
        if len(front) == min(10, len(tracks)):
            break
    ids = {t.uri for t in front}
    for t in front:
        old = history.get(t.uri, {})
        history[t.uri] = {"week": monday, "streak": old.get("streak", 0)+1
                         if old.get("week") == last_monday else 1}
    # If constraints exhaust the candidates, the body still fills the playlist.
    return front + [t for t in tracks if t.uri not in ids]

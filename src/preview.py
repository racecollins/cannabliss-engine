"""Readable before/after reports without changing playlist history."""

from pathlib import Path
import json


def write_preview(result, current_tracks, path):
    before = {t.uri: (i + 1, t) for i, t in enumerate(current_tracks)}
    after = {t.uri for t in result.ordered_tracks}
    rows = [{"position": i + 1, "previous_position": before.get(t.uri, (None,))[0],
             "name": t.name, "artists": t.artists, "uri": t.uri,
             "reason": result.reasons.get(t.uri, "Retained")}
            for i, t in enumerate(result.ordered_tracks)]
    removed = [{"position": pos, "name": t.name, "artists": t.artists, "uri": uri}
               for uri, (pos, t) in before.items() if uri not in after]
    payload = {"preview_only": True, "bootstrap": result.bootstrap, "tracks": rows,
               "removed": removed, "summary": result.summary}
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.with_suffix(".json").write_text(json.dumps(payload, indent=2) + "\n")
    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")
    lines = ["# Cannabliss refresh preview", "", "Preview only — Spotify has not been changed.", "",
             f"{len(rows)} songs · {result.new_track_count} automatic additions · {len(removed)} removals", ""]
    if result.bootstrap:
        lines += ["No trustworthy saved baseline exists. Current songs are protected for 14 days; "
                  "their Spotify addition dates determine initial priority. Those dates may reflect "
                  "earlier automated rewrites, so review this first ordering carefully.", ""]
    lines += ["| Next | Previous | Song | Artist | Reason |", "|---:|---:|---|---|---|"]
    for row in rows:
        lines.append("| " + " | ".join(cell(row[k] if row[k] is not None else "New")
                      for k in ("position", "previous_position", "name", "artists", "reason")) + " |")
    lines += ["", "## Leaving rotation", ""]
    lines += [f"- {cell(t['name'])} — {cell(t['artists'])} (previously {t['position']})" for t in removed] or ["None."]
    destination.with_suffix(".md").write_text("\n".join(lines) + "\n")

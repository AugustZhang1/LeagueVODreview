"""Fetch recent ranked solo games through Challenger players and report what the events look like.

    python scripts/fetch_samples.py --platform na1 --games 20 --save 3

Saves `--save` match + timeline pairs to tests/fixtures/real/ and writes REPORT.md next to them.
Needs RIOT_API_KEY in .env.
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

from lolreview.constants import QUEUE_RANKED_SOLO
from lolreview.riot import RiotClient, cluster_for

OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "real"

KNOWN_EVENTS = {
    "CHAMPION_KILL",
    "CHAMPION_SPECIAL_KILL",
    "ELITE_MONSTER_KILL",
    "BUILDING_KILL",
    "TURRET_PLATE_DESTROYED",
    "DRAGON_SOUL_GIVEN",
    "GAME_END",
    "ITEM_PURCHASED",
    "ITEM_SOLD",
    "ITEM_DESTROYED",
    "ITEM_UNDO",
    "SKILL_LEVEL_UP",
    "LEVEL_UP",
    "WARD_PLACED",
    "WARD_KILL",
    "PAUSE_END",
    "OBJECTIVE_BOUNTY_PRIZE",
    "OBJECTIVE_BOUNTY_FINISH",
    "OBJECTIVE_BOUNTY_PRESTART",
    "CHAMPION_TRANSFORM",
}


def _events(timeline: dict):
    for frame in timeline["info"]["frames"]:
        yield from frame.get("events", [])


def _clock(ms: int) -> str:
    s = int(ms // 1000)
    return f"{s // 60}:{s % 60:02d}"


def _fmt(obj) -> str:
    return json.dumps(obj, sort_keys=True)


def _positions(match: dict, timeline: dict):
    for frame in timeline["info"]["frames"]:
        for pf in frame.get("participantFrames", {}).values():
            if "position" in pf:
                yield pf["position"]
        for ev in frame.get("events", []):
            if "position" in ev:
                yield ev["position"]


def _monster_label(ev: dict) -> str:
    sub = ev.get("monsterSubType")
    return f"{ev.get('monsterType')}/{sub}" if sub else str(ev.get("monsterType"))


def build_report(games: list[tuple[dict, dict]]) -> str:
    """Markdown summary of what the events in `games` (a list of (match, timeline)) contain."""
    fields: dict[str, set[str]] = defaultdict(set)
    counts: dict[str, int] = defaultdict(int)
    examples: dict[str, dict] = {}
    monster_types: set[str] = set()
    monster_subtypes: set[str] = set()
    first_kill: dict[str, int] = {}
    building_samples: list[str] = []
    building_agree = building_total = 0
    versions: set[str] = set()
    xs: list[int] = []
    ys: list[int] = []
    buff_hints: list[str] = []

    for match, timeline in games:
        info = match["info"]
        versions.add(str(info.get("gameVersion")))
        team_of = {p["participantId"]: p["teamId"] for p in info["participants"]}
        for p in _positions(match, timeline):
            xs.append(p["x"])
            ys.append(p["y"])
        end_ms = None
        for ev in _events(timeline):
            t = ev["type"]
            counts[t] += 1
            fields[t].update(ev)
            examples.setdefault(t, ev)
            if "BUFF" in t.upper() or any("buff" in k.lower() for k in ev):
                buff_hints.append(f"{t}: {_fmt(ev)}")
            if t == "GAME_END":
                end_ms = ev["timestamp"]
            if t == "ELITE_MONSTER_KILL":
                if "monsterType" in ev:
                    monster_types.add(str(ev["monsterType"]))
                if "monsterSubType" in ev:
                    monster_subtypes.add(str(ev["monsterSubType"]))
                label = _monster_label(ev)
                first_kill[label] = min(first_kill.get(label, ev["timestamp"]), ev["timestamp"])
                if ev.get("monsterType") in ("BARON_NAKSHOR", "ELDER_DRAGON") or (
                    ev.get("monsterSubType") == "ELDER_DRAGON"
                ):
                    end = end_ms or timeline["info"]["frames"][-1]["timestamp"]
                    buff_hints.append(
                        f"{label} killed at {_clock(ev['timestamp'])}, game ends {_clock(end)}"
                        " (buff length is not an event; read it off the patch notes or replay)"
                    )
            if t == "BUILDING_KILL":
                building_total += 1
                killer_team = team_of.get(ev.get("killerId"))
                if killer_team is not None and killer_team != ev.get("teamId"):
                    building_agree += 1
                if len(building_samples) < 3:
                    building_samples.append(
                        f"- {info.get('gameId')} {_clock(ev['timestamp'])}: "
                        f"`{ev.get('buildingType')}` teamId={ev.get('teamId')}, "
                        f"killerId={ev.get('killerId')} (killer team {killer_team})"
                    )

    kinds_seen = set(counts)
    has_monster = lambda name: any(name in m for m in monster_types | monster_subtypes)  # noqa: E731
    unknown = sorted(kinds_seen - KNOWN_EVENTS)

    out = ["# Real data report", "", f"Games: {len(games)}", ""]

    out += ["## Event types", ""]
    for t in sorted(counts):
        out += [
            f"### {t} ({counts[t]})",
            "",
            f"Fields: {', '.join(sorted(fields[t]))}",
            "",
            f"Example: `{_fmt(examples[t])}`",
            "",
        ]

    out += [
        "## Monsters",
        "",
        f"monsterType: {', '.join(sorted(monster_types)) or 'none'}",
        "",
        f"monsterSubType: {', '.join(sorted(monster_subtypes)) or 'none'}",
        "",
    ]

    out += ["## BUILDING_KILL teamId", ""]
    out += building_samples or ["No BUILDING_KILL events."]
    if building_total:
        out += [
            "",
            f"teamId differs from the killer's team in {building_agree} of {building_total} "
            "events (all of them means teamId is the team that lost the building).",
        ]
    out.append("")

    out += [
        "## Presence",
        "",
        f"- DRAGON_SOUL_GIVEN: {'yes' if 'DRAGON_SOUL_GIVEN' in kinds_seen else 'no'}",
        f"- GAME_END: {'yes' if 'GAME_END' in kinds_seen else 'no'}",
        f"- Rift Herald: {'yes' if has_monster('RIFTHERALD') else 'no'}",
        f"- Atakhan: {'yes' if has_monster('ATAKHAN') else 'no'}",
        f"- Unknown event types: {', '.join(unknown) if unknown else 'none'}",
        "",
    ]

    out += ["## gameVersion", "", ", ".join(sorted(versions)) or "none", ""]

    out += ["## Position bounds", ""]
    if xs:
        out.append(f"x: {min(xs)} to {max(xs)}, y: {min(ys)} to {max(ys)}")
    else:
        out.append("No positions.")
    out.append("")

    out += ["## Earliest objective kill", ""]
    for label in sorted(first_kill):
        out.append(f"- {label}: {_clock(first_kill[label])} ({first_kill[label] // 1000} s)")
    if not first_kill:
        out.append("No objective kills.")
    out.append("")

    out += ["## Baron / Elder buff hints", ""]
    out += [f"- {h}" for h in buff_hints] or ["None."]
    out.append("")
    return "\n".join(out)


def collect_games(
    client, platform: str, n_games: int, players: int = 25
) -> list[tuple[dict, dict]]:
    """Walk Challenger players and gather up to n_games distinct ranked solo (match, timeline)."""
    cluster = cluster_for(platform)
    league = client.apex_league(platform, "CHALLENGER")
    entries = sorted(league["entries"], key=lambda e: -e.get("leaguePoints", 0))[:players]
    per_player = max(1, -(-n_games // max(1, len(entries))) + 1)
    seen: set[str] = set()
    games: list[tuple[dict, dict]] = []
    for entry in entries:
        puuid = entry.get("puuid")
        if not puuid:
            continue
        for match_id in client.match_ids(cluster, puuid, queue=QUEUE_RANKED_SOLO, count=per_player):
            if match_id in seen:
                continue
            seen.add(match_id)
            match = client.match(cluster, match_id)
            if match["info"].get("queueId") != QUEUE_RANKED_SOLO:
                continue
            games.append((match, client.timeline(cluster, match_id)))
            if len(games) >= n_games:
                return games
    return games


def save_games(games: list[tuple[dict, dict]], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for match, timeline in games:
        match_id = match["metadata"]["matchId"]
        (out / f"{match_id}.match.json").write_text(json.dumps(match), encoding="utf-8")
        (out / f"{match_id}.timeline.json").write_text(json.dumps(timeline), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--platform", default="na1")
    ap.add_argument("--games", type=int, default=20)
    ap.add_argument("--save", type=int, default=3)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)

    client = RiotClient(on_key_error="raise")
    games = collect_games(client, args.platform, args.games)
    save_games(games[: args.save], args.out)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "REPORT.md").write_text(build_report(games), encoding="utf-8")
    print(f"fetched {len(games)} games, saved {min(args.save, len(games))} to {args.out}")


if __name__ == "__main__":
    main()

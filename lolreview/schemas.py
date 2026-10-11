from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Role = Literal["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
Side = Literal["ally", "enemy"]
Grade = Literal["!!", "!", "?", "??"]
ModelKind = Literal["trained", "stub"]


class ModelInfo(BaseModel):
    kind: ModelKind
    version: str
    trained_at: str | None = None
    patches: list[str] | None = None


class Health(BaseModel):
    riot_key: Literal["ok", "expired", "missing"]
    model: ModelInfo


class Rank(BaseModel):
    tier: str
    division: str | None
    lp: int


class GameSummary(BaseModel):
    match_id: str
    participant_id: int
    champion: str
    role: Role | None
    result: Literal["win", "loss", "remake"]
    k: int
    d: int
    a: int
    cs: int
    duration_s: int
    started_at: str
    patch: str
    reviewed: bool


class PlayerGames(BaseModel):
    puuid: str
    riot_id: str
    platform: str
    rank: Rank | None
    games: list[GameSummary]
    next_start: int | None


class ReviewModel(BaseModel):
    kind: ModelKind
    version: str


class ReviewMatch(BaseModel):
    match_id: str
    platform: str
    patch: str
    ddragon_version: str
    started_at: str
    duration_s: int
    result: Literal["win", "loss"]
    surrender: bool
    my_side: Literal["blue", "red"]
    tier_used: str
    tier_note: str | None
    model: ReviewModel
    patch_in_training: bool


class Player(BaseModel):
    participant_id: int
    riot_id: str
    champion: str
    champion_name: str
    role: Role
    team: Side
    is_me: bool


class Building(BaseModel):
    id: str
    team: Side
    kind: Literal["tower", "inhibitor", "nexus"]
    x: float
    y: float


class CurvePoint(BaseModel):
    t: float
    p: float


class GameEvent(BaseModel):
    t: float
    team: Side
    kind: Literal[
        "kill",
        "dragon",
        "elder",
        "baron",
        "herald",
        "grubs",
        "atakhan",
        "tower",
        "inhibitor",
        "plate",
    ]
    killer: int | None = None
    victim: int | None = None
    assists: list[int] | None = None
    detail: str | None = None
    x: float | None = None
    y: float | None = None


class FightDamage(BaseModel):
    participant_id: int
    dealt: int
    taken: int


class Moment(BaseModel):
    id: str
    t_start: float
    t_end: float
    p_before: float
    p_after: float
    delta: float
    grade: Grade | None
    title: str
    zone: str
    involves_me: bool
    events: list[GameEvent]
    damage: list[FightDamage] = []
    kill_gold: int = 0


class PlayerState(BaseModel):
    participant_id: int
    x: float
    y: float
    pos_age_s: float
    level: int
    k: int
    d: int
    a: int
    cs: int
    gold: int
    items: list[int | None]
    trinket: int | None
    quest_item: int | None = None  # boots in the Bot Lane quest's extra slot
    respawn_in_s: float


class Buff(BaseModel):
    kind: Literal["baron", "elder"]
    ends_in_s: float


class TeamState(BaseModel):
    kills: int
    gold: int
    towers: int
    dragons: list[str]
    soul: str | None
    grubs: int
    heralds: int
    barons: int
    buff: Buff | None


class SnapshotTeams(BaseModel):
    ally: TeamState
    enemy: TeamState


class RecentKill(BaseModel):
    x: float
    y: float
    team: Side
    age_s: float


class Objectives(BaseModel):
    dragon_in_s: float  # until the next dragon, or Elder once a team has the soul
    dragon_kind: Literal["dragon", "elder"]
    baron_pit_in_s: float  # until the Baron pit's next monster is up
    baron_pit_kind: Literal["grubs", "herald", "baron"]


class Snapshot(BaseModel):
    t: float
    players: list[PlayerState]
    teams: SnapshotTeams
    buildings_down: list[str]
    recent_kills: list[RecentKill]
    objectives: Objectives | None = None


class GradeCounts(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    great: int = Field(alias="!!")
    good: int = Field(alias="!")
    mistake: int = Field(alias="?")
    blunder: int = Field(alias="??")


class Summary(BaseModel):
    me: GradeCounts
    team: GradeCounts
    biggest_id: str


class WindowOption(BaseModel):
    what: str  # "Dragon", "Baron", "bot outer tower", ...
    value: float  # win chance with it taken minus without, for your team


class ObjectiveWindow(BaseModel):
    """A stretch when the enemy was weak (jungler or 2+ players dead) and something was up."""

    id: str
    t_start: float
    t_end: float
    title: str  # "Enemy Lee Sin dead, Dragon up"
    reason: str  # "Lee Sin dead for 0:31, Zed for 0:12"
    options: list[WindowOption]  # best first
    value: float  # the best option's value
    used: bool  # your team took an objective, tower or plate in it (or within 10 s after)
    taken: list[str]


class Review(BaseModel):
    match: ReviewMatch
    players: list[Player]
    buildings: list[Building]
    curve: list[CurvePoint]
    moments: list[Moment]
    snapshots: list[Snapshot]
    summary: Summary
    windows: list[ObjectiveWindow] = []


class ModelMetrics(BaseModel):
    """metrics.json from training; fields are whatever train.py writes."""

    model_config = ConfigDict(extra="allow")


class ErrorBody(BaseModel):
    code: str
    message: str
    retry_after_s: int | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class ReplayStatus(BaseModel):
    available: bool
    reason: str | None = None


class ReplaySeek(BaseModel):
    match_id: str
    t: float


class ReplaySeekResult(BaseModel):
    ok: bool

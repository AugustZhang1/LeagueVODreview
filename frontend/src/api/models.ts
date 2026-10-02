import type { components } from "./types";

type S = components["schemas"];

export type Health = S["Health"];
export type ModelInfo = S["ModelInfo"];
export type ModelMetrics = S["ModelMetrics"];
export type PlayerGames = S["PlayerGames"];
export type GameSummary = S["GameSummary"];
export type Rank = S["Rank"];
export type Review = S["Review"];
export type ReviewMatch = S["ReviewMatch"];
export type Player = S["Player"];
export type Building = S["Building"];
export type CurvePoint = S["CurvePoint"];
export type Moment = S["Moment"];
export type GameEvent = S["GameEvent"];
export type Snapshot = S["Snapshot"];
export type PlayerState = S["PlayerState"];
export type TeamState = S["TeamState"];
export type GradeCounts = S["GradeCounts"];
export type Role = S["Player"]["role"];
export type Side = S["Player"]["team"];
export type ReplayStatus = S["ReplayStatus"];
export type ReplaySeekResult = S["ReplaySeekResult"];

import type { ModelMetrics } from "../../api/models";

export type MinuteRow = { label: string; lightgbm: number; baseline: number };
export type CalibrationRow = { predicted: number; actual: number; count: number };
export type TierRow = { tier: string; games: number; accuracy: number; logLoss: number };
export type FeatureRow = { feature: string; gain: number; share: number };

export type ModelView = {
  trainedAt: string | null;
  games: number | null;
  patches: string[];
  /** LightGBM accuracy in the 10–15 minute bucket. */
  accuracyAt10: number | null;
  logLoss: number | null;
  baselineLogLoss: number | null;
  minutes: MinuteRow[];
  calibration: CalibrationRow[];
  /** The calibration bin nearest 70%. */
  nearest70: CalibrationRow | null;
  tiers: TierRow[];
  features: FeatureRow[];
};

type Obj = Record<string, unknown>;

const isObj = (v: unknown): v is Obj => typeof v === "object" && v !== null && !Array.isArray(v);
const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);
const list = (v: unknown): Obj[] => (Array.isArray(v) ? v.filter(isObj) : []);

/** "10-15" and "40+" both start at their first number. */
const bucketStart = (label: string) => Number.parseInt(label, 10);

function minuteLabel(row: Obj): string | null {
  return typeof row.bucket === "string" ? row.bucket.replace("-", "–") : null;
}

function minuteRows(lgb: Obj, base: Obj): MinuteRow[] {
  const baseByLabel = new Map<string, number>();
  for (const r of list(base.by_minute)) {
    const label = minuteLabel(r);
    const acc = num(r.accuracy);
    if (label && acc !== null) baseByLabel.set(label, acc);
  }
  const rows: MinuteRow[] = [];
  for (const r of list(lgb.by_minute)) {
    const label = minuteLabel(r);
    const acc = num(r.accuracy);
    const b = label ? baseByLabel.get(label) : undefined;
    if (label && acc !== null && b !== undefined) {
      rows.push({ label, lightgbm: acc, baseline: b });
    }
  }
  return rows;
}

/** Reads `metrics.json` as `training/train.py` writes it. */
export function readMetrics(raw: ModelMetrics): ModelView {
  const m = raw as Obj;
  const models = isObj(m.models) ? m.models : {};
  const lgb = isObj(models.lightgbm) ? models.lightgbm : {};
  const base = isObj(models.baseline) ? models.baseline : {};

  const minutes = minuteRows(lgb, base);
  const at10 = list(lgb.by_minute).find((r) => {
    const label = minuteLabel(r);
    return label !== null && bucketStart(label) === 10;
  });
  const accuracyAt10 = num(at10?.accuracy);

  const lgbOverall = isObj(lgb.overall) ? lgb.overall : {};
  const baseOverall = isObj(base.overall) ? base.overall : {};

  const calibration = list(m.calibration).flatMap((r) => {
    const predicted = num(r.predicted);
    const actual = num(r.actual);
    return predicted !== null && actual !== null
      ? [{ predicted, actual, count: num(r.count) ?? 0 }]
      : [];
  });
  let nearest70: CalibrationRow | null = null;
  for (const c of calibration) {
    if (!nearest70 || Math.abs(c.predicted - 0.7) < Math.abs(nearest70.predicted - 0.7)) {
      nearest70 = c;
    }
  }

  const tiers = list(lgb.by_tier).flatMap((r) => {
    const tier = typeof r.tier === "string" ? r.tier : null;
    const accuracy = num(r.accuracy);
    const logLoss = num(r.log_loss);
    return tier && accuracy !== null && logLoss !== null
      ? [{ tier, games: num(r.games) ?? 0, accuracy, logLoss }]
      : [];
  });

  const importance = list(m.feature_importance).flatMap((r) => {
    const gain = num(r.gain);
    return typeof r.feature === "string" && gain !== null ? [{ feature: r.feature, gain }] : [];
  });
  const totalGain = importance.reduce((s, r) => s + r.gain, 0);
  const features = importance
    .sort((a, b) => b.gain - a.gain)
    .slice(0, 15)
    .map((r) => ({ ...r, share: totalGain > 0 ? r.gain / totalGain : 0 }));

  return {
    trainedAt: typeof m.trained_at === "string" ? m.trained_at : null,
    games: num(m.games),
    patches: Array.isArray(m.patches) ? m.patches.filter((p) => typeof p === "string") : [],
    accuracyAt10,
    logLoss: num(lgbOverall.log_loss),
    baselineLogLoss: num(baseOverall.log_loss),
    minutes,
    calibration,
    nearest70,
    tiers,
    features,
  };
}

export const pct = (v: number) => `${Math.round(v * 100)}%`;
export const pct1 = (v: number) => `${(v * 100).toFixed(1)}%`;
export const featureName = (f: string) => f.replace(/_/g, " ");
export const tierName = (t: string) => t.charAt(0).toUpperCase() + t.slice(1).toLowerCase();

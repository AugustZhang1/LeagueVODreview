import { DEFAULT_PLATFORM, PLATFORMS } from "./platforms";

const RECENT_KEY = "lvr.recent";
const PLATFORM_KEY = "lvr.platform";
const MAX_RECENT = 5;

export type RecentSearch = { platform: string; name: string; tag: string };

export function readRecent(): RecentSearch[] {
  try {
    const raw = localStorage.getItem(RECENT_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter(
        (r): r is RecentSearch =>
          typeof r?.platform === "string" &&
          typeof r?.name === "string" &&
          typeof r?.tag === "string",
      )
      .slice(0, MAX_RECENT);
  } catch {
    return [];
  }
}

export function addRecent(entry: RecentSearch): void {
  const same = (r: RecentSearch) =>
    r.platform === entry.platform &&
    r.name.toLowerCase() === entry.name.toLowerCase() &&
    r.tag.toLowerCase() === entry.tag.toLowerCase();
  const next = [entry, ...readRecent().filter((r) => !same(r))].slice(0, MAX_RECENT);
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify(next));
  } catch {
    // storage unavailable; the page works without it
  }
}

export function readPlatform(): string {
  try {
    const v = localStorage.getItem(PLATFORM_KEY);
    if (v && PLATFORMS.some((p) => p.id === v)) return v;
  } catch {
    // ignore
  }
  return DEFAULT_PLATFORM;
}

export function savePlatform(id: string): void {
  try {
    localStorage.setItem(PLATFORM_KEY, id);
  } catch {
    // ignore
  }
}

export type ParsedRiotId = { name: string; tag: string } | { error: string };

export function parseRiotId(input: string): ParsedRiotId {
  const text = input.trim();
  const at = text.lastIndexOf("#");
  if (at < 0) return { error: "Enter your Riot ID with its tag, like Name#NA1." };
  const name = text.slice(0, at).trim();
  const tag = text.slice(at + 1).trim();
  if (name.length < 1) return { error: "Enter the name before the #." };
  if (name.length > 16) return { error: "The name is up to 16 characters." };
  if (tag.length < 3 || tag.length > 5) return { error: "The tag after # is 3 to 5 characters." };
  return { name, tag };
}

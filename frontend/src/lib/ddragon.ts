const BASE = "https://ddragon.leagueoflegends.com/cdn";

export const championIconUrl = (version: string, champion: string) =>
  `${BASE}/${version}/img/champion/${champion}.png`;

export const itemIconUrl = (version: string, itemId: number) =>
  `${BASE}/${version}/img/item/${itemId}.png`;

export const mapUrl = (version: string) => `${BASE}/${version}/img/map/map11.png`;

/** The champion's default skin splash art (1215x717); not versioned. */
export const splashUrl = (champion: string) => `${BASE}/img/champion/splash/${champion}_0.jpg`;

/** Two letters for the image fallback: "MonkeyKing" gives "MK", "Ahri" gives "Ah". */
export function initials(name: string): string {
  const caps = name.match(/[A-Z]/g);
  if (caps && caps.length >= 2) return caps[0] + caps[1];
  return name.slice(0, 2).replace(/^./, (c) => c.toUpperCase());
}

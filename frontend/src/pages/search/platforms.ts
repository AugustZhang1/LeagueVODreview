export type Platform = { id: string; label: string };

export const PLATFORMS: Platform[] = [
  { id: "na1", label: "NA" },
  { id: "euw1", label: "EUW" },
  { id: "eun1", label: "EUNE" },
  { id: "kr", label: "KR" },
  { id: "jp1", label: "JP" },
  { id: "br1", label: "BR" },
  { id: "la1", label: "LAN" },
  { id: "la2", label: "LAS" },
  { id: "oc1", label: "OCE" },
  { id: "tr1", label: "TR" },
  { id: "ru", label: "RU" },
  { id: "me1", label: "ME" },
  { id: "sg2", label: "SG" },
  { id: "tw2", label: "TW" },
  { id: "vn2", label: "VN" },
];

export const DEFAULT_PLATFORM = "na1";

export function platformLabel(id: string): string {
  const lower = id.toLowerCase();
  return PLATFORMS.find((p) => p.id === lower)?.label ?? id.toUpperCase();
}

/** Win chance (0-1) for blue from its gold lead: even at 0, about 84% at +10k. */
export const winFromLead = (lead: number): number => 1 / (1 + Math.exp(-lead / 5500));

/** Data Dragon version for a patch like "16.20.826.3891". */
export const ddragonVersion = (patch: string): string =>
  `${patch.split(".").slice(0, 2).join(".")}.1`;

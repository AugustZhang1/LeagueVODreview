import { itemIconUrl } from "../lib/ddragon";
import { GameImage } from "./GameImage";

type Props = { version: string; itemId: number | null; name?: string; size?: number };

/** Item icon; an empty slot is a plain `--surface-2` square. */
export function ItemIcon({ version, itemId, name, size = 20 }: Props) {
  if (itemId === null) return <GameImage src={null} label="Empty slot" size={size} />;
  return (
    <GameImage
      src={itemIconUrl(version, itemId)}
      label={name ?? `Item ${itemId}`}
      size={size}
      fallbackText={String(itemId).slice(0, 2)}
    />
  );
}

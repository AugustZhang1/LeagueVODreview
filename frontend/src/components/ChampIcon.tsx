import { championIconUrl } from "../lib/ddragon";
import { GameImage } from "./GameImage";

type Props = {
  version: string;
  champion: string;
  name?: string;
  size?: number;
  ring?: "ally" | "enemy" | "you";
};

/** Round champion icon. `champion` is the Data Dragon id ("MonkeyKing"), `name` the display name. */
export function ChampIcon({ version, champion, name, size = 32, ring }: Props) {
  return (
    <GameImage
      src={championIconUrl(version, champion)}
      label={name ?? champion}
      size={size}
      round
      ring={ring}
    />
  );
}

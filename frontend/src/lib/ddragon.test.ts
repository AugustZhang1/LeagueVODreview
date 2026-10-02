import { describe, expect, it } from "vitest";
import { championIconUrl, initials, itemIconUrl, mapUrl } from "./ddragon";

describe("ddragon", () => {
  it("builds image urls from the game's version", () => {
    expect(championIconUrl("26.19.1", "MonkeyKing")).toBe(
      "https://ddragon.leagueoflegends.com/cdn/26.19.1/img/champion/MonkeyKing.png",
    );
    expect(itemIconUrl("26.19.1", 3089)).toBe(
      "https://ddragon.leagueoflegends.com/cdn/26.19.1/img/item/3089.png",
    );
    expect(mapUrl("26.19.1")).toBe(
      "https://ddragon.leagueoflegends.com/cdn/26.19.1/img/map/map11.png",
    );
  });
  it("makes two-letter fallbacks", () => {
    expect(initials("MonkeyKing")).toBe("MK");
    expect(initials("Ahri")).toBe("Ah");
    expect(initials("zed")).toBe("Ze");
  });
});

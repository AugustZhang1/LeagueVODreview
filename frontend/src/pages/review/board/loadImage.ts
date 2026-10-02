const cache = new Map<string, Promise<HTMLImageElement | null>>();

/** Loads an image once per URL; resolves to null if it fails, so callers can draw a fallback. */
export function loadImage(url: string): Promise<HTMLImageElement | null> {
  let hit = cache.get(url);
  if (!hit) {
    hit = new Promise((resolve) => {
      const img = new Image();
      img.crossOrigin = "anonymous";
      img.onload = () => resolve(img);
      img.onerror = () => resolve(null);
      img.src = url;
    });
    cache.set(url, hit);
  }
  return hit;
}

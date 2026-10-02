import "@testing-library/jest-dom/vitest";

// jsdom has no ResizeObserver; the minimap uses one to size its canvas.
if (!("ResizeObserver" in globalThis)) {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
}

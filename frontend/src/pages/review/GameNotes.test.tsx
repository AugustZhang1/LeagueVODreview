import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { GameNotes } from "./GameNotes";

const key = "lolreview:notes:NA1_1:4";
const box = () => screen.getByLabelText("Your notes on this game");

describe("GameNotes", () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => vi.restoreAllMocks());

  it("saves every change to localStorage", async () => {
    const user = userEvent.setup();
    render(<GameNotes matchId="NA1_1" participantId={4} t={0} />);
    await user.type(box(), "Lost lane");
    expect(localStorage.getItem(key)).toBe("Lost lane");
  });

  it("loads the saved notes on mount", () => {
    localStorage.setItem(key, "Check the jungle timing");
    render(<GameNotes matchId="NA1_1" participantId={4} t={0} />);
    expect(box()).toHaveValue("Check the jungle timing");
  });

  it("Add time appends the current time on a new line", async () => {
    const user = userEvent.setup();
    render(<GameNotes matchId="NA1_1" participantId={4} t={754} />);
    await user.type(box(), "Dive");
    await user.click(screen.getByRole("button", { name: "Add time" }));
    expect(box()).toHaveValue("Dive\n12:34 ");
    expect(localStorage.getItem(key)).toBe("Dive\n12:34 ");
  });

  it("still works when localStorage throws", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("denied");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("denied");
    });
    const user = userEvent.setup();
    render(<GameNotes matchId="NA1_1" participantId={4} t={0} />);
    await user.type(box(), "Still here");
    expect(box()).toHaveValue("Still here");
  });
});

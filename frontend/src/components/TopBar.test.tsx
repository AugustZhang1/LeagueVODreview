import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { MemoryRouter, useLocation } from "react-router-dom";
import { TopBar } from "./TopBar";

function Where() {
  return <p data-testid="where">{useLocation().pathname}</p>;
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <TopBar />
      <Where />
    </MemoryRouter>,
  );
}

const search = () => screen.queryByRole("textbox", { name: "Riot ID" });

beforeEach(() => localStorage.clear());

describe("TopBar", () => {
  it("has no search on the home page", () => {
    renderAt("/");
    expect(search()).not.toBeInTheDocument();
  });

  it("searches from other pages with the last-used server", async () => {
    localStorage.setItem("lvr.platform", "euw1");
    renderAt("/model");
    await userEvent.type(search()!, "Mimic#NA1{Enter}");
    expect(screen.getByTestId("where")).toHaveTextContent("/p/euw1/Mimic/NA1");
    expect(localStorage.getItem("lvr.recent")).toContain("Mimic");
  });

  it("keeps the page when the Riot ID is invalid", async () => {
    renderAt("/model");
    await userEvent.type(search()!, "nohash{Enter}");
    expect(screen.getByTestId("where")).toHaveTextContent("/model");
    expect(search()).toHaveFocus();
  });

  it("focuses the search on a slash and leaves the slash out of it", async () => {
    renderAt("/model");
    await userEvent.keyboard("/");
    expect(search()).toHaveFocus();
    expect(search()).toHaveValue("");
  });
});

import { describe, expect, it } from "vitest";
import { GRADES, gradeColor, gradeName, isGoodGrade, isStrongGrade } from "./grades";

describe("grades", () => {
  it("names each grade", () => {
    expect(GRADES.map(gradeName)).toEqual(["Great", "Good", "Mistake", "Blunder"]);
  });
  it("gives each grade its own colour", () => {
    expect(GRADES.map(gradeColor)).toEqual([
      "var(--grade-great)",
      "var(--grade-good)",
      "var(--grade-mistake)",
      "var(--grade-blunder)",
    ]);
  });
  it("splits good from bad", () => {
    expect(GRADES.filter(isGoodGrade)).toEqual(["!!", "!"]);
  });
  it("marks the strong grades", () => {
    expect(GRADES.filter(isStrongGrade)).toEqual(["!!", "??"]);
  });
});

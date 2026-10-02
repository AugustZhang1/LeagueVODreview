import { describe, expect, it } from "vitest";
import { GRADES, gradeName, isGoodGrade, isStrongGrade } from "./grades";

describe("grades", () => {
  it("names each grade", () => {
    expect(GRADES.map(gradeName)).toEqual(["Great", "Good", "Mistake", "Blunder"]);
  });
  it("splits good from bad", () => {
    expect(GRADES.filter(isGoodGrade)).toEqual(["!!", "!"]);
  });
  it("marks the strong grades", () => {
    expect(GRADES.filter(isStrongGrade)).toEqual(["!!", "??"]);
  });
});

import type { components } from "../api/types";

export type Grade = NonNullable<components["schemas"]["Moment"]["grade"]>;

export const GRADES: Grade[] = ["!!", "!", "?", "??"];

const NAMES: Record<Grade, string> = {
  "!!": "Great",
  "!": "Good",
  "?": "Mistake",
  "??": "Blunder",
};

export function gradeName(grade: Grade): string {
  return NAMES[grade];
}

/** Good grades are blue ("good for you"), bad ones red. */
export function isGoodGrade(grade: Grade): boolean {
  return grade === "!!" || grade === "!";
}

/** Strong grades (!! and ??) are filled badges and filled graph dots. */
export function isStrongGrade(grade: Grade): boolean {
  return grade === "!!" || grade === "??";
}

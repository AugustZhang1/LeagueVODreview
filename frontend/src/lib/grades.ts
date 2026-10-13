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

const COLORS: Record<Grade, string> = {
  "!!": "var(--grade-great)",
  "!": "var(--grade-good)",
  "?": "var(--grade-mistake)",
  "??": "var(--grade-blunder)",
};

/** The grade's colour as a CSS variable, for SVG fills and strokes. */
export function gradeColor(grade: Grade): string {
  return COLORS[grade];
}

/** Good grades are blue ("good for you"), bad ones red. */
export function isGoodGrade(grade: Grade): boolean {
  return grade === "!!" || grade === "!";
}

/** Strong grades (!! and ??) are filled badges and filled graph dots. */
export function isStrongGrade(grade: Grade): boolean {
  return grade === "!!" || grade === "??";
}

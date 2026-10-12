export const DEPARTMENTS = [
  "Computer Science",
  "Information Technology",
  "Electronics and Communication",
  "Mechanical Engineering",
  "Civil Engineering",
  "Electrical Engineering",
  "Business Administration",
  "Commerce",
  "Mathematics",
  "Physics",
  "Chemistry",
] as const;

export type DepartmentName = (typeof DEPARTMENTS)[number];

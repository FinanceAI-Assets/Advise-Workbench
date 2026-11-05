import { redirect } from "next/navigation";

// Moved: this screen lives in the user workspace at /skills.
export default function LegacySkillsPage() {
  redirect("/skills");
}

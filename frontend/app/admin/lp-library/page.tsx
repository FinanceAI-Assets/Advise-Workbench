import { redirect } from "next/navigation";

// Moved: this screen lives in the user workspace at /library.
export default function LegacyLibraryPage() {
  redirect("/library");
}

import { AdminShell } from "@/components/shell/AdminShell";

export default function AdminConsoleLayout({ children }: { children: React.ReactNode }) {
  return <AdminShell>{children}</AdminShell>;
}

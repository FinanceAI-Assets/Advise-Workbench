"use client";

import { AdminShell } from "@/components/shell/AdminShell";
import { PageSkeleton } from "@/components/workbench/PageFrame";
import { useAuth } from "@/lib/auth-context";

// The console is for platform administrators. The API enforces this too; the check here
// only decides what to show.
export default function AdminConsoleLayout({ children }: { children: React.ReactNode }) {
  const { user, ready, token } = useAuth();
  if (!ready || (token && !user)) {
    return (
      <div className="p-6">
        <PageSkeleton />
      </div>
    );
  }
  if (!user) return <PageSkeleton />;
  return <AdminShell>{children}</AdminShell>;
}

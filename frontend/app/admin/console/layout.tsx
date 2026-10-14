"use client";

import Link from "next/link";

import { AdminShell } from "@/components/shell/AdminShell";
import { EmptyState } from "@/components/ui/EmptyState";
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
  if (!user?.isAdmin) {
    return (
      <div className="p-6">
        <EmptyState
          title="Administrator access required"
          description="The admin console is available to platform administrators only."
        >
          <Link href="/engagements">Back to your workspace</Link>
        </EmptyState>
      </div>
    );
  }
  return <AdminShell>{children}</AdminShell>;
}

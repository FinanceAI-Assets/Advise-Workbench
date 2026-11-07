"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { AdminShell } from "@/components/shell/AdminShell";
import { PageSkeleton } from "@/components/workbench/PageFrame";
import { useAuth } from "@/lib/auth-context";

// The console is for platform administrators. The API enforces this too; the check here
// only decides what to show, and sends everyone else back to the user workspace.
export default function AdminConsoleLayout({ children }: { children: React.ReactNode }) {
  const { user, ready, token } = useAuth();
  const router = useRouter();
  const denied = Boolean(user && !user.isAdmin);

  useEffect(() => {
    if (denied) router.replace("/engagements");
  }, [denied, router]);

  if (!ready || (token && !user) || denied) {
    return (
      <div className="p-6">
        <PageSkeleton />
      </div>
    );
  }
  if (!user) return <PageSkeleton />;
  return <AdminShell>{children}</AdminShell>;
}

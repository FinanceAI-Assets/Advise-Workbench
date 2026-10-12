import React from "react";
import { Inter, Open_Sans, JetBrains_Mono } from "next/font/google";

import { ErrorBoundary } from "@/components/ErrorBoundary";
import { QueryProvider } from "@/components/providers/QueryProvider";
import { AppShell } from "@/components/shell/AppShell";
import { GlobalToastListener } from "@/components/toast/GlobalToastListener";
import { AuthProvider } from "@/lib/auth-context";
import "@/styles/globals.css";

const openSans = Open_Sans({
  subsets: ["latin"],
  variable: "--font-open-sans",
});

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains-mono",
});

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${openSans.variable} ${inter.variable} ${jetbrainsMono.variable}`}
    >
      <body suppressHydrationWarning>
        <ErrorBoundary>
          <QueryProvider>
            <AuthProvider>
              <GlobalToastListener />
              <AppShell>{children}</AppShell>
            </AuthProvider>
          </QueryProvider>
        </ErrorBoundary>
      </body>
    </html>
  );
}

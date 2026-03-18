import type { Metadata } from "next";

import "@/app/globals.css";

export const metadata: Metadata = {
  title: "Cannabliss Control Center",
  description: "Weekly playlist intelligence and curation analytics",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="bg-background font-sans text-foreground antialiased">{children}</body>
    </html>
  );
}

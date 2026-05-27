import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Plot Map Builder — BrickBytes",
  description: "Auto Plot Map Builder for BrickBytes admin",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}

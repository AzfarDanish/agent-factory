import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Coloring Factory Village",
  description: "Visual pipeline monitor for the AI Coloring Page Factory",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-gray-950 text-white">{children}</body>
    </html>
  );
}

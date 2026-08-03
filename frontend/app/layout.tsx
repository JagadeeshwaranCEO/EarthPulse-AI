import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "EarthPulse AI — Mission Control",
  description: "Planetary early warning intelligence — prediction, explanation, simulation.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-canvas text-slate-200 antialiased">{children}</body>
    </html>
  );
}

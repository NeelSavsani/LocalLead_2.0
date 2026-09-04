import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LocalLeadPulse — Automated B2B Lead Generator for Website-less Businesses",
  description:
    "AI-powered two-layer lead generation pipeline discovering local businesses without standalone websites, with strict limit controls and CRM Excel export.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-slate-950 text-slate-100 antialiased selection:bg-indigo-500 selection:text-white">
        {children}
      </body>
    </html>
  );
}

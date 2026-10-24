import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Clinic Voice | Never miss a patient's call",
  description:
    "An AI voice receptionist for dental and medical clinics. Answer questions, capture appointment requests, and give your team room to care. Try a 14-day free pilot.",
  applicationName: "Clinic Voice",
  authors: [{ name: "Arthi Arumugam" }],
  openGraph: {
    title: "Clinic Voice | A warm welcome. Every time.",
    description:
      "AI receptionist for clinics: never miss a call. One-week setup, $1,500 once, then $400/month. Start with a 14-day free pilot.",
    type: "website",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#f7f8f2",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ChromaSAR — SAR interpretation with confidence",
  description:
    "Flood mapping and colorization from Sentinel-1 SAR, with calibrated per-pixel " +
    "confidence gating every downstream decision.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

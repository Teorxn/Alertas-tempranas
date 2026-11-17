import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Alertas tempranas | Acompañamiento académico",
  description: "Señales tempranas de acompañamiento académico para docentes.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}

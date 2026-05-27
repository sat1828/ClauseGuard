import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "ClauseGuard — AI Contract Risk Analysis",
  description:
    "AI-powered contract risk analysis for people who can't afford a lawyer. Upload any legal contract and get full risk analysis, plain-English explanations, and safer alternatives in under 60 seconds.",
  keywords: ["contract analysis", "legal AI", "NDA review", "employment contract", "legaltech"],
  openGraph: {
    title: "ClauseGuard",
    description: "AI-powered contract risk analysis",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.className} antialiased bg-gray-50 text-gray-900`}>
        {children}
      </body>
    </html>
  );
}

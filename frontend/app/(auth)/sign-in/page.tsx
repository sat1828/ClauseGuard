/**
 * Sign-In Page
 * ============
 * Clerk-powered authentication page.
 *
 * In production: Replace the placeholder with Clerk's <SignIn /> component.
 * For local dev without Clerk credentials, this page redirects to /dashboard
 * using the dev-user-001 fallback in the auth dependency.
 *
 * To enable Clerk:
 * 1. Set NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY in .env
 * 2. Install @clerk/nextjs: npm install @clerk/nextjs
 * 3. Replace the div below with <SignIn />
 */

import Link from "next/link";
import { Shield } from "lucide-react";

export default function SignInPage() {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-8 w-full max-w-md space-y-6">
        <div className="text-center space-y-2">
          <div className="flex justify-center">
            <Shield className="h-10 w-10 text-blue-600" />
          </div>
          <h1 className="text-2xl font-black text-gray-900">Sign in to ClauseGuard</h1>
          <p className="text-sm text-gray-500">
            AI-powered contract risk analysis
          </p>
        </div>

        {/* 
          PRODUCTION: Replace this section with Clerk's SignIn component:
          
          import { SignIn } from "@clerk/nextjs";
          <SignIn />
          
          LOCAL DEV: Use the button below to bypass auth.
        */}
        <div className="space-y-3">
          <Link
            href="/dashboard"
            className="block w-full text-center bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-4 rounded-xl transition-colors"
          >
            Continue (Dev mode — no auth required)
          </Link>
          <p className="text-xs text-center text-gray-400">
            In production, Clerk authentication is required.
            <br />
            Set NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY to enable.
          </p>
        </div>

        <div className="text-center">
          <p className="text-xs text-gray-400">
            Don&apos;t have an account?{" "}
            <Link href="/sign-up" className="text-blue-600 hover:underline">
              Sign up
            </Link>
          </p>
        </div>

        <p className="text-[10px] text-gray-400 text-center leading-relaxed">
          ClauseGuard is not a law firm. All analysis is informational only.
          Always consult a qualified legal professional.
        </p>
      </div>
    </div>
  );
}

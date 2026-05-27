import Link from "next/link";
import { Shield } from "lucide-react";

export default function SignUpPage() {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-8 w-full max-w-md space-y-6">
        <div className="text-center space-y-2">
          <div className="flex justify-center">
            <Shield className="h-10 w-10 text-blue-600" />
          </div>
          <h1 className="text-2xl font-black text-gray-900">Create your account</h1>
          <p className="text-sm text-gray-500">Start analysing contracts for free</p>
        </div>

        {/*
          PRODUCTION: Replace with Clerk's SignUp component:
          import { SignUp } from "@clerk/nextjs";
          <SignUp />
        */}
        <div className="space-y-3">
          <Link
            href="/dashboard"
            className="block w-full text-center bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-4 rounded-xl transition-colors"
          >
            Continue (Dev mode — no auth required)
          </Link>
        </div>

        <div className="text-center">
          <p className="text-xs text-gray-400">
            Already have an account?{" "}
            <Link href="/sign-in" className="text-blue-600 hover:underline">
              Sign in
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

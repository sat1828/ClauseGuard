import Link from "next/link";
import { Shield, Zap, FileSearch, MessageSquare, AlertTriangle } from "lucide-react";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-white">
      {/* Disclaimer */}
      <div className="bg-amber-50 border-b border-amber-200 py-2 px-4 text-center">
        <p className="text-xs text-amber-800">
          <strong>Legal Disclaimer:</strong> ClauseGuard is not a law firm. All analysis is for
          informational purposes only. Always consult a qualified legal professional.
        </p>
      </div>

      {/* Nav */}
      <nav className="border-b border-gray-100 bg-white/80 backdrop-blur-sm sticky top-0 z-40">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Shield className="h-6 w-6 text-blue-600" />
            <span className="text-xl font-black text-gray-900 tracking-tight">ClauseGuard</span>
          </div>
          <Link
            href="/dashboard"
            className="bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold px-5 py-2.5 rounded-xl transition-colors"
          >
            Try it free →
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-6xl mx-auto px-6 pt-20 pb-16 text-center">
        <div className="inline-flex items-center gap-2 bg-blue-50 border border-blue-200 text-blue-700 text-xs font-semibold px-3 py-1.5 rounded-full mb-8">
          <Zap className="h-3.5 w-3.5" />
          Analyse any contract in under 60 seconds
        </div>

        <h1 className="text-5xl md:text-6xl font-black text-gray-900 leading-tight tracking-tight mb-6">
          AI contract review
          <br />
          <span className="text-blue-600">without the lawyer fees.</span>
        </h1>

        <p className="text-xl text-gray-500 max-w-2xl mx-auto leading-relaxed mb-10">
          Upload any legal contract — employment, NDA, SaaS, lease — and get full risk
          analysis, plain-English explanations, safer alternatives, and a chat interface
          to ask anything. For free.
        </p>

        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <Link
            href="/dashboard"
            className="bg-blue-600 hover:bg-blue-700 text-white font-bold px-8 py-4 rounded-xl text-lg transition-colors shadow-lg shadow-blue-500/20"
          >
            Analyse my contract →
          </Link>
        </div>

        <p className="text-xs text-gray-400 mt-4">
          No signup required to try · Supports PDF, DOCX, TXT
        </p>
      </section>

      {/* Features */}
      <section className="max-w-6xl mx-auto px-6 pb-20">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[
            {
              icon: <FileSearch className="h-6 w-6 text-blue-600" />,
              title: "30 Clause Types",
              desc: "Identifies every critical clause: IP assignment, non-competes, unlimited liability, auto-renewals, and 26 more.",
            },
            {
              icon: <AlertTriangle className="h-6 w-6 text-red-500" />,
              title: "4-Tier Risk Scoring",
              desc: "Every clause scored Low, Medium, High, or Critical with plain-English explanation of what could go wrong.",
            },
            {
              icon: <Shield className="h-6 w-6 text-emerald-600" />,
              title: "Safer Alternatives",
              desc: "For every high-risk clause, get a legally sound replacement and 3 negotiation talking points you can send.",
            },
            {
              icon: <MessageSquare className="h-6 w-6 text-purple-600" />,
              title: "Ask the Contract",
              desc: "Chat with your document. Every answer is grounded in your contract with citations — no hallucinations.",
            },
          ].map((f) => (
            <div
              key={f.title}
              className="bg-gray-50 border border-gray-200 rounded-xl p-6 space-y-3"
            >
              {f.icon}
              <h3 className="font-bold text-gray-900">{f.title}</h3>
              <p className="text-sm text-gray-500 leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-gray-100 py-8 text-center">
        <p className="text-xs text-gray-400 max-w-2xl mx-auto leading-relaxed">
          ClauseGuard is not a law firm and does not provide legal advice. All analysis is for
          informational purposes only and does not constitute legal counsel or create an
          attorney-client relationship. Always consult a qualified legal professional before
          making decisions based on any contract.
        </p>
      </footer>
    </div>
  );
}

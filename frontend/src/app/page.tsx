import Link from "next/link";

export default function Homepage() {
  return (
    <div className="min-h-full flex flex-col bg-stone-50 text-stone-800">
      <header className="bg-white border-b border-stone-200 px-8 py-4 flex items-center justify-between">
        <Link href="/" className="text-2xl font-bold tracking-tight">
          <span className="text-green-700">Try</span>1000
        </Link>
        <div className="flex items-center gap-4">
          <Link href="/auth/login" className="text-sm text-stone-500 hover:text-stone-800 font-medium">Sign In</Link>
          <Link href="/auth/login" className="px-5 py-2.5 bg-green-700 text-white text-sm font-semibold hover:bg-green-800 transition-colors">
            Start Now
          </Link>
        </div>
      </header>

      <section className="flex-1 px-8 py-16">
        <div className="max-w-5xl mx-auto">
          <h1 className="text-6xl font-bold mb-4 leading-tight tracking-tight">
            Design Tactics.<br />Simulate Matches.<br /><span className="text-green-700">Prove They Work.</span>
          </h1>
          <p className="text-xl text-stone-500 mb-2 max-w-2xl">
            Run hundreds of match simulations to test your tactical ideas — without stepping onto the training pitch.
          </p>
          <p className="text-lg text-stone-400 mb-10">No graphics. No animations. Pure tactical depth.</p>

          <div className="grid grid-cols-3 gap-8 mb-12">
            {[
              { step: "01", title: "Design Your Tactic", desc: "Choose a formation, set pressing intensity, define build-up patterns — just like on the tactics board." },
              { step: "02", title: "Run Simulations", desc: "Simulate up to 1,000 matches. Every player makes decisions based on your tactical instructions." },
              { step: "03", title: "Analyse & Improve", desc: "Review AI-generated reports. Identify patterns, fix weaknesses, and iterate." },
            ].map((f) => (
              <div key={f.step}>
                <div className="text-xs text-stone-300 font-mono mb-1.5">{f.step}</div>
                <h3 className="text-lg font-bold mb-1.5">{f.title}</h3>
                <p className="text-base text-stone-500 leading-relaxed">{f.desc}</p>
              </div>
            ))}
          </div>

          <Link href="/auth/login"
            className="inline-flex items-center gap-2 px-8 py-3.5 bg-green-700 text-white font-semibold hover:bg-green-800 transition-colors text-lg">
            Get Started
            <span>→</span>
          </Link>
        </div>
      </section>

      <footer className="border-t border-stone-200 px-8 py-4 text-sm text-stone-400">
        Built for football coaches and performance analysts.
      </footer>
    </div>
  );
}

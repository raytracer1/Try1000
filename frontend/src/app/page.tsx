import Image from "next/image";
import Link from "next/link";
import { Header } from "../components/layout/Header";

export default function Homepage() {
  return (
    <div className="min-h-full flex flex-col text-stone-800">
      <Header />

      {/* Hero */}
      <section className="flex-1 px-8 py-16 lg:py-24">
        <div className="max-w-6xl mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-16 items-center">
            {/* Text */}
            <div>
              <h1 className="text-5xl lg:text-6xl font-bold mb-4 leading-tight tracking-tight">
                Design Tactics.<br />Simulate Matches.<br /><span className="text-green-700">Prove They Work.</span>
              </h1>
              <p className="text-xl text-stone-500 mb-2 max-w-xl">
                Run hundreds of match simulations to test your tactical ideas — without stepping onto the training pitch.
              </p>
              <p className="text-lg text-stone-400 mb-8">No graphics. No animations. Pure tactical depth.</p>
              <Link
                href="/auth/login"
                className="inline-flex items-center gap-2 px-8 py-3.5 bg-green-700 text-white font-semibold hover:bg-green-800 transition-colors text-lg"
              >
                Get Started
                <span>→</span>
              </Link>
            </div>

            {/* Hero image */}
            <div>
              <Image
                src="/imgs/try1000.jpg"
                alt="Try1000 football tactics simulation"
                width={1536}
                height={1024}
                preload
                className="rounded-xl shadow-2xl w-full h-auto"
                sizes="(max-width: 1024px) 100vw, 50vw"
              />
            </div>
          </div>
        </div>
      </section>

      {/* Steps */}
      <div className="bg-white border-y border-stone-200">
        <div className="max-w-6xl mx-auto py-16">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-10">
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
        </div>
      </div>

      {/* Footer */}
      <footer className="border-t border-stone-200 px-8 py-4 text-sm text-stone-400">
        Built for football coaches and performance analysts.
      </footer>
    </div>
  );
}

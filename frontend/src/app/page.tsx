import Link from "next/link";

export default function Homepage() {
  return (
    <div className="flex flex-col min-h-full">
      {/* Header */}
      <header className="border-b border-gray-800 px-8 py-4 flex items-center justify-between">
        <Link href="/" className="text-xl font-bold tracking-tight">
          <span className="text-emerald-400">Try</span>1000
        </Link>
        <div className="flex items-center gap-4">
          <Link href="/auth/login" className="text-sm text-gray-400 hover:text-white transition-colors">Sign In</Link>
          <Link href="/auth/login" className="px-4 py-1.5 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-500 transition-colors">
            Get Started
          </Link>
        </div>
      </header>

      {/* Hero */}
      <section className="flex-1 flex flex-col items-center justify-center text-center px-4 py-20">
        <h1 className="text-6xl font-bold mb-4 tracking-tight">
          <span className="text-emerald-400">Try</span>1000
        </h1>
        <p className="text-2xl text-gray-300 mb-3 max-w-lg">
          AI-Powered Football Tactics Simulation
        </p>
        <p className="text-gray-500 mb-12 max-w-md">
          Design formations. Simulate up to 1,000 matches. Analyze results with AI.
          No 3D graphics — pure tactical depth.
        </p>

        <div className="grid grid-cols-3 gap-6 max-w-3xl w-full mb-16">
          {[
            { icon: "⚽", title: "Tactics Editor", desc: "Choose from 4-3-3, 4-4-2, 3-5-2 and more. Drag players, set pressing intensity, define build-up style." },
            { icon: "▶️", title: "Batch Simulation", desc: "Run 1 to 1,000 matches in minutes. AI-generated player logic adapts to your tactical choices." },
            { icon: "🧠", title: "AI Analysis", desc: "Get detailed reports on attack patterns, defensive weaknesses, and optimization suggestions." },
          ].map((f) => (
            <div key={f.title} className="bg-gray-900 rounded-xl border border-gray-800 p-6 text-left">
              <div className="text-2xl mb-3">{f.icon}</div>
              <h3 className="font-semibold mb-2">{f.title}</h3>
              <p className="text-sm text-gray-400 leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>

        <Link href="/auth/login" className="px-8 py-3 bg-emerald-600 text-white rounded-lg font-medium text-lg hover:bg-emerald-500 transition-colors">
          Start Simulating
        </Link>
      </section>

      {/* Footer */}
      <footer className="border-t border-gray-800 px-8 py-6 text-center text-sm text-gray-500">
        <p>Try1000 — Built for coaches, analysts, and football enthusiasts.</p>
      </footer>
    </div>
  );
}

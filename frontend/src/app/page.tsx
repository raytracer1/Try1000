import Link from "next/link";

export default function Homepage() {
  return (
    <div className="max-w-4xl mx-auto text-center py-16">
      <h1 className="text-5xl font-bold mb-4 tracking-tight">
        <span className="text-emerald-400">Try</span>1000
      </h1>
      <p className="text-xl text-gray-400 mb-3">
        AI-powered football tactics simulation
      </p>
      <p className="text-gray-500 mb-10 max-w-md mx-auto">
        Design tactics. Simulate 1,000 matches. Analyze results. Improve your strategy.
        No graphics — pure tactical experimentation.
      </p>
      <div className="grid grid-cols-3 gap-6 mb-12 max-w-2xl mx-auto text-left">
        {[
          { icon: "⚽", title: "Design", desc: "Choose formations, set pressing intensity, define build-up style" },
          { icon: "▶️", title: "Simulate", desc: "Run 1 to 1,000 matches in minutes with AI-generated player logic" },
          { icon: "📊", title: "Improve", desc: "Get AI analysis reports and optimization suggestions from match data" },
        ].map((f) => (
          <div key={f.title} className="bg-gray-900 rounded-xl border border-gray-800 p-5">
            <div className="text-2xl mb-2">{f.icon}</div>
            <h3 className="font-semibold mb-1">{f.title}</h3>
            <p className="text-xs text-gray-400">{f.desc}</p>
          </div>
        ))}
      </div>
      <Link href="/auth/login" className="inline-block px-8 py-3 bg-emerald-600 text-white rounded-lg font-medium hover:bg-emerald-500 transition-colors">
        Get Started
      </Link>
    </div>
  );
}

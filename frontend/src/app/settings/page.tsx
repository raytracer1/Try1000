"use client";

import { useState } from "react";

export default function SettingsPage() {
  const [llmProvider, setLlmProvider] = useState("anthropic");
  const [llmKey, setLlmKey] = useState("");
  const [llmModel, setLlmModel] = useState("claude-sonnet-5");
  const [simSpeed, setSimSpeed] = useState("fast");
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    localStorage.setItem("llm_provider", llmProvider);
    localStorage.setItem("llm_model", llmModel);
    if (llmKey) localStorage.setItem("llm_api_key", llmKey);
    localStorage.setItem("sim_speed", simSpeed);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Settings</h1>

      <div className="space-y-4">
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
          <h2 className="text-lg font-semibold mb-3">LLM Provider</h2>
          <p className="text-sm text-gray-500 mb-3">Configure an LLM API key to enable Level 2 (AI-generated player logic). Without a key, the engine uses Level 1 (rule-based).</p>

          <label className="text-sm text-gray-400 block mb-1">Provider</label>
          <select className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 mb-3"
            value={llmProvider} onChange={(e) => setLlmProvider(e.target.value)}>
            <option value="anthropic">Anthropic (Claude)</option>
            <option value="openai">OpenAI (GPT)</option>
          </select>

          <label className="text-sm text-gray-400 block mb-1">API Key</label>
          <input type="password" className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 mb-3 font-mono"
            placeholder="sk-..." value={llmKey} onChange={(e) => setLlmKey(e.target.value)} />

          <label className="text-sm text-gray-400 block mb-1">Model</label>
          <input type="text" className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200"
            value={llmModel} onChange={(e) => setLlmModel(e.target.value)} />
        </div>

        <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
          <h2 className="text-lg font-semibold mb-3">Simulation Speed</h2>
          <div className="flex gap-3">
            {[
              { value: "full", label: "Full (1s/tick)", desc: "Best replay quality" },
              { value: "fast", label: "Fast (5s/tick)", desc: "5x faster" },
            ].map((opt) => (
              <button key={opt.value}
                onClick={() => setSimSpeed(opt.value)}
                className={`flex-1 p-3 rounded-lg border text-left text-sm transition-colors ${
                  simSpeed === opt.value
                    ? "border-emerald-500 bg-emerald-500/10 text-emerald-400"
                    : "border-gray-700 bg-gray-800 text-gray-400 hover:border-gray-600"
                }`}>
                <div className="font-medium">{opt.label}</div>
                <div className="text-xs mt-0.5 opacity-70">{opt.desc}</div>
              </button>
            ))}
          </div>
        </div>

        <button onClick={handleSave}
          className="w-full py-2.5 bg-emerald-600 text-white rounded-lg font-medium hover:bg-emerald-500 transition-colors">
          {saved ? "Saved!" : "Save Settings"}
        </button>
        <p className="text-xs text-gray-500 text-center">Settings are stored in your browser&apos;s local storage.</p>
      </div>
    </div>
  );
}

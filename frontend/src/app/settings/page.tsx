"use client";

import { useState, useEffect } from "react";
import { api } from "../../lib/api";

export default function SettingsPage() {
  const [llmProvider, setLlmProvider] = useState("");
  const [llmKey, setLlmKey] = useState("");
  const [llmModel, setLlmModel] = useState("claude-sonnet-5");
  const [hasKey, setHasKey] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    api.getMe().then((user) => {
      setLlmProvider(user.llm_provider || "");
      setLlmModel(user.llm_model || "claude-sonnet-5");
      setHasKey(user.has_llm_key);
    }).catch(() => {});
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.saveLLMSettings({ llm_provider: llmProvider, llm_api_key: llmKey, llm_model: llmModel });
      setHasKey(!!llmKey);
      setMessage("Saved");
    } catch (e: any) { setMessage("Error: " + e.message); }
    finally { setSaving(false); setTimeout(() => setMessage(""), 2000); }
  };

  return (
    <div className="max-w-xl mx-auto">
      <h1 className="text-2xl font-bold mb-6 text-stone-800">Settings</h1>

      <div className="bg-white border border-stone-200 rounded-lg p-5">
        <h2 className="text-lg font-bold mb-1 text-stone-800">LLM Provider</h2>
        <p className="text-sm text-stone-400 mb-4">Configure an API key to enable AI-generated player logic and tactical analysis.</p>

        <label className="text-sm text-stone-500 block mb-1">Provider</label>
        <select className="w-full bg-stone-50 border border-stone-200 rounded px-3 py-2 text-sm text-stone-700 mb-3" value={llmProvider} onChange={(e) => setLlmProvider(e.target.value)}>
          <option value="">None (basic)</option>
          <option value="anthropic">Anthropic (Claude)</option>
          <option value="openai">OpenAI (GPT)</option>
        </select>

        <label className="text-sm text-stone-500 block mb-1">API Key {hasKey && <span className="text-green-700 text-xs">(saved)</span>}</label>
        <input type="password" className="w-full bg-stone-50 border border-stone-200 rounded px-3 py-2 text-sm text-stone-700 mb-3 font-mono"
          placeholder={hasKey ? "••••••" : "sk-..."} value={llmKey} onChange={(e) => setLlmKey(e.target.value)} />

        <label className="text-sm text-stone-500 block mb-1">Model</label>
        <input type="text" className="w-full bg-stone-50 border border-stone-200 rounded px-3 py-2 text-sm text-stone-700 mb-4"
          value={llmModel} onChange={(e) => setLlmModel(e.target.value)} />

        <button onClick={handleSave} disabled={saving}
          className="w-full py-2.5 bg-green-700 text-white font-semibold text-sm hover:bg-green-800 disabled:opacity-50">
          {saving ? "Saving..." : message || "Save Settings"}
        </button>
      </div>
    </div>
  );
}

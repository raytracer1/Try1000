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
      await api.saveLLMSettings({
        llm_provider: llmProvider,
        llm_api_key: llmKey,
        llm_model: llmModel,
      });
      setHasKey(!!llmKey);
      setMessage("Saved!");
    } catch (e: any) {
      setMessage("Error: " + e.message);
    } finally {
      setSaving(false);
      setTimeout(() => setMessage(""), 2000);
    }
  };

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Settings</h1>

      <div className="space-y-4">
        <div className="bg-gray-900 rounded-xl border border-gray-800 p-4">
          <h2 className="text-lg font-semibold mb-3">LLM Provider</h2>
          <p className="text-sm text-gray-500 mb-3">
            Your API key is stored securely in your account and only sent to the local engine when executing AI tasks. Never exposed to the frontend.
          </p>

          <label className="text-sm text-gray-400 block mb-1">Provider</label>
          <select className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 mb-3"
            value={llmProvider} onChange={(e) => setLlmProvider(e.target.value)}>
            <option value="">None (Level 1 only)</option>
            <option value="anthropic">Anthropic (Claude)</option>
            <option value="openai">OpenAI (GPT)</option>
          </select>

          <label className="text-sm text-gray-400 block mb-1">
            API Key {hasKey && <span className="text-emerald-400 text-xs">(saved)</span>}
          </label>
          <input type="password"
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 mb-3 font-mono"
            placeholder={hasKey ? "•••••• (leave blank to keep current)" : "sk-..."}
            value={llmKey} onChange={(e) => setLlmKey(e.target.value)} />

          <label className="text-sm text-gray-400 block mb-1">Model</label>
          <input type="text" className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200"
            value={llmModel} onChange={(e) => setLlmModel(e.target.value)} />
        </div>

        <button onClick={handleSave} disabled={saving}
          className="w-full py-2.5 bg-emerald-600 text-white rounded-lg font-medium hover:bg-emerald-500 disabled:opacity-50 transition-colors">
          {saving ? "Saving..." : message || "Save Settings"}
        </button>
      </div>
    </div>
  );
}

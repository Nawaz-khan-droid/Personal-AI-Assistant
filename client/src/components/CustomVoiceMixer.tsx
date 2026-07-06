"use client";

import React, { useState } from 'react';

interface Props {
  socket: WebSocket | null;
}

type Mode = 'preset' | 'mix';

const PRESETS = [
  { id: 'am_adam', label: 'JARVIS Core', desc: 'Authoritative Male' },
  { id: 'af_bella', label: 'VERONICA Core', desc: 'Crisp Female' },
];

const MOD_VOICES = [
  { id: 'am_michael', label: 'Tactical (Michael)' },
  { id: 'af_heart', label: 'Warm (Heart)' },
  { id: 'bm_george', label: 'British (George)' },
  { id: 'bf_emma', label: 'British (Emma)' },
];

export default function CustomVoiceMixer({ socket }: Props) {
  const [mode, setMode] = useState<Mode>('preset');
  const [presetId, setPresetId] = useState('am_adam');
  const [modVoice, setModVoice] = useState('am_michael');
  const [alpha, setAlpha] = useState(0.5);
  const [customName, setCustomName] = useState('');
  const [savedMsg, setSavedMsg] = useState('');

  const send = (payload: object) => {
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(payload));
    }
  };

  const selectPreset = (id: string) => {
    setPresetId(id);
    setMode('preset');
    send({ type: 'set_voice_profile', mode: 'preset', voice_id: id });
  };

  const handleSlider = (val: number) => {
    setAlpha(val);
    if (!presetId) return;
    setMode('mix');
    send({
      type: 'set_voice_profile',
      mode: 'mix',
      base_voice: presetId,
      mod_voice: modVoice,
      alpha: val,
    });
  };

  const saveCustom = () => {
    const name = customName.trim();
    if (!name) return;
    send({
      type: 'save_custom_mix',
      name,
      base_voice: presetId,
      mod_voice: modVoice,
      alpha,
    });
    setSavedMsg(`"${name}" compiled`);
    setTimeout(() => setSavedMsg(''), 3000);
  };

  const preview = () => {
    send({
      type: 'trigger_preview',
      text: 'System tuning complete. Matrix online.',
    });
  };

  return (
    <div className="p-5 bg-slate-900 border border-slate-800 rounded-2xl flex flex-col gap-5 text-white">
      <div>
        <h2 className="text-base font-extrabold text-blue-400">Vocal Identity Core</h2>
        <p className="text-[11px] text-slate-400">
          Select a preset or blend two voices into a custom mix.
        </p>
      </div>

      {/* Preset toggles */}
      <div className="grid grid-cols-2 gap-3">
        {PRESETS.map((v) => {
          const active = mode === 'preset' && presetId === v.id;
          const borderCls = v.id === 'am_adam'
            ? 'border-cyan-500 bg-cyan-950/30'
            : 'border-pink-500 bg-pink-950/30';
          return (
            <button
              key={v.id}
              onClick={() => selectPreset(v.id)}
              className={`p-3 rounded-xl border flex flex-col gap-0.5 transition-all text-left ${
                active ? borderCls : 'border-slate-800 bg-slate-950/40 hover:border-slate-600'
              }`}
            >
              <span className="font-bold text-sm">{v.label}</span>
              <span className="text-[11px] text-slate-400">{v.desc} ({v.id})</span>
            </button>
          );
        })}
      </div>

      {/* Mixing board */}
      <div className="p-4 bg-slate-950/50 rounded-2xl border border-slate-800/80 flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">
            Vocal Mixing Board
          </h3>
          {mode === 'mix' && (
            <span className="text-[10px] bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded-full font-mono">
              Custom Mix
            </span>
          )}
        </div>

        <div className="flex items-center gap-2 text-xs">
          <span className="text-slate-400">Base:</span>
          <select
            value={presetId}
            onChange={(e) => { setPresetId(e.target.value); handleSlider(alpha); }}
            className="flex-1 bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs"
          >
            {PRESETS.map((v) => (
              <option key={v.id} value={v.id}>{v.label}</option>
            ))}
          </select>
          <span className="text-slate-400">Mod:</span>
          <select
            value={modVoice}
            onChange={(e) => { setModVoice(e.target.value); handleSlider(alpha); }}
            className="flex-1 bg-slate-800 border border-slate-700 rounded px-2 py-1 text-xs"
          >
            {MOD_VOICES.map((v) => (
              <option key={v.id} value={v.id}>{v.label}</option>
            ))}
          </select>
        </div>

        <div className="flex justify-between text-[11px] text-slate-500 font-medium">
          <span>Pure Base</span>
          <span>Pure Mod</span>
        </div>
        <input
          type="range"
          min="0"
          max="1"
          step="0.05"
          value={alpha}
          onChange={(e) => handleSlider(parseFloat(e.target.value))}
          className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-blue-500"
        />
        <div className="text-center text-xs font-semibold text-blue-400">
          {Math.round((1 - alpha) * 100)}% Base / {Math.round(alpha * 100)}% Mod
        </div>

        {/* Save custom mix */}
        <div className="flex gap-2 mt-1">
          <input
            type="text"
            value={customName}
            onChange={(e) => setCustomName(e.target.value)}
            placeholder="Name your mix..."
            className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs outline-none focus:border-blue-500"
          />
          <button
            onClick={saveCustom}
            className="bg-blue-600 hover:bg-blue-500 text-white px-3 py-1.5 rounded-lg text-xs font-semibold transition-all"
          >
            Save
          </button>
        </div>
        {savedMsg && (
          <p className="text-[11px] text-green-400 text-center">{savedMsg}</p>
        )}
      </div>

      {/* Preview */}
      <button
        onClick={preview}
        className="w-full py-2.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-xl text-xs font-bold tracking-wide transition-all"
      >
        🔊 Test Current Voice
      </button>
    </div>
  );
}

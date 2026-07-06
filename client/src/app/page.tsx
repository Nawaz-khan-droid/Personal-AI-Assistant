"use client";

import React, { useEffect, useRef, useState } from 'react';
import VoiceInterface from '@/components/VoiceInterface';
import VoiceCaptureManager from '@/components/VoiceCaptureManager';
import VoicePlaybackManager from '@/components/VoicePlaybackManager';
import CustomVoiceMixer from '@/components/CustomVoiceMixer';

export default function JarvisDashboard() {
  const [socket, setSocket] = useState<WebSocket | null>(null);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    const ws = new WebSocket(wsUrl);
    ws.binaryType = 'arraybuffer';

    ws.onopen = () => console.log('[WS] Connected to JARVIS backend');
    ws.onclose = () => console.log('[WS] Disconnected');
    ws.onerror = (err) => console.error('[WS] Error:', err);

    socketRef.current = ws;
    setSocket(ws);

    return () => {
      ws.close();
    };
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      {/* Header */}
      <header className="px-6 py-4 border-b border-slate-800 bg-slate-900/80 backdrop-blur-md">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold tracking-tight">
              JARVIS <span className="text-cyan-400">PRO</span>
            </h1>
            <p className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">
              Moonshine STT · Groq LLM · Kokoro TTS
            </p>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-6xl mx-auto p-4 md:p-6 grid grid-cols-1 lg:grid-cols-3 gap-4 items-start">
        {/* Left Column: Chat */}
        <div className="lg:col-span-2">
          <div className="bg-slate-900/50 border border-slate-800 rounded-xl overflow-hidden">
            <VoiceInterface socket={socket} />
          </div>
        </div>

        {/* Right Column: Controls */}
        <div className="space-y-4">
          <VoiceCaptureManager socket={socket} />
          <CustomVoiceMixer socket={socket} />
          <VoicePlaybackManager socket={socket} />
        </div>
      </main>
    </div>
  );
}

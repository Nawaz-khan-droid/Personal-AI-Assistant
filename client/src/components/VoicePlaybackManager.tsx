"use client";

import React, { useEffect, useRef } from 'react';
import { useVoiceStore } from '@/store/voiceStore';

interface VoicePlaybackManagerProps {
  socket: WebSocket | null;
}

export default function VoicePlaybackManager({ socket }: VoicePlaybackManagerProps) {
  const systemState = useVoiceStore((s) => s.systemState);
  const audioContextRef = useRef<AudioContext | null>(null);
  const nextStartTimeRef = useRef(0);

  useEffect(() => {
    const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    audioContextRef.current = new AudioCtx();
    return () => { audioContextRef.current?.close(); };
  }, []);

  useEffect(() => {
    if (!socket) return;

    const handleMessage = async (event: MessageEvent) => {
      if (typeof event.data === 'string') return;
      const ctx = audioContextRef.current;
      if (!ctx) return;

      try {
        if (ctx.state === 'suspended') await ctx.resume();
        const audioBuffer = await ctx.decodeAudioData(event.data);
        const source = ctx.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(ctx.destination);

        const now = ctx.currentTime;
        if (nextStartTimeRef.current < now) nextStartTimeRef.current = now;
        source.start(nextStartTimeRef.current);
        nextStartTimeRef.current += audioBuffer.duration;
      } catch (err) {
        console.error('Audio playback error:', err);
      }
    };

    socket.addEventListener('message', handleMessage);
    return () => socket.removeEventListener('message', handleMessage);
  }, [socket]);

  const stateColor: Record<string, string> = {
    idle: 'bg-slate-500',
    listening: 'bg-green-500 animate-pulse',
    processing: 'bg-yellow-500',
    speaking: 'bg-blue-500 animate-pulse',
  };

  return (
    <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl text-center">
      <div className="flex items-center justify-center gap-2 mb-2">
        <span className={`w-2 h-2 rounded-full ${stateColor[systemState] || 'bg-slate-500'}`} />
        <span className="text-sm font-semibold text-slate-300 uppercase">
          {systemState}
        </span>
      </div>
      <p className="text-xs text-slate-500">
        {systemState === 'idle' && 'Standing by'}
        {systemState === 'listening' && 'Capturing audio — VAD active'}
        {systemState === 'processing' && 'STT → LLM → TTS pipeline'}
        {systemState === 'speaking' && 'Streaming audio to speakers'}
      </p>
    </div>
  );
}

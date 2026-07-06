"use client";

import React, { useRef, useState, useCallback, useEffect } from 'react';
import { useVoiceStore } from '@/store/voiceStore';

interface VoiceCaptureManagerProps {
  socket: WebSocket | null;
}

const CHUNK_DURATION_MS = 250;
const TARGET_SAMPLE_RATE = 16000;
const VAD_THRESHOLD = 0.008;       // RMS energy threshold for speech
const VAD_HANGOVER_FRAMES = 4;     // frames of silence before declaring speech_end
const PRE_SPEECH_BUFFER_MS = 500;  // ms of audio kept before speech start

// Inline AudioWorklet — survives Chrome tab-background throttling
const WORKLET_BLOB_URL = (() => {
  const code = `
class PCMCapture extends AudioWorkletProcessor {
  constructor(opts) {
    super(opts);
    this.buffer = [];
    this.targetSamples = (opts.processorOptions || {}).targetSamples || 4000;
  }
  process(inputs) {
    const ch = inputs[0];
    if (!ch || !ch[0]) return true;
    this.buffer.push(new Float32Array(ch[0]));
    let total = 0;
    for (const b of this.buffer) total += b.length;
    if (total >= this.targetSamples) {
      const merged = new Float32Array(total);
      let off = 0;
      for (const b of this.buffer) { merged.set(b, off); off += b.length; }
      this.buffer = [];
      const i16 = new Int16Array(merged.length);
      for (let i = 0; i < merged.length; i++) {
        const s = Math.max(-1, Math.min(1, merged[i]));
        i16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
      }
      this.port.postMessage(i16.buffer, [i16.buffer]);
    }
    return true;
  }
}
registerProcessor('pcm-capture', PCMCapture);`;
  return URL.createObjectURL(new Blob([code], { type: 'application/javascript' }));
})();

function rmsEnergy(samples: Float32Array): number {
  let sum = 0;
  for (let i = 0; i < samples.length; i++) sum += samples[i] * samples[i];
  return Math.sqrt(sum / samples.length);
}

export default function VoiceCaptureManager({ socket }: VoiceCaptureManagerProps) {
  const [isAutoMode, setIsAutoMode] = useState(false);
  const [isManuallyActive, setIsManuallyActive] = useState(false);
  const systemState = useVoiceStore((s) => s.systemState);
  const setSystemState = useVoiceStore((s) => s.setSystemState);

  // Refs (no re-renders)
  const streamRef = useRef<MediaStream | null>(null);
  const actxRef = useRef<AudioContext | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const workletRef = useRef<AudioWorkletNode | null>(null);
  const isSpeakingRef = useRef(false);
  const silenceFramesRef = useRef(0);
  const preSpeechRingRef = useRef<Float32Array[]>([]);
  const preSpeechSamples = Math.floor(TARGET_SAMPLE_RATE * PRE_SPEECH_BUFFER_MS / 1000);

  const flushToSocket = useCallback((chunks: Float32Array[], flush = true) => {
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    if (chunks.length === 0) return;
    let total = 0;
    for (const c of chunks) total += c.length;
    const merged = new Float32Array(total);
    let off = 0;
    for (const c of chunks) { merged.set(c, off); off += c.length; }
    const i16 = new Int16Array(merged.length);
    for (let i = 0; i < merged.length; i++) {
      const s = Math.max(-1, Math.min(1, merged[i]));
      i16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    socket.send(i16.buffer);
    if (flush) {
      socket.send(JSON.stringify({ type: 'speech_ended' }));
    }
  }, [socket]);

  // AudioWorklet message handler
  const onAudioData = useCallback((evt: MessageEvent<ArrayBuffer>) => {
    const ctx = actxRef.current;
    if (!ctx) return;

    // Decode Int16 → Float32 for VAD analysis
    const int16 = new Int16Array(evt.data);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) {
      float32[i] = int16[i] / (int16[i] < 0 ? 0x8000 : 0x7FFF);
    }

    const energy = rmsEnergy(float32);
    const isVoiced = energy > VAD_THRESHOLD;

    // Pre-speech ring buffer (keeps audio before speech starts)
    preSpeechRingRef.current.push(float32);
    let ringTotal = 0;
    for (const b of preSpeechRingRef.current) ringTotal += b.length;
    while (ringTotal > preSpeechSamples) {
      const head = preSpeechRingRef.current.shift();
      if (head) ringTotal -= head.length;
    }

    if (isAutoMode) {
      if (isVoiced) {
        silenceFramesRef.current = 0;
        if (!isSpeakingRef.current) {
          // Speech just started — flush pre-speech ring buffer first
          isSpeakingRef.current = true;
          setSystemState('listening');
          const ring = preSpeechRingRef.current;
          preSpeechRingRef.current = [];
          flushToSocket(ring, false);
        }
      } else {
        if (isSpeakingRef.current) {
          silenceFramesRef.current++;
          if (silenceFramesRef.current >= VAD_HANGOVER_FRAMES) {
            // Speech ended
            isSpeakingRef.current = false;
            preSpeechRingRef.current = [];
            socket?.send(JSON.stringify({ type: 'speech_ended' }));
            setSystemState('processing');
          }
        }
      }

      // Keep sending audio while speaking
      if (isSpeakingRef.current) {
        flushToSocket([float32], false);
      }
    }
  }, [isAutoMode, flushToSocket, socket, setSystemState]);

  // Initialize AudioWorklet
  const initAudioPipeline = useCallback(async (stream: MediaStream) => {
    const actx = new AudioContext({ sampleRate: TARGET_SAMPLE_RATE });
    actxRef.current = actx;

    await actx.audioWorklet.addModule(WORKLET_BLOB_URL);

    const node = new AudioWorkletNode(actx, 'pcm-capture', {
      processorOptions: {
        targetSamples: Math.floor(TARGET_SAMPLE_RATE * CHUNK_DURATION_MS / 1000),
      },
    });
    workletRef.current = node;
    node.port.onmessage = onAudioData;

    const source = actx.createMediaStreamSource(stream);
    sourceRef.current = source;
    source.connect(node);
  }, [onAudioData]);

  const startMic = useCallback(async () => {
    if (!socket || socket.readyState !== WebSocket.OPEN) return null;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: TARGET_SAMPLE_RATE,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      streamRef.current = stream;
      await initAudioPipeline(stream);
      return stream;
    } catch (err) {
      console.error('Mic access denied:', err);
      setSystemState('idle');
      return null;
    }
  }, [socket, initAudioPipeline, setSystemState]);

  const stopMic = useCallback(() => {
    if (workletRef.current) { workletRef.current.disconnect(); workletRef.current = null; }
    if (sourceRef.current) { sourceRef.current.disconnect(); sourceRef.current = null; }
    if (actxRef.current) { actxRef.current.close(); actxRef.current = null; }
    if (streamRef.current) { streamRef.current.getTracks().forEach(t => t.stop()); streamRef.current = null; }
    isSpeakingRef.current = false;
    silenceFramesRef.current = 0;
    preSpeechRingRef.current = [];
  }, []);

  // --- MANUAL MODE ---
  const handleManualStart = async () => {
    const stream = await startMic();
    if (!stream) return;
    isSpeakingRef.current = true;
    setIsManuallyActive(true);
    setSystemState('listening');
  };

  const handleManualStop = () => {
    isSpeakingRef.current = false;
    setIsManuallyActive(false);
    socket?.send(JSON.stringify({ type: 'speech_ended' }));
    stopMic();
    setSystemState('processing');
  };

  // --- AUTO MODE ---
  useEffect(() => {
    if (!isAutoMode) {
      if (isManuallyActive) return; // don't stop if manual is active
      stopMic();
      setSystemState('idle');
      return;
    }

    // Start mic + VAD
    (async () => {
      const stream = await startMic();
      if (stream) setSystemState('idle');
    })();

    return () => {
      // Only cleanup if still in auto mode (prevent race with manual)
      if (isAutoMode) {
        stopMic();
        setSystemState('idle');
      }
    };
  }, [isAutoMode]);

  // Cleanup on unmount
  useEffect(() => {
    return () => { stopMic(); };
  }, [stopMic]);

  // Listen for backend state changes from WebSocket
  useEffect(() => {
    if (!socket) return;
    const handler = (evt: MessageEvent) => {
      if (typeof evt.data !== 'string') return;
      try {
        const msg = JSON.parse(evt.data);
        if (msg.type === 'thinking' || msg.type === 'processing') {
          setSystemState('processing');
        } else if (msg.type === 'bot_response_text') {
          setSystemState('speaking');
        } else if (msg.type === 'stt_text') {
          // Still listening — STT is happening, then LLM is coming
        }
      } catch { /* ignore parse errors */ }
    };
    socket.addEventListener('message', handler);
    return () => socket.removeEventListener('message', handler);
  }, [socket, setSystemState]);

  const canSend = socket?.readyState === WebSocket.OPEN;
  const showManual = !isAutoMode;

  return (
    <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
      {/* Header + Auto toggle */}
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-sm font-bold text-blue-400">Vocal Telemetry</h3>
          <p className="text-[10px] text-slate-400 font-mono uppercase">
            Status: <span className="text-cyan-400">{systemState}</span>
          </p>
        </div>
        <label className="flex items-center gap-1.5 text-[11px] text-slate-400 cursor-pointer select-none">
          Auto
          <input
            type="checkbox"
            checked={isAutoMode}
            onChange={(e) => setIsAutoMode(e.target.checked)}
            className="w-7 h-4 bg-slate-700 checked:bg-blue-600 rounded-full appearance-none relative cursor-pointer
                       before:content-[''] before:absolute before:h-3 before:w-3 before:bg-white before:rounded-full
                       before:top-0.5 before:left-0.5 checked:before:translate-x-3 before:transition-all"
          />
        </label>
      </div>

      {/* Manual controls */}
      {showManual && (
        <button
          onClick={isManuallyActive ? handleManualStop : handleManualStart}
          disabled={!canSend}
          className={`w-full py-3 rounded-xl font-bold text-xs tracking-wider transition-all ${
            isManuallyActive
              ? 'bg-red-600 hover:bg-red-500 animate-pulse'
              : 'bg-blue-600 hover:bg-blue-500'
          } disabled:opacity-40`}
        >
          {isManuallyActive ? 'STOP' : 'START'}
        </button>
      )}

      {/* Auto mode status */}
      {isAutoMode && (
        <div className="p-3 bg-slate-950/50 border border-slate-800 rounded-lg text-center text-xs text-slate-400">
          {systemState === 'idle' && <span>Listening for speech...</span>}
          {systemState === 'listening' && <span className="text-green-400 font-semibold animate-pulse">Recording...</span>}
          {systemState === 'processing' && <span className="text-yellow-400">Processing...</span>}
          {systemState === 'speaking' && <span className="text-blue-400">JARVIS speaking...</span>}
        </div>
      )}
    </div>
  );
}

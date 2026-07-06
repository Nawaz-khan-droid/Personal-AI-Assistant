import { create } from 'zustand';

export type SystemState = 'idle' | 'listening' | 'processing' | 'speaking';

interface VoiceState {
  systemState: SystemState;
  setSystemState: (s: SystemState) => void;
  lastTranscript: string;
  setLastTranscript: (t: string) => void;
  lastResponse: string;
  setLastResponse: (r: string) => void;
}

export const useVoiceStore = create<VoiceState>((set) => ({
  systemState: 'idle',
  setSystemState: (s) => set({ systemState: s }),
  lastTranscript: '',
  setLastTranscript: (t) => set({ lastTranscript: t }),
  lastResponse: '',
  setLastResponse: (r) => set({ lastResponse: r }),
}));

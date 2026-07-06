
import { create } from 'zustand';

export interface Message {
    id: string;
    role: 'user' | 'assistant' | 'system';
    content: string;
    timestamp: number;
}

interface ChatState {
    messages: Message[];
    status: 'disconnected' | 'connecting' | 'connected' | 'error';
    isRecording: boolean;
    latency: number | null;
    debugInfo: {
        lastError: string | null;
        connectionAttempts: number;
        wsState: string;
    };

    addMessage: (msg: Message) => void;
    updateLastAssistantMessage: (chunk: string) => void;
    setStatus: (status: ChatState['status']) => void;
    setLatency: (ms: number) => void;
    setDebugInfo: (info: Partial<ChatState['debugInfo']>) => void;
    setRecording: (isRecording: boolean) => void;
    clearMessages: () => void;
}

export const useChatStore = create<ChatState>((set) => ({
    messages: [],
    status: 'disconnected',
    isRecording: false,

    latency: null,
    debugInfo: {
        lastError: null,
        connectionAttempts: 0,
        wsState: 'CLOSED'
    },

    addMessage: (msg) => set((state) => {
        const MAX = 100;
        const next = [...state.messages, msg];
        if (next.length > MAX) next.splice(0, next.length - MAX);
        return { messages: next };
    }),

    updateLastAssistantMessage: (chunk: string) => set((state) => {
        const lastMsg = state.messages[state.messages.length - 1];
        if (lastMsg && lastMsg.role === 'assistant') {
            const updatedMessages = [...state.messages];
            updatedMessages[state.messages.length - 1] = {
                ...lastMsg,
                content: lastMsg.content + chunk
            };
            return { messages: updatedMessages };
        }
        return state;
    }),

    setStatus: (status) => set({ status }),

    setLatency: (latency) => set({ latency }),

    setDebugInfo: (info) => set((state) => ({
        debugInfo: { ...state.debugInfo, ...info }
    })),

    setRecording: (isRecording) => set({ isRecording }),

    clearMessages: () => set({ messages: [] })
}));

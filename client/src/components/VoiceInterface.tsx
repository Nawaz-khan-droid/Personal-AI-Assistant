"use client";

import React, { useEffect, useRef, useState } from 'react';
import { useChatStore } from '../store/chatStore';
import {
    Mic, MicOff, Send, Activity, Terminal,
    Clock
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import clsx from 'clsx';

interface VoiceInterfaceProps {
  socket: WebSocket | null;
}

export default function VoiceInterface({ socket }: VoiceInterfaceProps) {
    const { messages, status, isRecording, setRecording, latency, debugInfo } = useChatStore();
    const [inputText, setInputText] = useState('');
    const [showDebug, setShowDebug] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    // Listen for WS messages for chat
    useEffect(() => {
        if (!socket) return;
        const handler = (evt: MessageEvent) => {
            if (typeof evt.data !== 'string') return;
            try {
                const msg = JSON.parse(evt.data);
                if (msg.type === 'bot_response_text') {
                    useChatStore.getState().addMessage({
                        id: Date.now().toString(),
                        role: 'assistant',
                        content: msg.text,
                        timestamp: Date.now()
                    });
                }
            } catch { /* ignore parse errors */ }
        };
        socket.addEventListener('message', handler);
        return () => socket.removeEventListener('message', handler);
    }, [socket]);

    const sendTextMessage = (text: string) => {
        if (!socket || socket.readyState !== WebSocket.OPEN) return;
        socket.send(JSON.stringify({ type: 'text_message', content: text }));
        useChatStore.getState().addMessage({
            id: Date.now().toString(),
            role: 'user',
            content: text,
            timestamp: Date.now()
        });
    };

    const handleSend = () => {
        if (!inputText.trim()) return;
        sendTextMessage(inputText);
        setInputText('');
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const toggleRecording = () => {
        const newState = !isRecording;
        setRecording(newState);
    };

    const getStatusColor = () => {
        switch (status) {
            case 'connected': return 'bg-emerald-500';
            case 'connecting': return 'bg-amber-500';
            case 'disconnected':
            case 'error': return 'bg-rose-500';
            default: return 'bg-gray-500';
        }
    };

    return (
        <div className="flex flex-col h-screen bg-gray-950 text-gray-100 font-sans overflow-hidden selection:bg-cyan-500/30">
            <div className="fixed inset-0 bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] from-indigo-900/10 via-gray-950 to-gray-950 pointer-events-none" />

            <header className="px-6 py-4 border-b border-gray-800/60 bg-gray-900/80 backdrop-blur-md flex justify-between items-center z-20 shadow-sm">
                <div className="flex items-center gap-4">
                    <div className="relative group">
                        <div className={clsx(
                            "w-3 h-3 rounded-full shadow-[0_0_12px_rgba(0,0,0,0.5)] transition-all duration-500",
                            getStatusColor(),
                            status === 'connected' && "shadow-[0_0_15px_rgba(16,185,129,0.4)] animate-pulse"
                        )} />
                        <div className="absolute top-6 left-0 px-2 py-1 bg-gray-800 text-[10px] rounded border border-gray-700 opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none z-50">
                            WS: {debugInfo?.wsState || 'UNKNOWN'}
                        </div>
                    </div>

                    <div>
                        <h1 className="text-lg font-bold tracking-tight text-gray-100">
                            JARVIS <span className="text-cyan-500">PRO</span>
                        </h1>
                        <div className="flex items-center gap-3 text-[10px] font-mono text-gray-500 uppercase tracking-wider">
                            <span>System v2.0</span>
                            {latency !== null && (
                                <span className={clsx("flex items-center gap-1", latency < 100 ? "text-emerald-500" : "text-amber-500")}>
                                    <Clock className="w-3 h-3" /> {latency}ms
                                </span>
                            )}
                        </div>
                    </div>
                </div>

                <div className="flex items-center gap-4">
                    <button
                        onClick={() => setShowDebug(!showDebug)}
                        className={clsx(
                            "p-2 rounded-lg transition-colors text-xs font-mono flex items-center gap-2",
                            showDebug ? "bg-gray-800 text-cyan-400" : "hover:bg-gray-800/50 text-gray-500"
                        )}
                    >
                        <Terminal className="w-4 h-4" />
                        DEBUG
                    </button>
                </div>
            </header>

            <div className="flex-1 flex overflow-hidden relative">
                <main className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6 scrollbar-thin scrollbar-thumb-gray-800 scrollbar-track-transparent">
                    <AnimatePresence mode="popLayout">
                        {messages.length === 0 && (
                            <motion.div
                                initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                                className="h-full flex flex-col items-center justify-center text-gray-500 space-y-8"
                            >
                                <div className="relative">
                                    <div className="absolute inset-0 bg-cyan-500/20 blur-3xl rounded-full" />
                                    <Activity className="w-24 h-24 text-gray-800 relative z-10 opacity-50" />
                                </div>
                                <p className="font-mono text-sm tracking-widest text-gray-600">AWAITING INPUT_</p>
                            </motion.div>
                        )}

                        {messages.map((msg) => (
                            <motion.div
                                key={msg.id}
                                initial={{ opacity: 0, y: 20, scale: 0.98 }}
                                animate={{ opacity: 1, y: 0, scale: 1 }}
                                className={clsx(
                                    "flex w-full max-w-4xl mx-auto gap-4 group",
                                    msg.role === 'user' ? "justify-end" : "justify-start"
                                )}
                            >
                                {msg.role === 'assistant' && (
                                    <div className="w-8 h-8 rounded-lg bg-cyan-950 border border-cyan-900/50 flex items-center justify-center mt-1 text-cyan-500 shadow-[0_0_15px_rgba(6,182,212,0.1)]">
                                        <Activity className="w-4 h-4" />
                                    </div>
                                )}

                                <div className={clsx(
                                    "px-5 py-3.5 rounded-2xl max-w-[85%] md:max-w-[75%] text-[15px] leading-relaxed shadow-sm backdrop-blur-sm",
                                    msg.role === 'user'
                                        ? "bg-blue-600 text-gray-50 rounded-br-sm shadow-blue-500/5"
                                        : "bg-gray-800/40 border border-gray-700/50 text-gray-200 rounded-bl-sm"
                                )}>
                                    {msg.content}
                                    <div className="flex justify-end mt-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                        <span className="text-[10px] text-gray-500 font-mono">
                                            {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                                        </span>
                                    </div>
                                </div>
                            </motion.div>
                        ))}
                    </AnimatePresence>
                    <div ref={messagesEndRef} className="h-4" />
                </main>

                <AnimatePresence>
                    {showDebug && debugInfo && (
                        <motion.div
                            initial={{ x: 300, opacity: 0 }}
                            animate={{ x: 0, opacity: 1 }}
                            exit={{ x: 300, opacity: 0 }}
                            className="absolute right-0 top-0 bottom-0 w-80 bg-gray-900/95 backdrop-blur-xl border-l border-gray-800 p-4 shadow-2xl z-30 font-mono text-xs overflow-y-auto"
                        >
                            <div className="space-y-6">
                                <div>
                                    <h3 className="text-gray-500 font-bold mb-2 uppercase tracking-wider">Connection Stats</h3>
                                    <div className="space-y-2 bg-gray-950/50 p-3 rounded border border-gray-800">
                                        <div className="flex justify-between">
                                            <span className="text-gray-400">Status:</span>
                                            <span className={clsx("font-bold",
                                                status === 'connected' ? 'text-green-400' :
                                                    status === 'error' ? 'text-red-400' : 'text-yellow-400'
                                            )}>{status.toUpperCase()}</span>
                                        </div>
                                        <div className="flex justify-between">
                                            <span className="text-gray-400">Latency:</span>
                                            <span className="text-cyan-400">{latency ?? 'N/A'} ms</span>
                                        </div>
                                        <div className="flex justify-between">
                                            <span className="text-gray-400">Attempts:</span>
                                            <span className="text-gray-200">{debugInfo.connectionAttempts}</span>
                                        </div>
                                        <div className="flex justify-between">
                                            <span className="text-gray-400">WS State:</span>
                                            <span className="text-gray-200">{debugInfo.wsState}</span>
                                        </div>
                                    </div>
                                </div>

                                {debugInfo.lastError && (
                                    <div>
                                        <h3 className="text-red-500 font-bold mb-2 uppercase tracking-wider">Error Log</h3>
                                        <div className="bg-red-950/20 border border-red-900/50 p-3 rounded text-red-400 break-words">
                                            {debugInfo.lastError}
                                        </div>
                                    </div>
                                )}

                                <div>
                                    <h3 className="text-gray-500 font-bold mb-2 uppercase tracking-wider">System Specs</h3>
                                    <div className="space-y-1 text-gray-400">
                                        <p>Frontend: React 19 / Next.js 15</p>
                                        <p>Backend: FastAPI / Python 3.12</p>
                                        <p>Protocol: WebSocket (Secure)</p>
                                        <p>Pipeline: STT - LLM - TTS</p>
                                    </div>
                                </div>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>

            <div className="p-6 bg-gray-900/90 border-t border-gray-800 backdrop-blur-xl z-20">
                <div className="max-w-3xl mx-auto flex items-end gap-4">
                    <div className="relative group">
                        {isRecording && (
                            <div className="absolute inset-0 bg-red-500 rounded-full animate-ping opacity-20 pointer-events-none" />
                        )}
                        <button
                            onClick={toggleRecording}
                            className={clsx(
                                "w-14 h-14 rounded-full flex items-center justify-center transition-all duration-300 shadow-xl border-2",
                                isRecording
                                    ? "bg-gray-100 text-red-600 border-red-500 scale-105"
                                    : "bg-gray-800 text-gray-400 border-gray-700 hover:border-gray-500 hover:text-gray-200"
                            )}
                        >
                            {isRecording ? <MicOff className="w-6 h-6" /> : <Mic className="w-6 h-6" />}
                        </button>
                    </div>

                    <div className="flex-1 relative">
                        <textarea
                            value={inputText}
                            onChange={(e) => setInputText(e.target.value)}
                            onKeyDown={handleKeyDown}
                            placeholder="Type a command to JARVIS..."
                            className="w-full bg-gray-950 text-gray-100 pl-5 pr-14 py-4 rounded-xl border border-gray-800 focus:border-cyan-500/50 focus:ring-1 focus:ring-cyan-500/50 transition-all resize-none shadow-inner min-h-[60px] max-h-[120px]"
                            rows={1}
                        />
                        <button
                            onClick={handleSend}
                            disabled={!inputText.trim()}
                            className="absolute right-3 bottom-3 p-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg disabled:opacity-0 disabled:scale-90 transition-all shadow-lg"
                        >
                            <Send className="w-4 h-4" />
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
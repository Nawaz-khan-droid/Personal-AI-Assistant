'use client';

import { useConnectionState, useVoiceAssistant, BarVisualizer, VoiceAssistantControlBar } from '@livekit/components-react';
import { ConnectionState, Track } from 'livekit-client';

export function AgentSessionView_01() {
  const state = useConnectionState();
  const { state: agentState, audioTrack } = useVoiceAssistant();

  // For visualizer
  const trackRef = audioTrack?.publication?.track ? { 
      publication: audioTrack.publication,
      source: Track.Source.Microphone,
      participant: audioTrack.participant
  } : undefined;

  return (
    <div className="flex flex-col items-center justify-center w-full max-w-2xl bg-zinc-900 border border-zinc-800 rounded-2xl overflow-hidden shadow-2xl relative">
      <div className="flex items-center justify-between w-full px-6 py-4 border-b border-zinc-800/50 bg-zinc-950/50">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-cyan-600 rounded-full flex items-center justify-center shadow-lg shadow-cyan-900/50">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-white">
              <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"></path>
              <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
              <line x1="12" x2="12" y1="19" y2="22"></line>
            </svg>
          </div>
          <div>
            <h2 className="text-lg font-semibold text-white">JARVIS Neural Interface</h2>
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${
                state === ConnectionState.Connected ? 'bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]' :
                state === ConnectionState.Connecting ? 'bg-yellow-500 animate-pulse' :
                'bg-red-500'
              }`} />
              <span className="text-xs text-zinc-400 capitalize">
                {state === ConnectionState.Connected ? agentState : state}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="flex flex-col items-center justify-center w-full min-h-[300px] p-8 relative overflow-hidden">
        {state === ConnectionState.Connecting && (
          <div className="text-cyan-500 flex flex-col items-center gap-4 animate-pulse">
            <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <p className="tracking-widest uppercase text-sm font-medium">Connecting to JARVIS...</p>
          </div>
        )}

        {state === ConnectionState.Connected && (
          <div className="w-full flex justify-center items-center h-40">
            {trackRef ? (
               <BarVisualizer
                  state={agentState}
                  barCount={7}
                  trackRef={trackRef}
                  className="w-full h-full max-w-xs text-cyan-500 drop-shadow-[0_0_15px_rgba(6,182,212,0.5)]"
                />
            ) : (
                <div className="text-zinc-600 text-sm">Waiting for audio track...</div>
            )}
          </div>
        )}
        
        {state === ConnectionState.Disconnected && (
          <div className="text-red-400 text-sm">Session Disconnected</div>
        )}
      </div>

      <div className="w-full p-4 border-t border-zinc-800 bg-zinc-950/80 flex justify-center">
         <VoiceAssistantControlBar controls={{ leave: true, microphone: true }} />
      </div>
    </div>
  );
}

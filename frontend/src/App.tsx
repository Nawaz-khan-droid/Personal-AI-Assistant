import { useState, useRef, useEffect } from 'react';
import { 
  LiveKitRoom, 
  useVoiceAssistant, 
  VoiceAssistantControlBar, 
  RoomAudioRenderer,
  useTranscriptions,
  useLocalParticipant 
} from '@livekit/components-react';
import { AgentAudioVisualizerAura } from './components/agents-ui/agent-audio-visualizer-aura';

const API_URL = "http://localhost:8000/api/token";

function CustomTranscript({ persona }: { persona: string }) {
  const transcript = useTranscriptions();
  const { localParticipant } = useLocalParticipant();
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [transcript]);

  // Determine accent colors dynamically based on the selected persona
  const isJarvis = persona.toLowerCase() === 'jarvis';
  const agentBg = isJarvis ? 'bg-zinc-800 text-cyan-100' : 'bg-zinc-800 text-pink-100';
  const agentLabelColor = isJarvis ? 'text-cyan-400' : 'text-pink-400';
  const userBg = isJarvis ? 'bg-cyan-700 text-white' : 'bg-pink-700 text-white';
  const userLabelColor = isJarvis ? 'text-cyan-200' : 'text-pink-200';

  return (
    <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3 scrollbar-thin">
      {(!transcript || transcript.length === 0) && (
        <p className="text-zinc-600 text-center text-sm mt-10">No messages yet.</p>
      )}

      {transcript?.map((msg: any, i: number) => {
        // LiveKit Components v2.9+ exposes identity on `participantInfo` directly within TextStreamData.
        // We match it against our own local identity to guarantee 100% accuracy, bypassing odd/even tracker hacks.
        const isUser = msg.participantInfo?.identity === localParticipant?.identity;
        const speakerLabel = isUser ? 'YOU' : persona.toUpperCase();

        const rawText = msg.message || msg.text || "";
        
        // CORRECT STRING CLEANUP: Strip the tool syntax but KEEP the clean text stream around it
        const cleanedText = rawText.replace(/<function[\s\S]*?<\/function>/gi, "").trim();

        // ONLY skip rendering if the message text is entirely empty after stripping space
        if (!cleanedText && !isUser) {
          return null;
        }

        return (
          <div key={i} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] p-3 rounded-2xl text-sm ${
              isUser ? `${userBg} rounded-br-md` : `${agentBg} rounded-bl-md`
            }`}>
              <p className={`text-xs mb-1 font-mono font-bold tracking-wider ${
                isUser ? userLabelColor : agentLabelColor
              }`}>
                {speakerLabel}
              </p>
              {/* Render the clean human language contents safely */}
              <p className="leading-relaxed">{cleanedText}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function JarvisSessionUI({ persona }: { persona: string }) {
  const { state, audioTrack } = useVoiceAssistant();
  return (
    <div className="h-screen w-screen bg-black text-white flex flex-col overflow-hidden relative">
      <CustomTranscript persona={persona} />
      <div className="flex-shrink-0 flex flex-col items-center justify-center py-4 bg-zinc-950/80 backdrop-blur-sm border-t border-b border-zinc-800">
        <AgentAudioVisualizerAura 
          size="lg" 
          color={persona === 'veronica' ? '#D946EF' : '#1FD5F9'} 
          colorShift={0.1} 
          state={state as any} 
          audioTrack={audioTrack as any} 
        />
        <p className="mt-2 text-xs text-zinc-500 uppercase tracking-widest">{state}</p>
      </div>
      <div className="flex-shrink-0 p-4 flex justify-center bg-black">
        <VoiceAssistantControlBar controls={{ leave: true, microphone: true }} />
      </div>
      <RoomAudioRenderer />
    </div>
  );
}

export default function App() {
  const [token, setToken] = useState('');
  const [url, setUrl] = useState('');
  const [password, setPassword] = useState('');
  const [persona, setPersona] = useState('jarvis');
  const [error, setError] = useState('');

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    try {
      const res = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password, persona })
      });
      if (!res.ok) throw new Error('Unauthorized');
      const data = await res.json();
      setToken(data.token);
      setUrl(data.url);
    } catch (err) {
      setError('Access Denied');
    }
  };

  const onDisconnected = () => {
    setToken('');
    setUrl('');
  };

  if (token && url) {
    return (
      <LiveKitRoom
        serverUrl={url}
        token={token}
        connect={true}
        audio={true}
        video={false}
        onDisconnected={onDisconnected}
      >
        <JarvisSessionUI persona={persona} />
      </LiveKitRoom>
    );
  }

  return (
    <div className="h-screen w-screen bg-black flex items-center justify-center p-4">
      <form onSubmit={handleLogin} className="w-full max-w-sm flex flex-col gap-4 p-8 border border-zinc-800 rounded-2xl bg-zinc-900 shadow-2xl">
        <h2 className="text-white text-center text-2xl font-light tracking-wider mb-2">{persona.toUpperCase()}</h2>
        <p className="text-zinc-500 text-center text-xs mb-4">NEURAL INTERFACE</p>
        <input 
          type="password" 
          placeholder="Access Code" 
          value={password} 
          onChange={(e) => setPassword(e.target.value)} 
          className="p-3 bg-white text-black border border-zinc-300 rounded-lg text-center tracking-widest focus:outline-none focus:ring-2 focus:ring-cyan-500" 
        />
        <div className="flex justify-center gap-4 mb-2 mt-2">
          <button 
            type="button" 
            onClick={() => setPersona('jarvis')} 
            className={`px-4 py-2 text-xs font-bold tracking-widest rounded-lg transition-colors ${
              persona === 'jarvis' ? 'bg-cyan-600 text-white' : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700'
            }`}
          >
            JARVIS
          </button>
          <button 
            type="button" 
            onClick={() => setPersona('veronica')} 
            className={`px-4 py-2 text-xs font-bold tracking-widest rounded-lg transition-colors ${
              persona === 'veronica' ? 'bg-pink-600 text-white' : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700'
            }`}
          >
            VERONICA
          </button>
        </div>
        <button 
          type="submit" 
          className={`p-3 text-white rounded-lg transition-colors font-medium ${
            persona === 'jarvis' ? 'bg-cyan-800 hover:bg-cyan-700' : 'bg-pink-800 hover:bg-pink-700'
          }`}
        >
          Connect
        </button>
        {error && <p className="text-red-500 text-sm text-center">{error}</p>}
      </form>
    </div>
  );
}

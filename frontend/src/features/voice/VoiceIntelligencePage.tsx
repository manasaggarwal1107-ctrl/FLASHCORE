import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, Mic, MicOff, Send, Square, Volume2, VolumeX, XCircle } from 'lucide-react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Input, Select } from '@/components/ui/Field';
import { PageHeader } from '@/components/ui/PageHeader';
import { Panel, PanelBody, PanelHeader } from '@/components/ui/Panel';
import { expansionApi } from '@/services/api/expansionApi';
import type { VoiceProposal } from '@/services/api/expansionApi';

type VoiceState = 'idle' | 'listening' | 'processing' | 'speaking';

interface BrowserSpeechRecognition {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((ev: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
}

export function VoiceIntelligencePage() {
  const qc = useQueryClient();
  const [language, setLanguage] = useState<'en' | 'hi' | 'hinglish' | 'auto'>('hinglish');
  const [voiceState, setVoiceState] = useState<VoiceState>('idle');
  const [inputText, setInputText] = useState('');
  const [activeSessionId, setActiveSessionId] = useState<number | undefined>();
  const [lastReply, setLastReply] = useState<{ reply: string; tools: Array<Record<string, unknown>>; pendingProposal?: VoiceProposal | null } | null>(null);
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const [ttsEnabled, setTtsEnabled] = useState(true);
  const recognitionRef = useRef<BrowserSpeechRecognition | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const sessionsQ = useQuery({ queryKey: ['voice.sessions'], queryFn: expansionApi.listVoiceSessions });

  const stopRecording = () => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // Ignore already stopped recognition
      }
      recognitionRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    if (streamRef.current) {
      for (const track of streamRef.current.getTracks()) track.stop();
      streamRef.current = null;
    }
    setVoiceState((prev) => (prev === 'listening' ? 'idle' : prev));
  };

  const stopSpeaking = () => {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    setVoiceState((prev) => (prev === 'speaking' ? 'idle' : prev));
  };

  useEffect(() => {
    return () => {
      stopRecording();
      stopSpeaking();
    };
  }, []);

  const speakReply = (text: string, langHint: string) => {
    if (!ttsEnabled || typeof window === 'undefined' || !('speechSynthesis' in window)) return;
    try {
      window.speechSynthesis.cancel();
      const utter = new SpeechSynthesisUtterance(text);
      utter.lang = langHint;
      utter.onstart = () => setVoiceState('speaking');
      utter.onend = () => setVoiceState('idle');
      utter.onerror = () => setVoiceState('idle');
      window.speechSynthesis.speak(utter);
    } catch {
      setVoiceState('idle');
    }
  };

  const queryMut = useMutation({
    mutationFn: ({ transcript, mode }: { transcript: string; mode: 'voice' | 'text' }) => {
      setVoiceState('processing');
      return expansionApi.queryVoice({
        session_id: activeSessionId,
        transcript,
        language,
        input_mode: mode,
      });
    },
    onSuccess: (res) => {
      setVoiceError(null);
      setActiveSessionId(Number(res.sessionId));
      setLastReply({
        reply: String(res.reply ?? ''),
        tools: (res.toolExecutions as Array<Record<string, unknown>>) ?? [],
        pendingProposal: (res.pendingProposal as VoiceProposal | null) ?? null,
      });
      setInputText('');
      setVoiceState('idle');
      void qc.invalidateQueries({ queryKey: ['voice.sessions'] });
      const hint = res.ttsHint as { voiceLang?: string } | undefined;
      speakReply(String(res.reply ?? ''), hint?.voiceLang ?? (language === 'en' ? 'en-IN' : 'hi-IN'));
    },
    onError: (e: Error) => {
      setVoiceState('idle');
      setVoiceError(e.message);
    },
  });

  const decideMut = useMutation({
    mutationFn: ({ id, approve }: { id: string; approve: boolean }) => expansionApi.decideVoiceAction(id, approve),
    onSuccess: (prop) => {
      setLastReply((prev) => (prev ? { ...prev, pendingProposal: prop } : prev));
      void qc.invalidateQueries({ queryKey: ['voice.sessions'] });
    },
    onError: (e: Error) => setVoiceError(e.message),
  });

  const startPushToTalk = async () => {
    setVoiceError(null);
    stopSpeaking();
    const speechWindow = window as unknown as {
      SpeechRecognition?: new () => BrowserSpeechRecognition;
      webkitSpeechRecognition?: new () => BrowserSpeechRecognition;
    };
    const SpeechRec = speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition;

    if (SpeechRec) {
      const rec = new SpeechRec();
      rec.lang = language === 'en' ? 'en-IN' : 'hi-IN';
      rec.interimResults = true;
      rec.continuous = false;
      let latestText = '';
      rec.onresult = (ev) => {
        const last = ev.results[ev.results.length - 1];
        if (last && last[0]) {
          latestText = last[0].transcript;
          setInputText(latestText);
        }
      };
      rec.onerror = () => {
        setVoiceError('Microphone or browser speech capture unavailable. Use text fallback below.');
        stopRecording();
      };
      rec.onend = () => {
        setVoiceState('idle');
        if (latestText.trim()) {
          queryMut.mutate({ transcript: latestText.trim(), mode: 'voice' });
        }
      };
      recognitionRef.current = rec;
      setVoiceState('listening');
      rec.start();
      return;
    }

    if (navigator.mediaDevices?.getUserMedia) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        streamRef.current = stream;
        const recorder = new MediaRecorder(stream);
        const chunks: BlobPart[] = [];
        recorder.ondataavailable = (e) => chunks.push(e.data);
        recorder.onstop = () => {
          const blob = new Blob(chunks, { type: 'audio/webm' });
          const reader = new FileReader();
          reader.onloadend = () => {
            const b64 = String(reader.result ?? '');
            void expansionApi.transcribeAudio({ audio_base64: b64, filename: 'speech.webm', language })
              .then((t) => queryMut.mutate({ transcript: t.text, mode: 'voice' }))
              .catch((err: Error) => setVoiceError(err.message));
          };
          reader.readAsDataURL(blob);
          for (const tr of stream.getTracks()) tr.stop();
        };
        mediaRecorderRef.current = recorder;
        setVoiceState('listening');
        recorder.start();
      } catch {
        setVoiceError('Microphone permission denied or unavailable. Text input works identically.');
      }
    } else {
      setVoiceError('Browser speech capture not supported on this device; use text input below.');
    }
  };

  const activeSession = sessionsQ.data?.find((s) => Number(s.id) === activeSessionId) ?? sessionsQ.data?.[0];

  return (
    <div className="space-y-4">
      <PageHeader
        title="FLASHCORE Voice Intelligence"
        description="Talk to your business. Understand it. Control it. Powered by Groq server-side tool orchestration with explicit approval."
        meta={<Badge tone="accent">State: {voiceState}</Badge>}
        actions={
          <div className="flex items-center gap-2">
            <Select aria-label="Assistant language" value={language} onChange={(e) => setLanguage(e.target.value as typeof language)}>
              <option value="en">English (en-IN)</option>
              <option value="hi">Hindi (hi-IN)</option>
              <option value="hinglish">Hinglish</option>
              <option value="auto">Auto</option>
            </Select>
            <Button size="sm" icon={ttsEnabled ? <Volume2 className="h-3.5 w-3.5" /> : <VolumeX className="h-3.5 w-3.5" />} onClick={() => { if (ttsEnabled) stopSpeaking(); setTtsEnabled((v) => !v); }}>
              {ttsEnabled ? 'TTS On' : 'TTS Muted'}
            </Button>
          </div>
        }
      />

      {voiceError && <div role="alert" className="rounded border border-warning/40 bg-warning/10 px-3 py-2 text-xs text-warning">{voiceError}</div>}

      <div className="grid gap-4 lg:grid-cols-12">
        <div className="space-y-4 lg:col-span-8">
          <Panel>
            <PanelHeader title="Assistant Console" description="Ask about today's sales, low stock, refunds, campaigns, or propose operational updates." />
            <PanelBody className="space-y-3">
              {/* Push-to-Talk & Text Fallback */}
              <div className="flex flex-wrap items-center gap-2">
                {voiceState === 'listening' ? (
                  <Button variant="danger" icon={<MicOff className="h-4 w-4" />} onClick={stopRecording}>Stop Mic</Button>
                ) : (
                  <Button variant="primary" icon={<Mic className="h-4 w-4" />} onClick={() => void startPushToTalk()}>Push to Talk</Button>
                )}
                {voiceState === 'speaking' && (
                  <Button size="sm" icon={<Square className="h-3.5 w-3.5" />} onClick={stopSpeaking}>Stop Speech</Button>
                )}
                <Input
                  aria-label="Ask FLASHCORE assistant"
                  placeholder="Type or dictate: e.g. 'What were today's sales?' or 'Aaj ka low stock dikhao'..."
                  className="flex-1"
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter' && inputText.trim()) queryMut.mutate({ transcript: inputText.trim(), mode: 'text' }); }}
                />
                <Button icon={<Send className="h-3.5 w-3.5" />} loading={queryMut.isPending} disabled={!inputText.trim()} onClick={() => queryMut.mutate({ transcript: inputText.trim(), mode: 'text' })}>
                  Send
                </Button>
              </div>

              <div className="flex flex-wrap gap-1.5">
                {['What were today’s sales?', 'Which products are running low?', 'What is the refund status?', 'Aaj ki sales aur top product batao'].map((prompt) => (
                  <Button key={prompt} size="sm" variant="ghost" onClick={() => queryMut.mutate({ transcript: prompt, mode: 'text' })}>
                    {prompt}
                  </Button>
                ))}
              </div>

              {lastReply?.pendingProposal && (
                <div className="rounded-md border border-warning/50 bg-warning/10 p-3 text-xs">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold text-ink">Approval Required: {lastReply.pendingProposal.toolName}</span>
                    <Badge tone="warning">{lastReply.pendingProposal.status}</Badge>
                  </div>
                  <p className="mt-1 text-ink-muted">{lastReply.pendingProposal.summary}</p>
                  {lastReply.pendingProposal.status === 'PENDING_APPROVAL' && (
                    <div className="mt-2 flex gap-2">
                      <Button size="sm" variant="primary" icon={<CheckCircle2 className="h-3.5 w-3.5" />} onClick={() => decideMut.mutate({ id: lastReply.pendingProposal!.id, approve: true })}>
                        Approve & Execute
                      </Button>
                      <Button size="sm" variant="danger" icon={<XCircle className="h-3.5 w-3.5" />} onClick={() => decideMut.mutate({ id: lastReply.pendingProposal!.id, approve: false })}>
                        Reject
                      </Button>
                    </div>
                  )}
                </div>
              )}

              <div className="max-h-96 space-y-2 overflow-y-auto rounded border border-line bg-canvas p-3">
                {(activeSession?.messages ?? []).length === 0 ? (
                  <p className="text-center text-xs text-ink-faint">Start a conversation by pressing Push to Talk or sending a message.</p>
                ) : (
                  activeSession?.messages.map((m) => (
                    <div key={m.id} className={m.role === 'user' ? 'ml-8 rounded bg-accent/10 p-2.5 text-sm text-ink' : 'mr-8 rounded border border-line bg-surface p-2.5 text-sm text-ink'}>
                      <div className="mb-0.5 text-2xs uppercase text-ink-faint">{m.role}</div>
                      <div className="whitespace-pre-wrap">{m.content}</div>
                    </div>
                  ))
                )}
              </div>
            </PanelBody>
          </Panel>
        </div>

        <div className="lg:col-span-4">
          <Panel>
            <PanelHeader title="Conversation History" />
            <PanelBody className="space-y-1.5">
              <Button size="sm" variant="secondary" className="w-full" onClick={() => { setActiveSessionId(undefined); setLastReply(null); }}>
                + New Conversation
              </Button>
              {(sessionsQ.data ?? []).map((s) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => setActiveSessionId(Number(s.id))}
                  className="block w-full truncate rounded border border-line bg-surface-raised px-2.5 py-2 text-left text-xs text-ink hover:border-accent"
                >
                  {s.title}
                </button>
              ))}
            </PanelBody>
          </Panel>
        </div>
      </div>
    </div>
  );
}

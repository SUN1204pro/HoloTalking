import { useState, useRef, useEffect } from "react";
import TabGroup from "../common/TabGroup";

const VIETNEU_VOICES = [
  { id: "Thái Sơn", name: "Thái Sơn (Bắc - Trầm ấm)", region: "Miền Bắc" },
  { id: "Ngọc Huyền", name: "Ngọc Huyền (Bắc - Dịu dàng)", region: "Miền Bắc" },
  { id: "Nam Phương", name: "Nam Phương (Nam - Hào sảng)", region: "Miền Nam" },
  { id: "Minh Hoàng", name: "Minh Hoàng (Trung - Điềm tĩnh)", region: "Miền Trung" },
  { id: "Bảo Quốc", name: "Bảo Quốc (Bắc - Uy nghi Lịch sử)", region: "Miền Bắc" },
  { id: "Kim Ngân", name: "Kim Ngân (Nam - Ngọt ngào)", region: "Miền Nam" },
];

function InputArea({
  activeTab, setActiveTab, scriptText, setScriptText, audioFile, setAudioFile,
  selectedVoice, setSelectedVoice, useGemini, setUseGemini, persona, setPersona,
  handleGenerate
}) {
  // Live Microphone Recording states
  const [isRecording, setIsRecording] = useState(false);
  const [recordTimer, setRecordTimer] = useState(0);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const timerIntervalRef = useRef(null);

  useEffect(() => {
    return () => {
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
    };
  }, []);

  const startLiveRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorderRef.current = new MediaRecorder(stream);
      audioChunksRef.current = [];

      mediaRecorderRef.current.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorderRef.current.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: "audio/wav" });
        const liveFile = new File([audioBlob], `live_mic_voice_${Date.now()}.wav`, { type: "audio/wav" });
        setAudioFile(liveFile);
        stream.getTracks().forEach((track) => track.stop());

        // Automatically trigger generate request to backend immediately
        if (handleGenerate) {
          setTimeout(() => {
            handleGenerate(liveFile);
          }, 300);
        }
      };

      mediaRecorderRef.current.start();
      setIsRecording(true);
      setRecordTimer(0);

      timerIntervalRef.current = setInterval(() => {
        setRecordTimer((prev) => prev + 1);
      }, 1000);
    } catch (err) {
      console.error("Microphone access error:", err);
      alert("Microphone access was denied or is not supported.");
    }
  };

  const stopLiveRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
    }
  };

  const formatTimer = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins < 10 ? "0" : ""}${mins}:${secs < 10 ? "0" : ""}${secs}`;
  };

  return (
    <div className="flex flex-col gap-3">
      <div>
        <label className="block font-label text-[10px] text-outline mb-2">
          CHOOSE INPUT METHOD
        </label>
        <TabGroup activeTab={activeTab} setActiveTab={setActiveTab} />
      </div>

      {/* TEXT TAB */}
      {activeTab === "TEXT" && (
        <>
          {/* Vietneu Voice Selector */}
          <div>
            <label className="block font-label text-[10px] text-outline mb-1">
              VIETNEU TTS VOICE
            </label>
            <select
              value={selectedVoice}
              onChange={(e) => setSelectedVoice(e.target.value)}
              className="w-full text-xs bg-black/40 text-on-surface rounded-xl border border-outline-variant/60 p-2.5 outline-none focus:border-secondary transition-colors"
            >
              {VIETNEU_VOICES.map((v) => (
                <option key={v.id} value={v.id} className="bg-neutral-900 text-white">
                  🎙️ {v.name}
                </option>
              ))}
            </select>
          </div>

          {/* Gemini AI Agent Toggle */}
          <div className="p-3 bg-black/30 border border-outline-variant/40 rounded-xl">
            <div className="flex items-center justify-between">
              <label htmlFor="gemini-toggle" className="flex items-center gap-2 text-xs font-label text-secondary cursor-pointer bronze-glow">
                <span>✨ Gemini AI Agent Response</span>
              </label>
              <input
                id="gemini-toggle"
                type="checkbox"
                checked={useGemini}
                onChange={(e) => setUseGemini(e.target.checked)}
                className="w-4 h-4 accent-amber-400 cursor-pointer"
              />
            </div>
            {useGemini && (
              <div className="mt-2.5 flex flex-col gap-2">
                <input
                  type="text"
                  value={persona}
                  onChange={(e) => setPersona(e.target.value)}
                  placeholder="Character Persona (e.g. Vua Lý Thái Tổ...)"
                  className="w-full text-xs bg-black/60 rounded-lg border border-outline-variant/50 p-2 outline-none focus:border-secondary text-on-surface placeholder:text-outline/70"
                />
              </div>
            )}
          </div>

          {/* Text script area */}
          <div>
            <label className="block font-label text-[10px] text-outline mb-1">
              {useGemini ? "GEMINI AI PROMPT / QUESTION" : "TEXT SCRIPT TO SPEAK"}
            </label>
            <textarea
              value={scriptText}
              onChange={(e) => setScriptText(e.target.value)}
              placeholder={
                useGemini
                  ? "Enter a prompt for Gemini AI to answer (e.g. Hãy tự giới thiệu về công ơn khai quốc của bạn...)"
                  : "Enter the exact text script for the historical character to speak..."
              }
              className="w-full min-h-[90px] text-xs bg-black/40 rounded-xl border border-outline-variant/60 p-3 outline-none focus:border-secondary resize-none transition-colors custom-scrollbar"
            />
          </div>
        </>
      )}

      {/* LIVE MIC TAB */}
      {activeTab === "LIVE_MIC" && (
        <div className="flex flex-col gap-3">
          {/* Gemini AI Agent Toggle for Live Mic */}
          <div className="p-3 bg-black/30 border border-outline-variant/40 rounded-xl">
            <div className="flex items-center justify-between">
              <label htmlFor="gemini-mic-toggle" className="flex items-center gap-2 text-xs font-label text-secondary cursor-pointer bronze-glow">
                <span>✨ Gemini AI Speech-to-Speech Mode</span>
              </label>
              <input
                id="gemini-mic-toggle"
                type="checkbox"
                checked={useGemini}
                onChange={(e) => setUseGemini(e.target.checked)}
                className="w-4 h-4 accent-amber-400 cursor-pointer"
              />
            </div>
            {useGemini && (
              <div className="mt-2.5 flex flex-col gap-2">
                <input
                  type="text"
                  value={persona}
                  onChange={(e) => setPersona(e.target.value)}
                  placeholder="Character Persona (e.g. Vua Lý Thái Tổ...)"
                  className="w-full text-xs bg-black/60 rounded-lg border border-outline-variant/50 p-2 outline-none focus:border-secondary text-on-surface placeholder:text-outline/70"
                />
              </div>
            )}
          </div>

          {/* LIVE RECORDING PANEL */}
          <div className="p-5 bg-black/40 border border-secondary/40 rounded-2xl flex flex-col items-center justify-center text-center bronze-glow">
            {isRecording ? (
              <div className="flex flex-col items-center gap-3 w-full">
                <div className="flex items-center gap-2 text-red-400 font-mono text-sm animate-pulse">
                  <span className="w-3.5 h-3.5 rounded-full bg-red-500 animate-ping" />
                  <span>RECORDING LIVE VOICE ({formatTimer(recordTimer)})</span>
                </div>
                <p className="text-[11px] text-outline italic">Speak clearly into your microphone...</p>
                <button
                  type="button"
                  onClick={stopLiveRecording}
                  className="mt-2 px-6 py-2.5 rounded-xl bg-red-600 hover:bg-red-500 text-white font-label text-xs tracking-wider uppercase flex items-center gap-2 cursor-pointer shadow-lg transition-all"
                >
                  <span className="material-symbols-outlined text-base">stop_circle</span>
                  Stop & Save Recorded Voice
                </button>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-3 w-full">
                <p className="text-[11px] text-outline uppercase font-label">Record live microphone speech session</p>
                <button
                  type="button"
                  onClick={startLiveRecording}
                  className="w-full py-3.5 px-4 rounded-xl bg-secondary/20 hover:bg-secondary/30 border border-secondary/60 text-secondary font-label text-xs tracking-wider uppercase flex items-center justify-center gap-2 cursor-pointer bronze-glow transition-all font-bold"
                >
                  <span className="material-symbols-outlined text-xl text-secondary">mic</span>
                  Start Live Mic Recording
                </button>
              </div>
            )}
          </div>

          {audioFile && (
            <div className="p-3 bg-black/30 border border-outline-variant/40 rounded-xl">
              <div className="text-xs text-secondary font-mono mb-2">✓ Recorded Live Audio: {audioFile.name}</div>
              <audio controls className="w-full" src={URL.createObjectURL(audioFile)} />
            </div>
          )}
        </div>
      )}

      {/* AUDIO FILE TAB */}
      {activeTab === "AUDIO" && (
        <div className="flex flex-col gap-3">
          <div className="border border-dashed border-outline-variant/60 rounded-2xl p-6 text-center bg-black/20">
            <input
              type="file"
              accept=".mp3,.wav,.m4a,audio/*"
              id="audio-upload"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) setAudioFile(file);
              }}
            />
            <label htmlFor="audio-upload" className="cursor-pointer block">
              <p className="text-sm text-outline">Click to upload audio file</p>
              <p className="text-xs mt-2 text-outline">MP3, WAV, M4A</p>
            </label>
            {audioFile && (
              <div className="mt-4 text-secondary text-sm font-mono">✓ {audioFile.name}</div>
            )}
          </div>

          {audioFile && (
            <audio controls className="w-full mt-1" src={URL.createObjectURL(audioFile)} />
          )}
        </div>
      )}
    </div>
  );
}

export default InputArea;
import { useState, useRef, useEffect } from "react";
import TabGroup from "../common/TabGroup";
import { API_BASE } from "../../api";

const VIETNEU_VOICES = [
  { id: "Thái Sơn", name: "Thái Sơn (Nam - Bắc trầm ấm, dõng dạc)" },
  { id: "Gia Bảo", name: "Gia Bảo (Nam - Nam Bộ truyền cảm)" },
  { id: "Đức Trí", name: "Đức Trí (Nam - Bắc uy nghi, truyền cảm)" },
  { id: "Ngọc Lan", name: "Ngọc Lan (Nữ - Bắc dịu dàng, trong trẻo)" },
  { id: "Mỹ Duyên", name: "Mỹ Duyên (Nữ - Nam Bộ ngọt ngào)" },
  { id: "Trúc Ly", name: "Trúc Ly (Nữ - Miền Trung điềm tĩnh)" },
  { id: "Xuân Vĩnh", name: "Xuân Vĩnh (Nam - Bắc rõ ràng, hùng hồn)" },
  { id: "Trọng Hữu", name: "Trọng Hữu (Nam - Nam Bộ nồng ấm)" },
  { id: "Bình An", name: "Bình An (Nam - Miền Trung mộc mạc)" },
  { id: "Ngọc Linh", name: "Ngọc Linh (Nữ - Bắc truyền cảm)" },
];

// Voice engine + speed controls, shared by the TEXT and LIVE_MIC tabs.
function VoiceEngineSelector({
  voices, selectedVoice, setSelectedVoice,
  ttsSpeed, setTtsSpeed, ttsEngine, setTtsEngine,
  elevenlabsVoiceId, setElevenlabsVoiceId,
  voiceStyle, setVoiceStyle,
  customVoiceRef, setCustomVoiceRef,
}) {
  const [elevenlabsVoices, setElevenlabsVoices] = useState([]);
  const [voiceUploadStatus, setVoiceUploadStatus] = useState("idle"); // idle | uploading | ready | error
  const [voiceUploadError, setVoiceUploadError] = useState("");

  const handleVoiceRefUpload = async (file) => {
    if (!file) return;
    setVoiceUploadStatus("uploading");
    setVoiceUploadError("");
    try {
      const fd = new FormData();
      fd.append("audio", file);
      const res = await fetch(`${API_BASE}/api/custom_voice/upload`, { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Upload failed");
      setCustomVoiceRef(data.ref_id);
      setVoiceUploadStatus("ready");
    } catch (err) {
      setVoiceUploadError(err.message || "Upload failed");
      setVoiceUploadStatus("error");
    }
  };
  const [elevenlabsStatus, setElevenlabsStatus] = useState("idle"); // idle | loading | ready | error
  const [elevenlabsError, setElevenlabsError] = useState("");

  // VoxCPM cloning source: an ElevenLabs voice, or -- fully local and free -- a VieNeu
  // preset's own timbre used directly as the reference (no ElevenLabs involved).
  const [voxcpmCloneSource, setVoxcpmCloneSource] = useState("elevenlabs"); // "elevenlabs" | "vietneu"

  // Voice Changer (Speech-to-Speech): upload a recording, convert it into the selected
  // ElevenLabs voice, and use the result as a richer VoxCPM cloning reference.
  const [showVoiceChanger, setShowVoiceChanger] = useState(false);
  const [changerFile, setChangerFile] = useState(null);
  const [changerStatus, setChangerStatus] = useState("idle"); // idle | converting | ready | error
  const [changerError, setChangerError] = useState("");
  const [changerResultUrl, setChangerResultUrl] = useState("");

  useEffect(() => {
    if (ttsEngine !== "voxcpm" || elevenlabsStatus !== "idle") return;
    const loadInitialVoices = async () => {
      setElevenlabsStatus("loading");
      try {
        const res = await fetch(`${API_BASE}/api/elevenlabs/voices`);
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to load ElevenLabs voices");
        setElevenlabsVoices(data);
        setElevenlabsStatus("ready");
        if (!elevenlabsVoiceId && data.length > 0) setElevenlabsVoiceId(data[0].id);
      } catch (err) {
        setElevenlabsError(err.message || "Failed to load ElevenLabs voices");
        setElevenlabsStatus("error");
      }
    };
    loadInitialVoices();
  }, [ttsEngine]);

  const selectedElevenlabsVoice = elevenlabsVoices.find((v) => v.id === elevenlabsVoiceId);

  const handleConvertVoice = async () => {
    if (!changerFile || !elevenlabsVoiceId) return;
    setChangerStatus("converting");
    setChangerError("");
    setChangerResultUrl("");
    try {
      const formData = new FormData();
      formData.append("voice_id", elevenlabsVoiceId);
      formData.append("audio", changerFile);
      const res = await fetch(`${API_BASE}/api/elevenlabs/voice-changer`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Voice changer conversion failed");
      setChangerResultUrl(`${data.reference_audio_url}?t=${Date.now()}`);
      setChangerStatus("ready");
    } catch (err) {
      setChangerError(err.message || "Voice changer conversion failed");
      setChangerStatus("error");
    }
  };

  return (
    <>
      {/* TTS Engine Toggle */}
      <div>
        <label className="block font-label text-[10px] text-outline mb-1">TTS ENGINE</label>
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => setTtsEngine("vietneu")}
            className={`text-[10px] font-label uppercase py-2 rounded-xl border transition-colors cursor-pointer ${
              ttsEngine === "vietneu"
                ? "bg-secondary text-black border-secondary font-bold"
                : "bg-black/40 text-outline border-outline-variant/60 hover:border-secondary/60"
            }`}
          >
            Vietneu Presets
          </button>
          <button
            type="button"
            onClick={() => setTtsEngine("voxcpm")}
            className={`text-[10px] font-label uppercase py-2 rounded-xl border transition-colors cursor-pointer ${
              ttsEngine === "voxcpm"
                ? "bg-secondary text-black border-secondary font-bold"
                : "bg-black/40 text-outline border-outline-variant/60 hover:border-secondary/60"
            }`}
          >
            Custom Voice (11L → VoxCPM)
          </button>
        </div>
      </div>

      {ttsEngine === "vietneu" ? (
        /* Vietneu Voice Selector */
        <div>
          <label className="block font-label text-[10px] text-outline mb-1">
            VIETNEU TTS VOICE
          </label>
          <select
            value={selectedVoice}
            onChange={(e) => setSelectedVoice(e.target.value)}
            className="w-full text-xs bg-black/40 text-on-surface rounded-xl border border-outline-variant/60 p-2.5 outline-none focus:border-secondary transition-colors"
          >
            {voices.map((v) => (
              <option key={v.id} value={v.id} className="bg-neutral-900 text-white">
                🎙️ {v.name}
              </option>
            ))}
          </select>
        </div>
      ) : (
        /* VoxCPM cloning reference: an ElevenLabs voice, or a local VieNeu preset */
        <div>
          <label className="block font-label text-[10px] text-outline mb-1">
            VOXCPM CLONE SOURCE
          </label>
          <div className="grid grid-cols-3 gap-2 mb-2">
            <button
              type="button"
              onClick={() => { setVoxcpmCloneSource("elevenlabs"); setCustomVoiceRef(""); }}
              className={`text-[10px] font-label uppercase py-1.5 rounded-lg border transition-colors cursor-pointer ${
                voxcpmCloneSource === "elevenlabs"
                  ? "bg-secondary text-black border-secondary font-bold"
                  : "bg-black/40 text-outline border-outline-variant/60 hover:border-secondary/60"
              }`}
            >
              ElevenLabs
            </button>
            <button
              type="button"
              onClick={() => { setVoxcpmCloneSource("vietneu"); setElevenlabsVoiceId(""); setCustomVoiceRef(""); }}
              className={`text-[10px] font-label uppercase py-1.5 rounded-lg border transition-colors cursor-pointer ${
                voxcpmCloneSource === "vietneu"
                  ? "bg-secondary text-black border-secondary font-bold"
                  : "bg-black/40 text-outline border-outline-variant/60 hover:border-secondary/60"
              }`}
            >
              VieNeu Preset
            </button>
            <button
              type="button"
              onClick={() => { setVoxcpmCloneSource("upload"); setElevenlabsVoiceId(""); }}
              className={`text-[10px] font-label uppercase py-1.5 rounded-lg border transition-colors cursor-pointer ${
                voxcpmCloneSource === "upload"
                  ? "bg-secondary text-black border-secondary font-bold"
                  : "bg-black/40 text-outline border-outline-variant/60 hover:border-secondary/60"
              }`}
            >
              Upload Voice
            </button>
          </div>

          {voxcpmCloneSource === "upload" ? (
            <div className="space-y-1.5">
              <input
                type="file"
                accept="audio/*"
                onChange={(e) => handleVoiceRefUpload(e.target.files?.[0])}
                className="w-full text-[11px] text-outline file:mr-2 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-[10px] file:font-label file:uppercase file:bg-secondary file:text-black file:cursor-pointer"
              />
              <p className="text-[10px] text-outline italic">
                Upload a clean 5-20s speech sample. VoxCPM clones this voice directly -- no ElevenLabs, fully local.
              </p>
              {voiceUploadStatus === "uploading" && (
                <p className="text-[10px] text-secondary">Uploading &amp; preparing reference...</p>
              )}
              {voiceUploadStatus === "ready" && customVoiceRef && (
                <p className="text-[10px] text-emerald-400">Voice reference ready ({customVoiceRef}).</p>
              )}
              {voiceUploadStatus === "error" && (
                <p className="text-[10px] text-red-400">{voiceUploadError}</p>
              )}
            </div>
          ) : voxcpmCloneSource === "vietneu" ? (
            <div>
              <select
                value={selectedVoice}
                onChange={(e) => setSelectedVoice(e.target.value)}
                className="w-full text-xs bg-black/40 text-on-surface rounded-xl border border-outline-variant/60 p-2.5 outline-none focus:border-secondary transition-colors"
              >
                {voices.map((v) => (
                  <option key={v.id} value={v.id} className="bg-neutral-900 text-white">
                    🎙️ {v.name}
                  </option>
                ))}
              </select>
              <p className="text-[10px] text-outline mt-1.5 italic">
                VoxCPM clones this VieNeu preset's own voice directly -- no ElevenLabs API calls, fully local and free.
              </p>
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between mb-1">
                <label className="block font-label text-[10px] text-outline">
                  ELEVENLABS VOICE (VOXCPM REFERENCE)
                </label>
                <button
                  type="button"
                  onClick={() => setShowVoiceChanger((s) => !s)}
                  className="text-[10px] font-label uppercase text-secondary hover:underline cursor-pointer"
                >
                  {showVoiceChanger ? "Cancel" : "+ Voice changer"}
                </button>
              </div>

              {showVoiceChanger && (
                <div className="mb-3 p-2.5 rounded-xl border border-outline-variant/60 bg-black/30 space-y-2">
                  <p className="text-[10px] text-outline italic">
                    Upload a recording of any speech. It will be converted into the voice selected below (same words/timing, different voice) and used as a richer VoxCPM cloning reference.
                  </p>
                  <input
                    type="file"
                    accept="audio/*"
                    onChange={(e) => setChangerFile(e.target.files?.[0] || null)}
                    className="w-full text-[11px] text-outline file:mr-2 file:py-1.5 file:px-2.5 file:rounded-lg file:border-0 file:bg-secondary file:text-black file:text-[10px] file:font-label file:uppercase file:cursor-pointer cursor-pointer"
                  />
                  <button
                    type="button"
                    onClick={handleConvertVoice}
                    disabled={!changerFile || !elevenlabsVoiceId || changerStatus === "converting"}
                    className="w-full text-[10px] font-label uppercase py-2 rounded-lg border border-secondary/60 text-secondary hover:bg-secondary/10 disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer"
                  >
                    {changerStatus === "converting" ? "Converting..." : "Convert & use as reference"}
                  </button>

                  {changerStatus === "error" && (
                    <div className="text-[11px] text-red-400">⚠ {changerError}</div>
                  )}

                  {changerStatus === "ready" && changerResultUrl && (
                    <div className="space-y-1">
                      <div className="text-[11px] text-secondary">✓ Reference updated for the selected voice.</div>
                      <audio controls className="w-full" src={changerResultUrl} />
                    </div>
                  )}
                </div>
              )}

              {elevenlabsStatus === "loading" && (
                <div className="text-[11px] text-outline italic px-1 py-2">Loading your ElevenLabs voice library...</div>
              )}

              {elevenlabsStatus === "error" && (
                <div className="text-[11px] text-red-400 px-1 py-2">
                  ⚠ {elevenlabsError}. Set <code className="font-mono">ELEVENLABS_API_KEY</code> in the backend .env.
                </div>
              )}

              {elevenlabsStatus === "ready" && (
                <>
                  <select
                    value={elevenlabsVoiceId}
                    onChange={(e) => setElevenlabsVoiceId(e.target.value)}
                    className="w-full text-xs bg-black/40 text-on-surface rounded-xl border border-outline-variant/60 p-2.5 outline-none focus:border-secondary transition-colors"
                  >
                    {elevenlabsVoices.map((v) => (
                      <option key={v.id} value={v.id} className="bg-neutral-900 text-white">
                        🗣️ {v.name}{v.category ? ` (${v.category})` : ""}
                      </option>
                    ))}
                  </select>
                  {selectedElevenlabsVoice?.preview_url && (
                    <audio controls className="w-full mt-2" src={selectedElevenlabsVoice.preview_url} />
                  )}
                  <p className="text-[10px] text-outline mt-1.5 italic">
                    VoxCPM clones this voice's timbre from a VieNeu Vietnamese sample re-voiced via ElevenLabs, then speaks your text locally.
                  </p>
                </>
              )}
            </>
          )}
        </div>
      )}

      {ttsEngine === "voxcpm" && (
        /* VoxCPM follows a natural-language style/delivery instruction prepended to
           the line, e.g. "deep, solemn, regal tone, speaking slowly and with authority". */
        <div>
          <label className="block font-label text-[10px] text-outline mb-1">
            VOICE STYLE / DELIVERY (OPTIONAL)
          </label>
          <textarea
            value={voiceStyle}
            onChange={(e) => setVoiceStyle(e.target.value)}
            placeholder="e.g. deep male Vietnamese king voice, dignified, majestic, speaking slowly with authority"
            className="w-full min-h-[60px] text-xs bg-black/40 rounded-xl border border-outline-variant/60 p-2.5 outline-none focus:border-secondary resize-none transition-colors custom-scrollbar"
          />
          <p className="text-[10px] text-outline mt-1 italic">
            Describe the tone/emotion in plain language. VoxCPM steers its delivery to match.
          </p>
        </div>
      )}

      {/* TTS Speed */}
      <div>
        <div className="flex justify-between text-[10px] text-outline mb-1 font-label">
          <span>SPEECH SPEED</span>
          <span className="text-secondary font-mono">{ttsSpeed.toFixed(1)}x</span>
        </div>
        <input
          type="range"
          min="0.5"
          max="2.0"
          step="0.1"
          value={ttsSpeed}
          onChange={(e) => setTtsSpeed(parseFloat(e.target.value))}
          className="w-full accent-amber-400 cursor-pointer"
        />
      </div>
    </>
  );
}

function InputArea({
  activeTab, setActiveTab, scriptText, setScriptText, audioFile, setAudioFile,
  selectedVoice, setSelectedVoice, ttsSpeed, setTtsSpeed,
  ttsEngine, setTtsEngine, elevenlabsVoiceId, setElevenlabsVoiceId,
  voiceStyle, setVoiceStyle,
  customVoiceRef, setCustomVoiceRef,
  useGemini, setUseGemini, persona, setPersona, clearConversation,
  handleGenerate
}) {
  const [voices, setVoices] = useState(VIETNEU_VOICES);

  // Fetch dynamic voices from backend if available
  useEffect(() => {
    fetch(`${API_BASE}/api/voices`)
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setVoices(
            data.map((v) => ({
              id: v.id,
              name: `${v.name} (${v.gender || ''} - ${v.region || ''} ${v.desc ? '- ' + v.desc : ''})`.trim()
            }))
          );
        }
      })
      .catch(() => {});
  }, []);

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
      // MediaRecorder actually encodes as WebM/Opus (or whatever the browser supports) --
      // it does not produce real WAV/PCM. Label the blob honestly; the backend transcodes
      // by content via ffmpeg regardless, but a correct extension/type avoids confusion.
      const mimeType = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "";
      mediaRecorderRef.current = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      const recordedMimeType = mediaRecorderRef.current.mimeType || "audio/webm";
      audioChunksRef.current = [];

      mediaRecorderRef.current.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorderRef.current.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: recordedMimeType });
        const liveFile = new File([audioBlob], `live_mic_voice_${Date.now()}.webm`, { type: recordedMimeType });
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
          <VoiceEngineSelector
            voices={voices} selectedVoice={selectedVoice} setSelectedVoice={setSelectedVoice}
            ttsSpeed={ttsSpeed} setTtsSpeed={setTtsSpeed}
            ttsEngine={ttsEngine} setTtsEngine={setTtsEngine}
            elevenlabsVoiceId={elevenlabsVoiceId} setElevenlabsVoiceId={setElevenlabsVoiceId}
            voiceStyle={voiceStyle} setVoiceStyle={setVoiceStyle}
            customVoiceRef={customVoiceRef} setCustomVoiceRef={setCustomVoiceRef}
          />

          {/* Text script area */}
          <div>
            <label className="block font-label text-[10px] text-outline mb-1">
              TEXT SCRIPT TO SPEAK
            </label>
            <textarea
              value={scriptText}
              onChange={(e) => setScriptText(e.target.value)}
              placeholder="Enter the exact text script for the historical character to speak..."
              className="w-full min-h-[90px] text-xs bg-black/40 rounded-xl border border-outline-variant/60 p-3 outline-none focus:border-secondary resize-none transition-colors custom-scrollbar"
            />
          </div>
        </>
      )}

      {/* LIVE MIC TAB */}
      {activeTab === "LIVE_MIC" && (
        <div className="flex flex-col gap-3">
          <VoiceEngineSelector
            voices={voices} selectedVoice={selectedVoice} setSelectedVoice={setSelectedVoice}
            ttsSpeed={ttsSpeed} setTtsSpeed={setTtsSpeed}
            ttsEngine={ttsEngine} setTtsEngine={setTtsEngine}
            elevenlabsVoiceId={elevenlabsVoiceId} setElevenlabsVoiceId={setElevenlabsVoiceId}
            voiceStyle={voiceStyle} setVoiceStyle={setVoiceStyle}
            customVoiceRef={customVoiceRef} setCustomVoiceRef={setCustomVoiceRef}
          />

          {/* Gemini AI Agent Toggle for Live Mic */}
          <div className="p-3 bg-black/30 border border-outline-variant/40 rounded-xl">
            <div className="flex items-center justify-between">
              <label htmlFor="gemini-mic-toggle" className="flex items-center gap-2 text-xs font-label text-secondary cursor-pointer bronze-glow">
                <span>✨ AI Agent Reply (Claude)</span>
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
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-outline italic">The avatar remembers this whole conversation.</span>
                  <button
                    type="button"
                    onClick={clearConversation}
                    className="text-[10px] font-label uppercase text-red-400 hover:underline cursor-pointer"
                  >
                    Clear memory
                  </button>
                </div>
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

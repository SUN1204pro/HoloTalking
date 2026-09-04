import { useState, useRef, useEffect } from "react";
import Sidebar from "./components/Sidebar/Sidebar";
import VideoArea from "./components/VideoArea/VideoArea";
import { API_BASE } from "./api";

// Stable conversation id so the avatar's server-side memory persists across
// reloads. One "brain" per browser.
function getSessionId() {
  try {
    let id = localStorage.getItem("holo_session_id");
    if (!id) {
      id = "sess_" + Math.random().toString(36).slice(2) + Date.now().toString(36);
      localStorage.setItem("holo_session_id", id);
    }
    return id;
  } catch {
    return "default";
  }
}

function App() {
  const [sessionId] = useState(getSessionId);

  const clearConversation = async () => {
    try {
      const fd = new FormData();
      fd.append("session_id", sessionId);
      await fetch(`${API_BASE}/api/history/clear`, { method: "POST", body: fd });
    } catch (e) {
      console.error("Failed to clear conversation memory", e);
    }
  };

  // STATE CỦA SIDEBAR
  const [scriptText, setScriptText] = useState("");
  const [activeTab, setActiveTab] = useState("TEXT");
  const [selectedImage, setSelectedImage] = useState(null);
  const [audioFile, setAudioFile] = useState(null);
  const [portraitFile, setPortraitFile] = useState(null);
  const [errorMessage, setErrorMessage] = useState("");

  // VIETNEU & GEMINI & SADTALKER STATES
  const [selectedVoice, setSelectedVoice] = useState("Thái Sơn");
  const [ttsSpeed, setTtsSpeed] = useState(1.0);
  const [ttsEngine, setTtsEngine] = useState("vietneu"); // "vietneu" | "voxcpm"
  const [elevenlabsVoiceId, setElevenlabsVoiceId] = useState("");
  const [voiceStyle, setVoiceStyle] = useState("");
  const [customVoiceRef, setCustomVoiceRef] = useState(""); // ref_id from /api/custom_voice/upload
  const [useGemini, setUseGemini] = useState(true);
  const [persona, setPersona] = useState("");
  const [fastMode, setFastMode] = useState(true);
  const [lipsyncEngine, setLipsyncEngine] = useState("wav2lip");
  const [preprocess, setPreprocess] = useState("full");
  const [enhancer, setEnhancer] = useState("none");
  const [still, setStill] = useState(true);
  const [expressionScale, setExpressionScale] = useState(1.0);
  const [spokenText, setSpokenText] = useState(null);

  // STATE CỦA VIDEO AREA & GENERATION
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedVideoUrl, setGeneratedVideoUrl] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [bgRemovedImageUrl, setBgRemovedImageUrl] = useState(null);
  const [idleVideoUrl, setIdleVideoUrl] = useState(null);
  const [isIdleGenerating, setIsIdleGenerating] = useState(false);
  const videoRef = useRef(null);

  // Streaming playback: clips arrive one sentence at a time over SSE. `isLastClip`
  // drives whether the <video> should loop (single/final clip, old behavior) or fire
  // onEnded so we can advance to the next queued clip as soon as it's ready.
  const [isLastClip, setIsLastClip] = useState(true);
  const clipQueueRef = useRef([]);
  const streamRef = useRef({ total: 1, currentIndex: -1, waitingForNext: false });

  // Poll the backend warm-up state. While it's setting up models, block the UI.
  const [serverWarming, setServerWarming] = useState(true);
  const [warmupStage, setWarmupStage] = useState("starting");
  useEffect(() => {
    let stop = false;
    const check = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/health`);
        const data = await res.json();
        if (stop) return;
        setServerWarming(!!data.warming_up);
        setWarmupStage(data.warmup_stage || "");
        if (!data.warming_up) return; // done polling
      } catch {
        if (stop) return;
        setServerWarming(true);
      }
      if (!stop) setTimeout(check, 2000);
    };
    check();
    return () => { stop = true; };
  }, []);

  // In LIVE_MIC you can either record OR type a message to the AI.
  const liveTextMode = activeTab === "LIVE_MIC" && !audioFile && scriptText.trim().length >= 2;

  const isGenerateReady =
    !serverWarming &&
    selectedImage &&
    ((activeTab === "TEXT" && scriptText.trim().length >= 3) ||
      (activeTab === "AUDIO" && audioFile !== null) ||
      (activeTab === "LIVE_MIC" && (audioFile !== null || liveTextMode)));

  // --- FUNCTIONS ---
  const handleImageUpload = (event) => {
    const file = event.target.files[0];
    if (!file) return;
    setPortraitFile(file);
    const imageUrl = URL.createObjectURL(file);
    setSelectedImage(imageUrl);
    setBgRemovedImageUrl(null);
    setIdleVideoUrl(null);
    setGeneratedVideoUrl(null);

    processAvatarAndGenerateIdle(file, imageUrl);
  };

  const onSelectCharacter = (imgSrc, charObj) => {
    setSelectedImage(imgSrc);
    setPortraitFile(null);
    setBgRemovedImageUrl(null);
    setIdleVideoUrl(null);
    setGeneratedVideoUrl(null);

    const presetName = typeof charObj === "object" ? charObj.filename || charObj.id : imgSrc.split("/").pop();
    processAvatarAndGenerateIdle(null, imgSrc, presetName);
  };

  const processAvatarAndGenerateIdle = async (file, originalImageUrl, presetFileName = null) => {
    setIsIdleGenerating(true);
    try {
      // Preprocess (Remove background)
      const preprocessFormData = new FormData();
      if (file) {
        preprocessFormData.append("image", file);
      } else if (presetFileName) {
        preprocessFormData.append("preset_avatar", presetFileName);
      } else if (originalImageUrl) {
        try {
          const res = await fetch(originalImageUrl);
          const blob = await res.blob();
          const imgFile = new File([blob], "selected_avatar.png", { type: blob.type || "image/png" });
          preprocessFormData.append("image", imgFile);
        } catch (e) {
          preprocessFormData.append("preset_avatar", originalImageUrl.split("/").pop());
        }
      }
      
      const preprocessRes = await fetch(`${API_BASE}/preprocess_avatar`, {
        method: "POST",
        body: preprocessFormData,
      });
      
      if (!preprocessRes.ok) {
        throw new Error("Failed to preprocess avatar");
      }
      
      const preprocessData = await preprocessRes.json();
      const cleanImageUrl = preprocessData.processed_image_url;
      setBgRemovedImageUrl(cleanImageUrl);
      setSelectedImage(cleanImageUrl);
      setIdleVideoUrl(null);

      // Fire-and-forget: render a freeze (idle, subtle head motion) clip and a
      // motion (talking) clip from this avatar, then save both to Downloads.
      generateAndDownloadAvatarClips();
    } catch (error) {
      console.error("Avatar Preprocess Error:", error);
    } finally {
      setIsIdleGenerating(false);
    }
  };

  const triggerBrowserDownload = (url, filename) => {
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  const generateAndDownloadAvatarClips = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/avatar_clips/generate`, { method: "POST" });
      if (!res.ok) throw new Error(`avatar clip generation failed (${res.status})`);
      const data = await res.json();
      // Two back-to-back <a download> clicks in the same tick can race each
      // other (one request gets aborted before it completes) -- space them out.
      triggerBrowserDownload(`${API_BASE}${data.freeze_path}`, "freeze.mp4");
      await new Promise((r) => setTimeout(r, 800));
      triggerBrowserDownload(`${API_BASE}${data.motion_path}`, "motion.mp4");
    } catch (error) {
      console.error("Avatar clips (freeze/motion) generation error:", error);
    }
  };

  // Plays the next clip if it's already queued; otherwise marks that we're waiting
  // so the SSE reader can hand it off the moment it arrives.
  const playNextQueuedClip = () => {
    const state = streamRef.current;
    const nextIndex = state.currentIndex + 1;
    const queuedIdx = clipQueueRef.current.findIndex((c) => c.index === nextIndex);
    if (queuedIdx !== -1) {
      const clip = clipQueueRef.current.splice(queuedIdx, 1)[0];
      state.currentIndex = clip.index;
      state.waitingForNext = false;
      setIsLastClip(clip.index >= state.total - 1);
      setGeneratedVideoUrl(`${clip.video_url}?t=${Date.now()}`);
    } else {
      state.waitingForNext = true;
    }
  };

  const handleClipEnded = () => {
    playNextQueuedClip();
  };

  const handleGenerate = async (overrideAudioFile = null) => {
    const targetAudio = overrideAudioFile || audioFile;
    setErrorMessage("");

    if (!selectedImage) {
      setErrorMessage("Please upload or select a portrait image.");
      return;
    }

    if (activeTab === "TEXT" && scriptText.trim().length < 3) {
      setErrorMessage("Please enter at least 3 characters.");
      return;
    }

    if ((activeTab === "AUDIO" || activeTab === "LIVE_MIC") && !targetAudio) {
      setErrorMessage("Please record or upload an audio file.");
      return;
    }

    setIsGenerating(true);
    setGeneratedVideoUrl(null);
    setSpokenText(null);
    setIsPlaying(false);
    clipQueueRef.current = [];
    streamRef.current = { total: 1, currentIndex: -1, waitingForNext: true };
    setIsLastClip(true);

    try {
      const formData = new FormData();

      if (bgRemovedImageUrl) {
        try {
          const res = await fetch(bgRemovedImageUrl);
          const blob = await res.blob();
          const file = new File([blob], "bg_removed_avatar.png", { type: blob.type || "image/png" });
          formData.append("image", file);
          formData.append("skip_bg_remove", "true");
        } catch (e) {
          console.error("Failed to fetch bgRemovedImageUrl", e);
          if (portraitFile) formData.append("image", portraitFile);
        }
      } else if (portraitFile) {
        formData.append("image", portraitFile);
      } else if (selectedImage) {
        try {
          const res = await fetch(selectedImage);
          const blob = await res.blob();
          const file = new File([blob], "selected_avatar.png", { type: blob.type || "image/png" });
          formData.append("image", file);
        } catch (e) {
          const filename = selectedImage.split("/").pop();
          formData.append("preset_avatar", filename);
        }
      }

      if (activeTab === "TEXT" || liveTextMode) {
        // TEXT tab, or LIVE_MIC with a typed message instead of a recording.
        const ai = liveTextMode || useGemini;   // live-mode typing always goes to the AI
        formData.append("inputType", "text");
        formData.append("text", scriptText);
        formData.append("voice_name", selectedVoice);
        formData.append("use_gemini", ai ? "true" : "false");
        if (ai && persona.trim()) formData.append("persona", persona.trim());
      } else {
        formData.append("inputType", "audio");
        formData.append("audio", targetAudio);
        formData.append("voice_name", selectedVoice);
        const isLiveGemini = activeTab === "LIVE_MIC" && useGemini;
        formData.append("use_gemini", isLiveGemini ? "true" : "false");
        if (isLiveGemini && persona.trim()) {
          formData.append("persona", persona.trim());
        }
      }

      formData.append("session_id", sessionId);
      formData.append("speed", ttsSpeed);
      formData.append("tts_engine", ttsEngine);
      if (ttsEngine === "voxcpm" && customVoiceRef) {
        formData.append("custom_voice_ref", customVoiceRef);
      } else if (ttsEngine === "voxcpm" && elevenlabsVoiceId) {
        formData.append("elevenlabs_voice_id", elevenlabsVoiceId);
      }
      if (ttsEngine === "voxcpm" && voiceStyle.trim()) {
        formData.append("voice_style", voiceStyle.trim());
      }
      formData.append("preprocess", preprocess);
      formData.append("enhancer", enhancer);
      formData.append("still", still ? "true" : "false");
      formData.append("expression_scale", expressionScale);
      formData.append("lipsync_engine", lipsyncEngine);

      const response = await fetch(`${API_BASE}/generate_stream`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        let detailMsg = `Server returned status ${response.status}`;
        if (typeof errData.detail === "string") {
          detailMsg = errData.detail;
        } else if (Array.isArray(errData.detail)) {
          detailMsg = errData.detail.map((e) => e.msg || JSON.stringify(e)).join(", ");
        } else if (errData.detail && typeof errData.detail === "object") {
          detailMsg = JSON.stringify(errData.detail);
        }
        throw new Error(detailMsg);
      }

      // Server-Sent Events: "meta" (total clip count + full text) arrives first,
      // then one "clip" event per sentence as each finishes rendering. The first
      // clip is played the instant it arrives; later ones queue and hand off via
      // handleClipEnded (wired to the <video>'s onEnded) as soon as they're ready.
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let sawAnyClip = false;
      let streamError = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        let sepIndex;
        while ((sepIndex = buffer.indexOf("\n\n")) !== -1) {
          const rawEvent = buffer.slice(0, sepIndex);
          buffer = buffer.slice(sepIndex + 2);
          const line = rawEvent.split("\n").find((l) => l.startsWith("data: "));
          if (!line) continue;
          const payload = JSON.parse(line.slice(6));

          if (payload.type === "meta") {
            streamRef.current.total = payload.total || 1;
            if (payload.full_text) setSpokenText(payload.full_text);
          } else if (payload.type === "clip") {
            sawAnyClip = true;
            setIsGenerating(false); // lift the overlay as soon as there's something to watch
            const state = streamRef.current;
            if (state.waitingForNext && payload.index === state.currentIndex + 1) {
              state.currentIndex = payload.index;
              state.waitingForNext = false;
              setIsLastClip(payload.index >= state.total - 1);
              setGeneratedVideoUrl(`${payload.video_url}?t=${Date.now()}`);
            } else {
              clipQueueRef.current.push(payload);
            }
          } else if (payload.type === "error") {
            streamError = payload.detail || "Generation failed.";
          } else if (payload.type === "done") {
            if (!sawAnyClip) setSpokenText(payload.spoken_text || " ");
          }
        }
      }

      if (streamError) throw new Error(streamError);
    } catch (error) {
      console.error("Video Generation Error:", error);
      const displayMsg =
        typeof error === "string"
          ? error
          : error?.message && typeof error.message === "string"
            ? error.message
            : JSON.stringify(error);
      setErrorMessage(displayMsg || "Failed to connect to backend server.");
    } finally {
      setIsGenerating(false);
    }
  };

  const togglePlay = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
      } else {
        videoRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  const handleDownload = () => {
    if (!generatedVideoUrl) return;
    const a = document.createElement("a");
    a.href = generatedVideoUrl;
    a.download = "historical-ai-video.mp4";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  return (
    <div className="bg-background text-on-surface font-body min-h-screen relative overflow-x-hidden">
      <div className="film-grain"></div>

      {serverWarming && (
        <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black/80 backdrop-blur-sm">
          <span className="material-symbols-outlined text-secondary text-5xl animate-spin mb-4">progress_activity</span>
          <p className="text-secondary font-label tracking-widest text-sm uppercase">Setting up models…</p>
          <p className="text-outline text-xs mt-1">{warmupStage}</p>
          <p className="text-outline/70 text-[11px] mt-3">First start only — this won't happen again while the server runs.</p>
        </div>
      )}

      <main className="relative z-10 flex min-h-screen max-w-[1440px] mx-auto px-10 py-12 gap-12 items-start">
        <Sidebar
          clearConversation={clearConversation}
          selectedImage={selectedImage}
          setSelectedImage={setSelectedImage}
          handleImageUpload={handleImageUpload}
          onSelectCharacter={onSelectCharacter}
          activeTab={activeTab}
          setActiveTab={setActiveTab}
          scriptText={scriptText}
          setScriptText={setScriptText}
          audioFile={audioFile}
          setAudioFile={setAudioFile}
          selectedVoice={selectedVoice}
          setSelectedVoice={setSelectedVoice}
          ttsSpeed={ttsSpeed}
          setTtsSpeed={setTtsSpeed}
          ttsEngine={ttsEngine}
          setTtsEngine={setTtsEngine}
          elevenlabsVoiceId={elevenlabsVoiceId}
          setElevenlabsVoiceId={setElevenlabsVoiceId}
          voiceStyle={voiceStyle}
          setVoiceStyle={setVoiceStyle}
          customVoiceRef={customVoiceRef}
          setCustomVoiceRef={setCustomVoiceRef}
          useGemini={useGemini}
          setUseGemini={setUseGemini}
          persona={persona}
          setPersona={setPersona}
          preprocess={preprocess}
          setPreprocess={setPreprocess}
          enhancer={enhancer}
          setEnhancer={setEnhancer}
          still={still}
          setStill={setStill}
          expressionScale={expressionScale}
          setExpressionScale={setExpressionScale}
          fastMode={fastMode}
          setFastMode={setFastMode}
          lipsyncEngine={lipsyncEngine}
          setLipsyncEngine={setLipsyncEngine}
          isGenerateReady={isGenerateReady}
          isGenerating={isGenerating}
          handleGenerate={handleGenerate}
          errorMessage={errorMessage}
        />

        <VideoArea
          selectedImage={selectedImage}
          isGenerating={isGenerating}
          generatedVideoUrl={generatedVideoUrl}
          setGeneratedVideoUrl={setGeneratedVideoUrl}
          isPlaying={isPlaying}
          setIsPlaying={setIsPlaying}
          togglePlay={togglePlay}
          handleDownload={handleDownload}
          videoRef={videoRef}
          spokenText={spokenText}
          idleVideoUrl={idleVideoUrl}
          isIdleGenerating={isIdleGenerating}
          isLastClip={isLastClip}
          onClipEnded={handleClipEnded}
        />
      </main>
    </div>
  );
}

export default App;
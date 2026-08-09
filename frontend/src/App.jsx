import { useState, useRef } from "react";
import Sidebar from "./components/Sidebar/Sidebar";
import VideoArea from "./components/VideoArea/VideoArea";

function App() {
  // STATE CỦA SIDEBAR
  const [scriptText, setScriptText] = useState("");
  const [activeTab, setActiveTab] = useState("TEXT");
  const [selectedImage, setSelectedImage] = useState(null);
  const [audioFile, setAudioFile] = useState(null);
  const [portraitFile, setPortraitFile] = useState(null);
  const [errorMessage, setErrorMessage] = useState("");

  // VIETNEU & GEMINI & SADTALKER STATES
  const [selectedVoice, setSelectedVoice] = useState("Thái Sơn");
  const [useGemini, setUseGemini] = useState(true);
  const [persona, setPersona] = useState("");
  const [fastMode, setFastMode] = useState(true);
  const [lipsyncEngine, setLipsyncEngine] = useState("sadtalker");
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

  const isGenerateReady =
    selectedImage &&
    ((activeTab === "TEXT" && scriptText.trim().length >= 3) ||
      ((activeTab === "AUDIO" || activeTab === "LIVE_MIC") && audioFile !== null));

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
      
      const preprocessRes = await fetch("http://127.0.0.1:8000/preprocess_avatar", {
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
    } catch (error) {
      console.error("Avatar Preprocess Error:", error);
    } finally {
      setIsIdleGenerating(false);
    }
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

      if (activeTab === "TEXT") {
        formData.append("inputType", "text");
        formData.append("text", scriptText);
        formData.append("voice_name", selectedVoice);
        formData.append("use_gemini", "false");
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

      formData.append("preprocess", preprocess);
      formData.append("enhancer", enhancer);
      formData.append("still", still ? "true" : "false");
      formData.append("expression_scale", expressionScale);
      formData.append("lipsync_engine", lipsyncEngine);

      const response = await fetch("http://127.0.0.1:8000/generate", {
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

      const data = await response.json();

      if (data.video_url) {
        const timestamp = new Date().getTime();
        setGeneratedVideoUrl(`${data.video_url}?t=${timestamp}`);
        if (data.spoken_text) {
          setSpokenText(data.spoken_text);
        }
      } else {
        setSpokenText(data.spoken_text || " ");
      }
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

      <main className="relative z-10 flex min-h-screen max-w-[1440px] mx-auto px-10 py-12 gap-12 items-start">
        <Sidebar
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
        />
      </main>
    </div>
  );
}

export default App;
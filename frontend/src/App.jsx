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
  const [useGemini, setUseGemini] = useState(false);
  const [persona, setPersona] = useState("");
  const [preprocess, setPreprocess] = useState("crop");
  const [enhancer, setEnhancer] = useState("gfpgan");
  const [still, setStill] = useState(true);
  const [expressionScale, setExpressionScale] = useState(1.0);
  const [spokenText, setSpokenText] = useState(null);

  // STATE CỦA VIDEO AREA & GENERATION
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedVideoUrl, setGeneratedVideoUrl] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
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

      if (portraitFile) {
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
        formData.append("use_gemini", useGemini ? "true" : "false");
        if (useGemini && persona.trim()) {
          formData.append("persona", persona.trim());
        }
      } else {
        formData.append("inputType", "audio");
        formData.append("audio", targetAudio);
        formData.append("use_gemini", useGemini ? "true" : "false");
        if (useGemini && persona.trim()) {
          formData.append("persona", persona.trim());
        }
      }

      formData.append("preprocess", preprocess);
      formData.append("enhancer", enhancer);
      formData.append("still", still ? "true" : "false");
      formData.append("expression_scale", expressionScale);

      const response = await fetch("http://127.0.0.1:8000/generate", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `Server returned status ${response.status}`);
      }

      const data = await response.json();

      if (data.video_url) {
        const timestamp = new Date().getTime();
        setGeneratedVideoUrl(`${data.video_url}?t=${timestamp}`);
        if (data.spoken_text) {
          setSpokenText(data.spoken_text);
        }
      } else {
        setErrorMessage("Generation completed but no video URL was returned.");
      }
    } catch (error) {
      console.error("Video Generation Error:", error);
      setErrorMessage(error.message || "Failed to connect to backend server.");
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
        />
      </main>
    </div>
  );
}

export default App;
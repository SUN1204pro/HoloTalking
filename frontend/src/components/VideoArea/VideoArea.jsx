import { useState } from "react";
import MainPlayer from "./MainPlayer";
import RecentVideos from "./RecentVideos";

function VideoArea({
  selectedImage, isGenerating, generatedVideoUrl, setGeneratedVideoUrl, isPlaying,
  setIsPlaying, togglePlay, handleDownload, videoRef, spokenText, idleVideoUrl, isIdleGenerating,
  isLastClip, onClipEnded
}) {
  const [targetIp, setTargetIp] = useState("192.168.1.98");
  const [targetPort, setTargetPort] = useState(9999);
  const [isPushing, setIsPushing] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [pushStatus, setPushStatus] = useState(null); // { type: 'success' | 'error', message: string }

  const handleToggleStream = async () => {
    setIsPushing(true);
    setPushStatus(null);
    try {
      if (!isStreaming) {
        const formData = new FormData();
        formData.append("target_ip", targetIp.trim());
        formData.append("port", targetPort);

        const res = await fetch("http://127.0.0.1:8000/api/push_video/start", {
          method: "POST",
          body: formData,
        });

        const data = await res.json();
        if (res.ok) {
          setIsStreaming(true);
          setPushStatus({
            type: "success",
            message: data.message || `Streaming to ${targetIp}:${targetPort}`
          });
        } else {
          throw new Error(data.detail || "Failed to start stream to target IP");
        }
      } else {
        const res = await fetch("http://127.0.0.1:8000/api/push_video/stop", {
          method: "POST",
        });

        const data = await res.json();
        if (res.ok) {
          setIsStreaming(false);
          setPushStatus({
            type: "success",
            message: data.message || "Stopped streaming"
          });
        } else {
          throw new Error(data.detail || "Failed to stop stream");
        }
      }
    } catch (err) {
      setPushStatus({
        type: "error",
        message: err.message || "Connection error. Make sure target device/socket is listening."
      });
    } finally {
      setIsPushing(false);
    }
  };

  return (
    <section className="flex-1 flex flex-col justify-center pl-4 lg:pl-10">
      <div className="w-full max-w-[800px] mx-auto">
        
        {/* Title & Download Button */}
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-label text-secondary text-[11px] tracking-widest flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${isPlaying ? 'bg-emerald-400 animate-ping' : 'bg-secondary'}`} />
            LIVE AVATAR STREAM FEED
          </h2>
          <button 
            onClick={handleDownload} disabled={!generatedVideoUrl}
            className={`border text-[10px] px-4 py-1.5 rounded-lg flex items-center gap-1.5 transition-all ${
              generatedVideoUrl ? 'border-secondary/40 text-secondary hover:bg-secondary hover:text-black bronze-glow cursor-pointer' : 'border-outline-variant/30 text-outline cursor-not-allowed'
            }`}
          >
            <span className="material-symbols-outlined text-sm">download</span> DOWNLOAD
          </button>
        </div>

        <MainPlayer
          selectedImage={selectedImage}
          isGenerating={isGenerating}
          generatedVideoUrl={generatedVideoUrl}
          setGeneratedVideoUrl={setGeneratedVideoUrl}
          isPlaying={isPlaying}
          setIsPlaying={setIsPlaying}
          togglePlay={togglePlay}
          videoRef={videoRef}
          idleVideoUrl={idleVideoUrl}
          isIdleGenerating={isIdleGenerating}
          isLastClip={isLastClip}
          onClipEnded={onClipEnded}
        />

        {/* SOCKET STREAM SENDER CONTROL CARD */}
        <div className="mb-6 p-4 rounded-2xl border border-amber-500/30 bg-black/50 backdrop-blur-md shadow-xl bronze-glow">
          <div className="flex items-center justify-between mb-3 border-b border-white/10 pb-2">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-amber-400 text-lg animate-pulse">
                cell_tower
              </span>
              <div>
                <h3 className="font-label text-xs font-bold text-on-surface tracking-wider uppercase">
                  SOCKET VIDEO SENDER (HOLOFAN / DISPLAY LINK)
                </h3>
                <p className="text-[10px] text-outline">
                  {isStreaming
                    ? "Streaming continuously - freeze frame while generating, talking clip otherwise"
                    : "Start a continuous TCP push stream to target IP"}
                </p>
              </div>
            </div>
            <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
              PORT {targetPort}
            </span>
          </div>

          <div className="flex flex-col sm:flex-row items-center gap-3">
            <div className="flex-1 w-full flex items-center gap-2 bg-black/60 border border-outline-variant/40 rounded-xl px-3 py-1.5">
              <span className="material-symbols-outlined text-outline text-sm">lan</span>
              <span className="text-[10px] font-label text-outline uppercase font-semibold">IP:</span>
              <input
                type="text"
                value={targetIp}
                onChange={(e) => setTargetIp(e.target.value)}
                placeholder="192.168.1.98"
                disabled={isStreaming}
                className="w-full bg-transparent text-xs text-secondary font-mono outline-none disabled:opacity-50"
              />
            </div>

            <div className="w-full sm:w-28 flex items-center gap-2 bg-black/60 border border-outline-variant/40 rounded-xl px-3 py-1.5">
              <span className="text-[10px] font-label text-outline uppercase font-semibold">PORT:</span>
              <input
                type="number"
                value={targetPort}
                onChange={(e) => setTargetPort(parseInt(e.target.value) || 9999)}
                disabled={isStreaming}
                className="w-full bg-transparent text-xs text-secondary font-mono outline-none disabled:opacity-50"
              />
            </div>

            <button
              type="button"
              onClick={handleToggleStream}
              disabled={isPushing}
              className={`w-full sm:w-auto px-5 py-2.5 rounded-xl font-label text-xs font-bold tracking-wider uppercase flex items-center justify-center gap-2 transition-all cursor-pointer shadow-lg border ${
                isPushing
                  ? 'bg-amber-500/20 text-amber-300 border-amber-500/40 cursor-wait'
                  : isStreaming
                    ? 'bg-gradient-to-r from-red-500 via-red-400 to-red-500 text-black border-red-300 hover:brightness-110 hover:scale-105 active:scale-95'
                    : 'bg-gradient-to-r from-amber-500 via-amber-400 to-amber-500 text-black border-amber-300 hover:brightness-110 hover:scale-105 active:scale-95'
              }`}
            >
              <span className="material-symbols-outlined text-sm">
                {isPushing ? "sync" : isStreaming ? "stop" : "play_arrow"}
              </span>
              {isPushing ? (isStreaming ? "STOPPING..." : "STARTING...") : isStreaming ? "STOP" : "START"}
            </button>
          </div>

          {/* STATUS NOTIFICATION BANNER */}
          {pushStatus && (
            <div className={`mt-3 p-2.5 rounded-xl text-xs flex items-center gap-2 font-mono ${
              pushStatus.type === "success" 
                ? "bg-emerald-500/20 border border-emerald-500/40 text-emerald-300" 
                : "bg-red-500/20 border border-red-500/40 text-red-300"
            }`}>
              <span className="material-symbols-outlined text-sm">
                {pushStatus.type === "success" ? "check_circle" : "error"}
              </span>
              <span className="flex-1">{pushStatus.message}</span>
            </div>
          )}
        </div>

        {/* Gemini AI Spoken Transcript Box */}
        {spokenText && (
          <div className="mb-6 p-4 rounded-xl border border-secondary/30 bg-black/40 text-xs leading-relaxed bronze-glow">
            <div className="text-[10px] font-label text-secondary uppercase tracking-wider mb-1 flex items-center gap-1.5">
              <span className="material-symbols-outlined text-sm">auto_awesome</span>
              AI Avatar Response Transcript
              {!isLastClip && (
                <span className="ml-auto normal-case text-outline/80 font-body italic flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                  rendering next line...
                </span>
              )}
            </div>
            <p className="text-on-surface/90 italic">"{spokenText}"</p>
          </div>
        )}
        
        <RecentVideos 
          setGeneratedVideoUrl={setGeneratedVideoUrl} 
          setIsPlaying={setIsPlaying} 
        />

      </div>
    </section>
  );
}

export default VideoArea;
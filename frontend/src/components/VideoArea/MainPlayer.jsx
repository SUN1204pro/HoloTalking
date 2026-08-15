import { useEffect } from "react";

function MainPlayer({
  selectedImage,
  isGenerating,
  generatedVideoUrl,
  setGeneratedVideoUrl,
  isPlaying,
  setIsPlaying,
  togglePlay,
  videoRef,
  idleVideoUrl,
  isIdleGenerating,
  isLastClip = true,
  onClipEnded
}) {
  // Autoplay generated video when ready
  useEffect(() => {
    if (generatedVideoUrl && videoRef.current) {
      videoRef.current.currentTime = 0;
      videoRef.current
        .play()
        .then(() => setIsPlaying(true))
        .catch((e) => console.log("Autoplay handled:", e));
    }
  }, [generatedVideoUrl]);

  return (
    <div className="glass-panel rounded-2xl overflow-hidden aspect-video relative shadow-2xl ring-1 ring-white/10 mb-6 bg-black">
      
      {/* 1. TALKING VIDEO PLAYER */}
      {generatedVideoUrl && (
        <video
          ref={videoRef}
          src={generatedVideoUrl}
          autoPlay
          playsInline
          className="w-full h-full object-contain z-10 relative"
          onPlay={() => setIsPlaying(true)}
          onPause={() => setIsPlaying(false)}
          onEnded={!isLastClip ? onClipEnded : undefined}
        />
      )}

      {/* 2. LIVE AVATAR STANDBY FEED (Display looping idle video or frozen image feed when no talking video) */}
      {!generatedVideoUrl && (
        <div className="absolute inset-0 flex items-center justify-center bg-neutral-950 overflow-hidden z-0">
          {idleVideoUrl ? (
            <video
              src={idleVideoUrl}
              autoPlay
              loop
              muted
              playsInline
              className="w-full h-full object-contain transition-opacity duration-1000 opacity-100"
            />
          ) : selectedImage ? (
            <div className="relative w-full h-full flex items-center justify-center">
              <img 
                src={selectedImage} 
                alt="Live Avatar Standby" 
                className={`w-full h-full object-contain transition-all duration-700 ${
                  isGenerating || isIdleGenerating ? 'scale-105 filter brightness-90 animate-pulse' : 'scale-100'
                }`}
              />
              <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-black/20" />
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center text-center p-6">
              <span className="material-symbols-outlined text-outline/30 text-6xl mb-3">account_circle</span>
              <p className="text-outline text-xs font-label uppercase tracking-widest">
                Select or Upload an Avatar Image to start Live Standby Feed
              </p>
            </div>
          )}
        </div>
      )}

      {/* 3. LIVE STATUS INDICATORS */}
      <div className="absolute top-4 left-4 z-20 flex items-center gap-2">
        {isPlaying ? (
          <span className="px-3 py-1 rounded-full bg-emerald-500/20 border border-emerald-500/40 text-emerald-400 font-mono text-[10px] flex items-center gap-1.5 backdrop-blur-md shadow-lg">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
            LIVE AVATAR TALKING...
          </span>
        ) : isGenerating ? (
          <span className="px-3 py-1 rounded-full bg-amber-500/20 border border-amber-500/40 text-amber-400 font-mono text-[10px] flex items-center gap-1.5 backdrop-blur-md shadow-lg">
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
            LISTENING & PROCESSING RESPONSE...
          </span>
        ) : isIdleGenerating ? (
          <span className="px-3 py-1 rounded-full bg-blue-500/20 border border-blue-500/40 text-blue-400 font-mono text-[10px] flex items-center gap-1.5 backdrop-blur-md shadow-lg">
            <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
            INITIALIZING LIVE AVATAR...
          </span>
        ) : selectedImage ? (
          <span className="px-3 py-1 rounded-full bg-red-500/20 border border-red-500/40 text-red-400 font-mono text-[10px] flex items-center gap-1.5 backdrop-blur-md shadow-lg">
            <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
            LIVE STANDBY - SAY SOMETHING
          </span>
        ) : null}
      </div>

      {/* 4. PROCESSING OVERLAY */}
      {isGenerating && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/60 z-30 backdrop-blur-xs">
          <span className="material-symbols-outlined text-secondary text-5xl animate-spin mb-3">auto_awesome</span>
          <p className="text-secondary font-label tracking-widest text-xs animate-pulse uppercase">
            Synthesizing Talking Avatar...
          </p>
        </div>
      )}

    </div>
  );
}

export default MainPlayer;
import MainPlayer from "./MainPlayer";
import RecentVideos from "./RecentVideos";

function VideoArea({
  selectedImage, isGenerating, generatedVideoUrl, setGeneratedVideoUrl, isPlaying,
  setIsPlaying, togglePlay, handleDownload, videoRef, spokenText, idleVideoUrl, isIdleGenerating
}) {
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
        />

        {/* Gemini AI Spoken Transcript Box */}
        {spokenText && (
          <div className="mb-6 p-4 rounded-xl border border-secondary/30 bg-black/40 text-xs leading-relaxed bronze-glow">
            <div className="text-[10px] font-label text-secondary uppercase tracking-wider mb-1 flex items-center gap-1.5">
              <span className="material-symbols-outlined text-sm">auto_awesome</span>
              AI Avatar Response Transcript
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
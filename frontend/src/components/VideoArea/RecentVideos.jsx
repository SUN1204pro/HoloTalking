import { recentGenerations } from "../../mock/dummyData";

function RecentVideos({ setGeneratedVideoUrl, setIsPlaying }) {
  return (
    <div>
      <h3 className="font-label text-[10px] text-outline mb-3 flex items-center gap-2">
        <span className="w-1.5 h-1.5 rounded-full bg-outline-variant"></span>
        RECENT GENERATIONS
      </h3>
      <div className="grid grid-cols-3 gap-4">
        {recentGenerations.map((vidUrl, idx) => (
          <div 
            key={idx} 
            onClick={() => {
              setGeneratedVideoUrl(vidUrl);
              setIsPlaying(false);
            }}
            className="aspect-video glass-panel rounded-xl relative group cursor-pointer hover:border-primary/50 transition-all overflow-hidden border border-outline-variant/30 bg-black"
          >
            <video src={vidUrl} className="w-full h-full object-cover opacity-50 group-hover:opacity-100 transition-opacity" />
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="material-symbols-outlined text-outline group-hover:text-primary transition-colors text-3xl drop-shadow-md">
                play_circle
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default RecentVideos;
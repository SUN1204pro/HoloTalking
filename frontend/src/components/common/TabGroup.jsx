function TabGroup({ activeTab, setActiveTab }) {
  return (
    <div className="flex gap-4 border-b border-outline-variant/50 pb-2">
      <button
        type="button"
        onClick={() => setActiveTab("TEXT")}
        className={`font-label text-xs transition-all uppercase cursor-pointer ${
          activeTab === "TEXT"
            ? "text-secondary border-b-2 border-secondary font-bold bronze-glow"
            : "text-outline hover:text-on-surface"
        }`}
      >
        📝 Text
      </button>

      <button
        type="button"
        onClick={() => setActiveTab("AUDIO")}
        className={`font-label text-xs transition-all uppercase cursor-pointer ${
          activeTab === "AUDIO"
            ? "text-secondary border-b-2 border-secondary font-bold bronze-glow"
            : "text-outline hover:text-on-surface"
        }`}
      >
        📁 Audio File
      </button>

      <button
        type="button"
        onClick={() => setActiveTab("LIVE_MIC")}
        className={`font-label text-xs transition-all uppercase cursor-pointer flex items-center gap-1 ${
          activeTab === "LIVE_MIC"
            ? "text-secondary border-b-2 border-secondary font-bold bronze-glow"
            : "text-outline hover:text-on-surface"
        }`}
      >
        🎙️ Live Mic
      </button>
    </div>
  );
}

export default TabGroup;
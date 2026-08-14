import { useState } from "react";

function SadTalkerSettings({
  preprocess, setPreprocess,
  enhancer, setEnhancer,
  still, setStill,
  expressionScale, setExpressionScale,
  fastMode, setFastMode,
  lipsyncEngine, setLipsyncEngine
}) {
  const [isOpen, setIsOpen] = useState(false);

  const handleToggleFastMode = (enabled) => {
    setFastMode(enabled);
    if (enabled) {
      setPreprocess("full");
      setEnhancer("none");
      setStill(true);
    } else {
      setPreprocess("full");
      setEnhancer("gfpgan");
      setStill(false);
    }
  };

  return (
    <div className="mt-3 border border-outline-variant/30 bg-black/20 rounded-xl overflow-hidden">
      {/* FAST MODE BANNER TOGGLE */}
      <div className="p-3 bg-gradient-to-r from-amber-500/10 via-black/40 to-black/20 border-b border-outline-variant/20 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-amber-400 text-base animate-pulse">
            bolt
          </span>
          <div>
            <div className="font-label text-[11px] font-bold text-on-surface tracking-wider uppercase flex items-center gap-1.5">
              FAST MODE
              <span className={`px-1.5 py-0.2 text-[9px] rounded font-mono ${fastMode ? 'bg-amber-400/20 text-amber-300 border border-amber-400/40' : 'bg-surface-container-highest text-outline'}`}>
                {fastMode ? "LOW LATENCY (~3s)" : "MAX QUALITY (~10s)"}
              </span>
            </div>
            <p className="text-[10px] text-outline">
              {fastMode ? "Fast generation without GFPGAN polish" : "Full 3D motion & GFPGAN face enhancer"}
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => handleToggleFastMode(!fastMode)}
          className={`relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
            fastMode ? 'bg-amber-400' : 'bg-surface-container-highest'
          }`}
        >
          <span
            className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-black shadow ring-0 transition duration-200 ease-in-out ${
              fastMode ? 'translate-x-4' : 'translate-x-0'
            }`}
          />
        </button>
      </div>

      {/* ADVANCED SETTINGS HEADER */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-3 py-2 flex items-center justify-between font-label text-[10px] text-outline hover:text-secondary transition-colors uppercase cursor-pointer"
      >
        <span className="flex items-center gap-1.5">
          <span className="material-symbols-outlined text-sm">tune</span>
          Advanced Pipeline Controls
        </span>
        <span className="material-symbols-outlined text-sm">
          {isOpen ? "expand_less" : "expand_more"}
        </span>
      </button>

      {isOpen && (
        <div className="p-3 pt-1 border-t border-outline-variant/20 flex flex-col gap-2.5 text-xs">
          {/* LIP-SYNC ENGINE */}
          <div>
            <label className="block text-[10px] text-outline mb-1 font-label">LIP-SYNC ENGINE</label>
            <select
              value={lipsyncEngine}
              onChange={(e) => setLipsyncEngine(e.target.value)}
              className="w-full bg-black/50 border border-amber-500/30 rounded-lg p-1.5 text-xs text-secondary font-medium outline-none"
            >
              <option value="wav2lip">Wav2Lip + SadTalker Head Motion (Overlay Sync)</option>
            </select>
          </div>

          {/* Preprocess */}
          <div>
            <label className="block text-[10px] text-outline mb-1 font-label font-bold text-secondary">
              PREPROCESS MODE
            </label>
            <select
              value={preprocess}
              onChange={(e) => setPreprocess(e.target.value)}
              className="w-full bg-black/50 border border-secondary/40 rounded-lg p-1.5 text-xs text-on-surface outline-none"
            >
              <option value="crop">Crop (Sharp 1:1 Face Zoom - Recommended)</option>
              <option value="full">Full (Paste animated face onto full body)</option>
              <option value="resize">Resize (Force full frame squish)</option>
            </select>
          </div>

          {/* Face Enhancer */}
          <div>
            <label className="block text-[10px] text-outline mb-1 font-label">FACE ENHANCER</label>
            <select
              value={enhancer}
              onChange={(e) => setEnhancer(e.target.value)}
              className="w-full bg-black/50 border border-outline-variant/40 rounded-lg p-1.5 text-xs text-on-surface outline-none"
            >
              <option value="gfpgan">GFPGAN (High Quality Face Polish)</option>
              <option value="none">None (Fastest - Low Latency)</option>
            </select>
          </div>

          {/* Expression Scale */}
          <div>
            <div className="flex justify-between text-[10px] text-outline mb-1 font-label">
              <span>EXPRESSION SCALE</span>
              <span className="text-secondary font-mono">{expressionScale}</span>
            </div>
            <input
              type="range"
              min="0.5"
              max="1.5"
              step="0.1"
              value={expressionScale}
              onChange={(e) => setExpressionScale(parseFloat(e.target.value))}
              className="w-full accent-amber-400 cursor-pointer"
            />
          </div>

          {/* Still Mode */}
          <div className="flex items-center justify-between pt-1">
            <span className="text-[10px] text-outline font-label">STILL MODE (STATIC HEAD)</span>
            <input
              type="checkbox"
              checked={still}
              onChange={(e) => setStill(e.target.checked)}
              className="w-4 h-4 accent-amber-400 cursor-pointer"
            />
          </div>
        </div>
      )}
    </div>
  );
}

export default SadTalkerSettings;


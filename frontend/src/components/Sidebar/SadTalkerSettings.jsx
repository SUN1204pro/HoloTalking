import { useState } from "react";

function SadTalkerSettings({
  preprocess, setPreprocess,
  enhancer, setEnhancer,
  still, setStill,
  expressionScale, setExpressionScale
}) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="mt-3 border border-outline-variant/30 bg-black/20 rounded-xl overflow-hidden">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-3 py-2 flex items-center justify-between font-label text-[10px] text-outline hover:text-secondary transition-colors uppercase cursor-pointer"
      >
        <span className="flex items-center gap-1.5">
          <span className="material-symbols-outlined text-sm">tune</span>
          SadTalker AI Settings
        </span>
        <span className="material-symbols-outlined text-sm">
          {isOpen ? "expand_less" : "expand_more"}
        </span>
      </button>

      {isOpen && (
        <div className="p-3 pt-1 border-t border-outline-variant/20 flex flex-col gap-2.5 text-xs">
          {/* Preprocess */}
          <div>
            <label className="block text-[10px] text-outline mb-1 font-label">PREPROCESS</label>
            <select
              value={preprocess}
              onChange={(e) => setPreprocess(e.target.value)}
              className="w-full bg-black/50 border border-outline-variant/40 rounded-lg p-1.5 text-xs text-on-surface outline-none"
            >
              <option value="crop">Crop (Fast, standard face zoom)</option>
              <option value="resize">Resize (Keep full frame shape)</option>
              <option value="full">Full (Full portrait resolution)</option>
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
              <option value="none">None (Faster processing)</option>
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
            <span className="text-[10px] text-outline font-label">STILL MODE (NO HEAD SHAKE)</span>
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

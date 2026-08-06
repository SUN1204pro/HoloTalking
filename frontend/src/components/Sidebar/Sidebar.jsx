import GlassPanel from "../common/GlassPanel";
import UploadArea from "./UploadArea";
import CharacterList from "./CharacterList";
import InputArea from "./InputArea";
import SadTalkerSettings from "./SadTalkerSettings";

function Sidebar({
  selectedImage, setSelectedImage, handleImageUpload, onSelectCharacter, activeTab, setActiveTab,
  scriptText, setScriptText, audioFile, setAudioFile,
  selectedVoice, setSelectedVoice, useGemini, setUseGemini, persona, setPersona,
  preprocess, setPreprocess, enhancer, setEnhancer, still, setStill,
  expressionScale, setExpressionScale, fastMode, setFastMode,
  lipsyncEngine, setLipsyncEngine,
  isGenerateReady, isGenerating, handleGenerate, errorMessage
}) {
  return (
    <section className="w-[420px] flex-shrink-0">
      <GlassPanel className="h-full p-6 flex flex-col justify-between">
        <div>
          {/* HEADER */}
          <div className="mb-6">
            <h1 className="font-display font-bold text-[30px] leading-[1] tracking-[0.03em] text-secondary bronze-glow">
              AI VIDEO<br />GENERATOR
            </h1>
            <p className="mt-2 font-label text-[9px] tracking-[0.25em] text-outline uppercase">
              Gemini AI • Vietneu TTS • SadTalker Avatar
            </p>
          </div>

          <UploadArea selectedImage={selectedImage} handleImageUpload={handleImageUpload} />
          <CharacterList selectedImage={selectedImage} onSelectCharacter={onSelectCharacter} />
          <InputArea
            activeTab={activeTab} setActiveTab={setActiveTab}
            scriptText={scriptText} setScriptText={setScriptText}
            audioFile={audioFile} setAudioFile={setAudioFile}
            selectedVoice={selectedVoice} setSelectedVoice={setSelectedVoice}
            useGemini={useGemini} setUseGemini={setUseGemini}
            persona={persona} setPersona={setPersona}
            handleGenerate={handleGenerate}
          />
          <SadTalkerSettings
            preprocess={preprocess} setPreprocess={setPreprocess}
            enhancer={enhancer} setEnhancer={setEnhancer}
            still={still} setStill={setStill}
            expressionScale={expressionScale} setExpressionScale={setExpressionScale}
            fastMode={fastMode} setFastMode={setFastMode}
            lipsyncEngine={lipsyncEngine} setLipsyncEngine={setLipsyncEngine}
          />
        </div>

        {/* GENERATE BUTTON & ERROR */}
        <div className="mt-4 pt-3 border-t border-outline-variant/30">
          {errorMessage && (
            <div className="mb-3 rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-400">
              ⚠ {errorMessage}
            </div>
          )}
          <button
            onClick={handleGenerate}
            disabled={!isGenerateReady || isGenerating}
            className={`w-full py-3.5 rounded-xl font-label text-[11px] tracking-[0.2em] transition-all uppercase flex justify-center items-center gap-2 ${isGenerateReady && !isGenerating
                ? "bg-secondary text-black hover:brightness-110 active:scale-[0.98] bronze-glow font-bold cursor-pointer"
                : "bg-surface-container-highest text-outline cursor-not-allowed"
              }`}
          >
            {isGenerating ? (
              <><span className="material-symbols-outlined animate-spin text-sm">autorenew</span>GENERATING VIDEO...</>
            ) : (
              <><span className="material-symbols-outlined text-sm">auto_awesome</span>Generate Video</>
            )}
          </button>
        </div>
      </GlassPanel>
    </section>
  );
}

export default Sidebar;
import { recentCharacters } from "../../mock/dummyData";

function CharacterList({ selectedImage, onSelectCharacter }) {
  return (
    <div className="mb-6">
      <label className="block font-label text-[10px] text-outline mb-2">
        BACKEND AVATAR CHARACTERS
      </label>
      <div className="flex gap-3 overflow-x-auto pb-2 custom-scrollbar">
        {recentCharacters.map((char, idx) => {
          const imgSrc = typeof char === "string" ? char : char.url;
          const charName = typeof char === "string" ? `Char ${idx + 1}` : char.name;
          const isSelected = selectedImage === imgSrc || selectedImage === char?.filename;
          
          return (
            <div 
              key={idx}
              onClick={() => onSelectCharacter(imgSrc, char)}
              className={`flex flex-col items-center cursor-pointer group flex-shrink-0`}
            >
              <img 
                src={imgSrc} 
                alt={charName}
                className={`w-14 h-14 rounded-lg object-cover border-2 transition-all ${
                  isSelected ? 'border-secondary bronze-glow opacity-100' : 'border-outline-variant/50 opacity-70 group-hover:opacity-100 group-hover:border-primary'
                }`}
              />
              <span className={`text-[10px] mt-1 font-body text-center truncate max-w-[64px] ${isSelected ? 'text-secondary font-bold' : 'text-on-surface-variant'}`}>
                {charName}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default CharacterList;
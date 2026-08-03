import { recentCharacters } from "../../mock/dummyData";

function CharacterList({ selectedImage, setSelectedImage }) {
  return (
    <div className="mb-6">
      <label className="block font-label text-[10px] text-outline mb-2">
        RECENT CHARACTERS
      </label>
      <div className="flex gap-3 overflow-x-auto pb-2 custom-scrollbar">
        {recentCharacters.map((src, idx) => (
          <img 
            key={idx} 
            src={src} 
            alt={`Character ${idx}`}
            onClick={() => setSelectedImage(src)} 
            className={`w-14 h-14 rounded-lg object-cover border-2 cursor-pointer transition-all ${
              selectedImage === src ? 'border-secondary bronze-glow' : 'border-outline-variant/50 opacity-60 hover:opacity-100 hover:border-primary'
            }`}
          />
        ))}
      </div>
    </div>
  );
}

export default CharacterList;
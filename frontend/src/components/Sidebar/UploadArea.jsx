function UploadArea({ selectedImage, handleImageUpload }) {
  return (
    <div className="mb-6">
      <label className="block font-label text-[10px] text-outline mb-2">
        SOURCE PORTRAIT
      </label>

      <label
        className={`h-[170px] flex flex-col justify-center items-center border-2 border-dashed rounded-xl cursor-pointer transition-all overflow-hidden relative ${
          selectedImage ? 'border-primary' : 'border-outline-variant/60 hover:border-primary'
        }`}
      >
        <input type="file" accept="image/*" className="hidden" onChange={handleImageUpload} />

        {selectedImage ? (
          <img src={selectedImage} alt="Uploaded portrait" className="absolute inset-0 w-full h-full object-cover" />
        ) : (
          <>
            <span className="material-symbols-outlined text-3xl text-outline">upload_file</span>
            <p className="mt-2 text-sm font-medium text-on-surface">Upload Historical Portrait</p>
            <p className="text-[11px] text-outline mt-1">Click to browse</p>
          </>
        )}
      </label>
    </div>
  );
}

export default UploadArea;
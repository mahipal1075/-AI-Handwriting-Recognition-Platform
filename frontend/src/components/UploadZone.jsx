import React, { useRef } from 'react';
import { Upload, Camera } from 'lucide-react';

const UploadZone = ({ onFileUpload, onCameraOpen }) => {
  const fileInputRef = useRef(null);

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      onFileUpload(e.dataTransfer.files[0]);
    }
  };

  return (
    <div 
      onDragOver={handleDragOver}
      onDrop={handleDrop}
      onClick={() => fileInputRef.current?.click()}
      className="flex-1 min-h-[300px] border-2 border-dashed border-slate-700 hover:border-blue-500/50 bg-slate-900/20 hover:bg-slate-900/40 rounded-xl flex flex-col items-center justify-center p-8 text-center cursor-pointer transition-all duration-300 group shadow-lg"
    >
      <input 
        type="file" 
        ref={fileInputRef} 
        onChange={(e) => onFileUpload(e.target.files[0])}
        className="hidden" 
        accept="image/jpeg,image/png,image/webp,application/pdf"
      />
      <div className="h-16 w-16 rounded-full bg-slate-800/80 group-hover:bg-blue-500/10 flex items-center justify-center mb-4 border border-slate-700/50 group-hover:border-blue-500/20 transition-all duration-300">
        <Upload className="h-8 w-8 text-slate-400 group-hover:text-blue-400 transition-colors" />
      </div>
      <h3 className="font-semibold text-lg text-slate-200 mb-1">
        Upload Handwriting Document
      </h3>
      <p className="text-slate-400 text-sm max-w-xs mb-4">
        Drag and drop files here, or click to browse (JPEG, PNG, WebP, PDF up to 10MB)
      </p>
      <span className="text-slate-500 text-xs">or</span>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onCameraOpen();
        }}
        className="mt-4 px-4 py-2 border border-slate-700 bg-slate-850 hover:bg-slate-800 rounded-lg text-sm text-slate-300 hover:text-white flex items-center gap-1.5 transition-colors cursor-pointer"
      >
        <Camera className="h-4 w-4" />
        Use Camera Snap
      </button>
    </div>
  );
};

export default UploadZone;

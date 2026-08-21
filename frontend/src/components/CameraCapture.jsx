import React, { useRef } from 'react';
import Webcam from 'react-webcam';
import { Camera, X } from 'lucide-react';

const CameraCapture = ({ onCapture, onClose }) => {
  const webcamRef = useRef(null);

  const capturePhoto = () => {
    if (!webcamRef.current) return;
    const imageSrc = webcamRef.current.getScreenshot();
    if (!imageSrc) return;

    // Convert Base64 screenshot to File for upload
    const byteString = atob(imageSrc.split(',')[1]);
    const mimeString = imageSrc.split(',')[0].split(':')[1].split(';')[0];
    
    const ab = new ArrayBuffer(byteString.length);
    const ia = new Uint8Array(ab);
    for (let i = 0; i < byteString.length; i++) {
      ia[i] = byteString.charCodeAt(i);
    }
    
    const blob = new Blob([ab], { type: mimeString });
    const file = new File([blob], `camera-capture-${Date.now()}.jpg`, { type: mimeString });
    
    onCapture(file);
  };

  return (
    <div className="flex-1 min-h-[300px] bg-slate-950 rounded-xl overflow-hidden flex flex-col relative shadow-2xl border border-slate-800">
      <Webcam
        audio={false}
        ref={webcamRef}
        screenshotFormat="image/jpeg"
        videoConstraints={{ facingMode: 'environment' }}
        className="w-full h-full object-cover flex-1"
      />
      
      <div className="absolute top-4 right-4 z-20">
        <button
          onClick={onClose}
          className="p-1.5 bg-slate-900/80 hover:bg-slate-900 rounded-full border border-slate-800 text-slate-400 hover:text-white transition-colors cursor-pointer"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      <div className="p-4 bg-slate-900 border-t border-slate-800 flex justify-center gap-4">
        <button
          onClick={capturePhoto}
          className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-medium text-sm transition-colors flex items-center gap-1.5 cursor-pointer shadow-md shadow-blue-500/10"
        >
          <Camera className="h-4 w-4" />
          Snap Capture
        </button>
        <button
          onClick={onClose}
          className="px-4 py-2.5 border border-slate-700 text-slate-300 hover:text-white rounded-lg text-sm transition-colors cursor-pointer"
        >
          Cancel
        </button>
      </div>
    </div>
  );
};

export default CameraCapture;

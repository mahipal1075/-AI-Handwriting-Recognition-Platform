import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import { logOut } from '../features/auth/authSlice';
import { 
  useUploadDocumentMutation, 
  useProcessDocumentMutation, 
  useGetDocumentResultQuery, 
  useUpdateDocumentResultMutation,
  useExportDocumentMutation
} from '../features/documents/documentApi';

// Import modular subcomponents
import UploadZone from '../components/UploadZone';
import CameraCapture from '../components/CameraCapture';
import OcrEditor from '../components/OcrEditor';

import { 
  Sparkles, LogOut, History, FileText, 
  AlertTriangle, Loader2, Download, FileDown, Eye, Edit3 
} from 'lucide-react';

const Dashboard = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const dispatch = useDispatch();
  const user = useSelector((state) => state.auth.user);

  // States
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [isCameraOpen, setIsCameraOpen] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [editedText, setEditedText] = useState('');
  const [isProcessingLocal, setIsProcessingLocal] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');
  const [uploadError, setUploadError] = useState('');

  // API Mutations
  const [uploadDocument, { isLoading: isUploading }] = useUploadDocumentMutation();
  const [processDocument] = useProcessDocumentMutation();
  const [updateDocumentResult, { isLoading: isSaving }] = useUpdateDocumentResultMutation();
  const [exportDocument, { isLoading: isExporting }] = useExportDocumentMutation();

  // Query Result
  const shouldFetchResult = selectedDoc && selectedDoc.status === 'done';
  const { 
    data: ocrResult, 
    isLoading: isResultLoading,
    refetch: refetchResult 
  } = useGetDocumentResultQuery(selectedDoc?._id, { skip: !shouldFetchResult });

  // Handle document pre-selection from redirect
  useEffect(() => {
    if (location.state?.selectedDocId) {
      setSelectedDoc({
        _id: location.state.selectedDocId,
        status: 'done',
        storagePath: `uploads/document-${location.state.selectedDocId}` 
      });
      // Clear location state
      navigate('/dashboard', { replace: true, state: {} });
    }
  }, [location.state, navigate]);

  // Sync edited text
  useEffect(() => {
    if (ocrResult) {
      setEditedText(ocrResult.extractedText);
    }
  }, [ocrResult]);

  const handleLogout = () => {
    dispatch(logOut());
    navigate('/login');
  };

  // Upload actions
  const handleFileUpload = async (file) => {
    setUploadError('');
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
      setStatusMessage('Uploading document...');
      const doc = await uploadDocument(formData).unwrap();
      setSelectedDoc(doc);
      
      // Start processing immediately
      await runOcrInference(doc._id);
    } catch (err) {
      setUploadError(err?.data?.message || 'File upload failed. Check file type and size.');
      setStatusMessage('');
    }
  };

  const handleCameraCapture = (file) => {
    setIsCameraOpen(false);
    handleFileUpload(file);
  };

  // Process triggers
  const runOcrInference = async (docId) => {
    try {
      setIsProcessingLocal(true);
      setStatusMessage('Binarizing image, detecting text regions...');
      
      await processDocument(docId).unwrap();
      
      setSelectedDoc(prev => ({ ...prev, status: 'done' }));
      setStatusMessage('');
      setIsProcessingLocal(false);
    } catch (err) {
      console.error(err);
      setSelectedDoc(prev => ({ ...prev, status: 'failed' }));
      setUploadError(err?.data?.error || 'OCR processing failed.');
      setStatusMessage('');
      setIsProcessingLocal(false);
    }
  };

  // Save edits
  const handleSaveChanges = async () => {
    if (!selectedDoc) return;
    try {
      await updateDocumentResult({
        id: selectedDoc._id,
        extractedText: editedText
      }).unwrap();
      setEditMode(false);
      if (refetchResult) refetchResult();
    } catch (err) {
      alert('Failed to save changes.');
    }
  };

  // Export action — supports 'txt' and 'pdf'
  const handleExport = async (format = 'txt') => {
    if (!ocrResult) return;
    try {
      const exportRes = await exportDocument({ resultId: ocrResult._id, format }).unwrap();
      const downloadUrl = `http://localhost:5000${exportRes.downloadUrl}`;
      const token = localStorage.getItem('token');
      
      const fileResponse = await fetch(downloadUrl, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      if (!fileResponse.ok) throw new Error('File download failed');
      
      const fileBlob = await fileResponse.blob();
      const tempUrl = window.URL.createObjectURL(fileBlob);
      
      const link = document.createElement('a');
      link.href = tempUrl;
      link.setAttribute('download', exportRes.filename);
      document.body.appendChild(link);
      link.click();
      link.parentNode.removeChild(link);
      window.URL.revokeObjectURL(tempUrl);
    } catch (err) {
      console.error(err);
      alert(`Failed to export as ${format.toUpperCase()}.`);
    }
  };

  const getDocImageUrl = () => {
    if (!selectedDoc) return '';
    if (selectedDoc.storagePath) {
      const relativePath = selectedDoc.storagePath.replace(/\\/g, '/');
      return `http://localhost:5000/${relativePath}`;
    }
    return '';
  };

  return (
    <div className="min-h-screen bg-gradient-to-tr from-slate-950 via-slate-900 to-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Top Header Navbar */}
      <header className="glass-panel border-b border-slate-800/50 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="h-9 w-9 rounded-lg bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center shadow-md shadow-indigo-500/10">
              <Sparkles className="h-5 w-5 text-white" />
            </div>
            <span className="font-bold text-lg bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-300">
              DataLens OCR
            </span>
          </div>

          <div className="flex items-center gap-4">
            <Link 
              to="/history" 
              className="px-3 py-1.5 rounded-lg border border-slate-800 bg-slate-900/30 hover:bg-slate-800/80 text-slate-300 hover:text-white text-sm transition-all flex items-center gap-1.5 cursor-pointer"
            >
              <History className="h-4 w-4" />
              History Log
            </Link>
            
            <span className="text-slate-300 text-sm hidden md:inline">
              Welcome, <strong className="text-white">{user?.fullName || 'User'}</strong>
            </span>

            <button
              onClick={handleLogout}
              className="px-3 py-1.5 rounded-lg border border-slate-800 bg-slate-900/50 hover:bg-red-950/20 hover:border-red-950/30 text-slate-400 hover:text-red-300 text-sm transition-all flex items-center gap-1.5 cursor-pointer"
            >
              <LogOut className="h-4 w-4" />
              Logout
            </button>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-7xl mx-auto px-6 py-8 flex-1 w-full flex flex-col">
        {/* Title area */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white tracking-tight">
            Handwriting Workspace
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Upload document images, snap snapshots from camera, and review smart OCR extractions
          </p>
        </div>

        {uploadError && (
          <div className="bg-red-500/10 border border-red-500/20 text-red-200 px-4 py-3 rounded-lg text-sm mb-6 flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-red-400 shrink-0" />
            {uploadError}
          </div>
        )}

        {/* Core Layout Split */}
        <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-8 items-stretch">
          
          {/* LEFT COLUMN: Upload, Camera & Image Preview */}
          <div className="flex flex-col gap-6">
            {!selectedDoc && !isCameraOpen ? (
              <UploadZone 
                onFileUpload={handleFileUpload} 
                onCameraOpen={() => setIsCameraOpen(true)} 
              />
            ) : isCameraOpen ? (
              <CameraCapture 
                onCapture={handleCameraCapture} 
                onClose={() => setIsCameraOpen(false)} 
              />
            ) : (
              // Image preview panel when document is selected
              <div className="flex-1 min-h-[350px] glass-panel rounded-xl flex flex-col overflow-hidden shadow-xl">
                <div className="px-5 py-4 border-b border-slate-800/60 bg-slate-900/30 flex items-center justify-between">
                  <div className="flex items-center gap-2 truncate">
                    <FileText className="h-5 w-5 text-indigo-400 shrink-0" />
                    <span className="font-semibold text-sm text-slate-200 truncate">
                      {selectedDoc.originalFilename || 'Document Sample'}
                    </span>
                  </div>
                  <button
                    onClick={() => {
                      setSelectedDoc(null);
                      setEditMode(false);
                      setEditedText('');
                    }}
                    className="text-slate-400 hover:text-white text-xs flex items-center gap-1 transition-colors cursor-pointer"
                  >
                    Clear File
                  </button>
                </div>
                <div className="flex-1 bg-slate-950/40 p-6 flex items-center justify-center min-h-[300px]">
                  {selectedDoc.fileType === 'application/pdf' ? (
                    <div className="text-center p-6">
                      <FileText className="h-16 w-16 text-slate-600 mx-auto mb-3" />
                      <span className="text-sm text-slate-400 block font-medium">PDF File Uploaded</span>
                      <span className="text-xs text-slate-500">Preview is only supported for image formats.</span>
                    </div>
                  ) : (
                    <img 
                      src={getDocImageUrl()}
                      alt="Source handwriting"
                      className="max-h-[450px] max-w-full rounded-lg object-contain shadow-md border border-slate-800"
                      onError={(e) => {
                        e.target.src = '';
                        e.target.className = 'hidden';
                      }}
                    />
                  )}
                </div>
              </div>
            )}
          </div>

          {/* RIGHT COLUMN: OCR Transcriber & Highlights Workspace */}
          <div className="flex flex-col">
            <div className="glass-panel rounded-xl flex-1 flex flex-col overflow-hidden shadow-xl border border-slate-800">
              
              {/* Header actions */}
              <div className="px-5 py-4 border-b border-slate-800/60 bg-slate-900/30 flex items-center justify-between shrink-0">
                <span className="font-semibold text-sm text-slate-200">
                  Extracted Transcription
                </span>

                {shouldFetchResult && ocrResult && !isResultLoading && (
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setEditMode(!editMode)}
                      className="px-2.5 py-1 rounded-md border border-slate-800 bg-slate-900/40 hover:bg-slate-850 hover:text-white text-slate-300 text-xs transition-all flex items-center gap-1 cursor-pointer"
                    >
                      {editMode ? (
                        <>
                          <Eye className="h-3.5 w-3.5" />
                          View Highlights
                        </>
                      ) : (
                        <>
                          <Edit3 className="h-3.5 w-3.5" />
                          Edit Text
                        </>
                      )}
                    </button>

                    <button
                      onClick={() => handleExport('txt')}
                      disabled={isExporting}
                      className="px-2.5 py-1 rounded-md bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium transition-colors flex items-center gap-1 cursor-pointer shadow-md shadow-blue-500/10 disabled:opacity-50"
                    >
                      {isExporting ? <Loader2 className="h-3 w-3 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
                      Export TXT
                    </button>

                    <button
                      onClick={() => handleExport('pdf')}
                      disabled={isExporting}
                      className="px-2.5 py-1 rounded-md bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium transition-colors flex items-center gap-1 cursor-pointer shadow-md shadow-indigo-500/10 disabled:opacity-50"
                    >
                      {isExporting ? <Loader2 className="h-3 w-3 animate-spin" /> : <FileDown className="h-3.5 w-3.5" />}
                      Export PDF
                    </button>
                  </div>
                )}
              </div>

              {/* Core Output Container */}
              <div className="flex-1 p-6 overflow-y-auto flex flex-col justify-start min-h-[300px]">
                
                {/* No File Selected State */}
                {!selectedDoc && !isProcessingLocal && (
                  <div className="flex-1 flex flex-col items-center justify-center text-center p-8">
                    <div className="h-12 w-12 rounded-full bg-slate-800/50 flex items-center justify-center mb-3">
                      <FileText className="h-6 w-6 text-slate-500" />
                    </div>
                    <p className="text-slate-400 text-sm max-w-xs">
                      No document active. Upload a handwriting image or snap a photo to run the recognition pipeline.
                    </p>
                  </div>
                )}

                {/* Running CPU Inference State */}
                {((selectedDoc && selectedDoc.status === 'processing') || isProcessingLocal) && (
                  <div className="flex-1 flex flex-col items-center justify-center text-center p-8 gap-4">
                    <Loader2 className="h-10 w-10 text-blue-500 animate-spin" />
                    <div>
                      <p className="text-slate-200 font-semibold">{statusMessage || 'Running HTR pipeline...'}</p>
                      <p className="text-slate-400 text-xs mt-1 max-w-xs mx-auto">
                        Loading TrOCR models on CPU and processing text segments line-by-line. This usually takes 5-15 seconds.
                      </p>
                    </div>
                  </div>
                )}

                {/* Failed Pipeline State */}
                {selectedDoc && selectedDoc.status === 'failed' && !isProcessingLocal && (
                  <div className="flex-1 flex flex-col items-center justify-center text-center p-8">
                    <AlertTriangle className="h-12 w-12 text-red-500 mb-3" />
                    <p className="text-red-200 font-semibold">OCR Processing Failed</p>
                    <p className="text-slate-500 text-sm max-w-xs mt-1">
                      Check that the ML microservice (port 8000) is running locally and has the TrOCR model weights loaded.
                    </p>
                  </div>
                )}

                {/* Completed Output States */}
                {selectedDoc && selectedDoc.status === 'done' && (
                  <OcrEditor 
                    ocrResult={ocrResult}
                    editMode={editMode}
                    editedText={editedText}
                    setEditedText={setEditedText}
                    handleSaveChanges={handleSaveChanges}
                    isSaving={isSaving}
                  />
                )}
              </div>
            </div>
          </div>

        </div>
      </main>
    </div>
  );
};

export default Dashboard;

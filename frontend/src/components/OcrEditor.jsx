import React from 'react';
import { Save, Loader2 } from 'lucide-react';

const OcrEditor = ({
  ocrResult,
  editMode,
  editedText,
  setEditedText,
  handleSaveChanges,
  isSaving
}) => {

  const renderConfidenceHighlights = () => {
    if (!ocrResult) return null;

    // Edited manually -> show raw text
    if (ocrResult.isEdited) {
      return (
        <div className="whitespace-pre-wrap leading-relaxed text-slate-200">
          {ocrResult.extractedText}
        </div>
      );
    }

    // Default highlights
    if (!ocrResult.annotations || ocrResult.annotations.length === 0) {
      return <div className="whitespace-pre-wrap leading-relaxed text-slate-200">{ocrResult.extractedText}</div>;
    }

    return (
      <div className="space-y-4 leading-relaxed text-slate-200">
        {ocrResult.annotations.map((ann, idx) => {
          let styleClass = "px-1 py-0.5 rounded transition-all duration-200 ";
          
          if (ann.highlightColor === 'red') {
            styleClass += "bg-red-500/10 text-red-300 border-b border-dashed border-red-500 cursor-help";
          } else if (ann.highlightColor === 'amber') {
            styleClass += "bg-amber-500/10 text-amber-300 border-b border-dashed border-amber-500 cursor-help";
          } else {
            styleClass += "hover:bg-slate-800";
          }

          return (
            <span 
              key={idx} 
              className={`${styleClass} mr-2 inline-block`}
              title={ann.highlightColor !== 'green' ? `Confidence score below optimal thresholds` : undefined}
            >
              {ann.correctedText}
            </span>
          );
        })}
      </div>
    );
  };

  if (editMode) {
    return (
      <div className="flex-1 flex flex-col h-full">
        <textarea
          value={editedText}
          onChange={(e) => setEditedText(e.target.value)}
          className="flex-1 w-full min-h-[250px] p-4 glass-input rounded-xl text-slate-100 text-sm placeholder-slate-500 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 resize-none font-mono"
          placeholder="Correct recognized handwriting transcript..."
        />
        <div className="mt-4 flex justify-end">
          <button
            onClick={handleSaveChanges}
            disabled={isSaving}
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-1.5 shadow-md shadow-emerald-500/10 cursor-pointer disabled:opacity-50"
          >
            {isSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            Save Corrections
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full justify-between">
      <div className="bg-slate-900/20 p-4 rounded-xl border border-slate-800/40 min-h-[200px]">
        {renderConfidenceHighlights()}
      </div>

      {ocrResult && (
        <div className="mt-6 pt-4 border-t border-slate-800/50 flex flex-wrap gap-x-6 gap-y-2 text-xs text-slate-400 bg-slate-900/10 p-3 rounded-lg">
          <div>
            Accuracy Confidence:{' '}
            <strong className={
              ocrResult.confidence >= 0.95 ? 'text-emerald-400' :
              ocrResult.confidence >= 0.70 ? 'text-amber-400' : 'text-red-400'
            }>
              {(ocrResult.confidence * 100).toFixed(0)}%
            </strong>
          </div>
          <div>
            Engine: <strong className="text-slate-300">{ocrResult.modelUsed}</strong>
          </div>
          <div>
            Inference Time: <strong className="text-slate-300">{ocrResult.processingMs}ms</strong>
          </div>
        </div>
      )}
    </div>
  );
};

export default OcrEditor;

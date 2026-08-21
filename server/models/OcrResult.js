import mongoose from 'mongoose';

const annotationSchema = new mongoose.Schema({
  bboxCoords: {
    x: Number,
    y: Number,
    w: Number,
    h: Number
  },
  correctedText: {
    type: String
  },
  highlightColor: {
    type: String
  }
}, { _id: false });

const ocrResultSchema = new mongoose.Schema({
  documentId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'Document',
    required: true
  },
  extractedText: {
    type: String,
    default: ''
  },
  confidence: {
    type: Number,
    min: 0,
    max: 1,
    default: 1.0
  },
  modelUsed: {
    type: String,
    default: 'trocr-small-handwritten'
  },
  processingMs: {
    type: Number,
    default: 0
  },
  isEdited: {
    type: Boolean,
    default: false
  },
  annotations: [annotationSchema]
}, {
  timestamps: true
});

// Enable text search index on the extractedText field
ocrResultSchema.index({ extractedText: 'text' });

const OcrResult = mongoose.models.OcrResult || mongoose.model('OcrResult', ocrResultSchema);
export default OcrResult;

import express from 'express';
import fs from 'fs';
import path from 'path';
import protect from '../middleware/auth.js';
import upload from '../middleware/upload.js';
import Document from '../models/Document.js';
import OcrResult from '../models/OcrResult.js';

const router = express.Router();

// @desc    Upload a document (image/pdf)
// @route   POST /api/documents/upload
// @access  Private
router.post('/upload', protect, upload.single('file'), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ message: 'No file uploaded' });
    }

    const document = await Document.create({
      userId: req.user.id,
      originalFilename: req.file.originalname,
      fileType: req.file.mimetype,
      storagePath: req.file.path,
      fileSizeBytes: req.file.size,
      status: 'pending'
    });

    res.status(201).json(document);
  } catch (error) {
    console.error('Upload Error:', error);
    res.status(500).json({ message: error.message });
  }
});

// @desc    Trigger OCR process on a document
// @route   POST /api/documents/:id/process
// @access  Private
router.post('/:id/process', protect, async (req, res) => {
  try {
    const document = await Document.findOne({ _id: req.params.id, userId: req.user.id });
    if (!document) {
      return res.status(404).json({ message: 'Document not found' });
    }

    if (document.status === 'processing') {
      return res.status(400).json({ message: 'Document is already being processed' });
    }

    // Update status to processing
    document.status = 'processing';
    await document.save();

    // Perform OCR request to Python FastAPI Service in a background check,
    // but here we wait to complete since it takes only a few seconds.
    const runOcrPipeline = async () => {
      const mlServiceUrl = process.env.ML_SERVICE_URL || 'http://127.0.0.1:8000';
      const mlServiceKey = process.env.ML_SERVICE_KEY || 'handwriting_platform_internal_secret_key';

      try {
        if (!fs.existsSync(document.storagePath)) {
          throw new Error(`File not found on storage: ${document.storagePath}`);
        }

        // Read file into a buffer and create a Blob for native Node.js fetch FormData
        const fileBuffer = fs.readFileSync(document.storagePath);
        const fileBlob = new Blob([fileBuffer], { type: document.fileType });
        
        const formData = new FormData();
        formData.append('file', fileBlob, document.originalFilename);

        console.log(`Sending OCR request for file ${document.originalFilename} to ${mlServiceUrl}/ocr/process`);

        const response = await fetch(`${mlServiceUrl}/ocr/process`, {
          method: 'POST',
          headers: {
            'X-Service-Key': mlServiceKey
          },
          body: formData,
          signal: AbortSignal.timeout(300000) // 5 minutes timeout for ML inference
        });

        if (!response.ok) {
          const errText = await response.text();
          throw new Error(`ML Service returned error status ${response.status}: ${errText}`);
        }

        const data = await response.json();
        
        // Save OCR result in DB
        const ocrResult = await OcrResult.create({
          documentId: document._id,
          extractedText: data.extractedText || '',
          confidence: typeof data.confidence === 'number' ? data.confidence : 1.0,
          modelUsed: data.modelUsed || 'trocr-small-handwritten',
          processingMs: data.processingMs || 0,
          annotations: data.annotations || [],
          isEdited: false
        });

        document.status = 'done';
        await document.save();

        console.log(`OCR complete for document ${document._id}`);
        return ocrResult;
      } catch (error) {
        console.error(`OCR processing failed for document ${document._id}:`, error.message);
        document.status = 'failed';
        await document.save();
        throw error;
      }
    };

    // Run pipeline synchronously for simplicity or handle as async request
    // We run it and return the result to frontend
    try {
      const result = await runOcrPipeline();
      res.json({
        message: 'Processing completed successfully',
        status: 'done',
        result
      });
    } catch (pipelineErr) {
      res.status(500).json({
        message: 'OCR Processing Pipeline Failed',
        status: 'failed',
        error: pipelineErr.message
      });
    }

  } catch (error) {
    console.error('Process Route Error:', error);
    res.status(500).json({ message: error.message });
  }
});

// @desc    Get document status
// @route   GET /api/documents/:id/status
// @access  Private
router.get('/:id/status', protect, async (req, res) => {
  try {
    const document = await Document.findOne({ _id: req.params.id, userId: req.user.id });
    if (!document) {
      return res.status(404).json({ message: 'Document not found' });
    }
    res.json({ status: document.status });
  } catch (error) {
    res.status(500).json({ message: error.message });
  }
});

// @desc    Get OCR result for a document
// @route   GET /api/documents/:id/result
// @access  Private
router.get('/:id/result', protect, async (req, res) => {
  try {
    const document = await Document.findOne({ _id: req.params.id, userId: req.user.id });
    if (!document) {
      return res.status(404).json({ message: 'Document not found' });
    }

    const result = await OcrResult.findOne({ documentId: document._id });
    if (!result) {
      return res.status(404).json({ message: 'OCR Result not found for this document' });
    }

    res.json(result);
  } catch (error) {
    res.status(500).json({ message: error.message });
  }
});

// @desc    Update OCR result text (manual edits)
// @route   PUT /api/documents/:id/result
// @access  Private
router.put('/:id/result', protect, async (req, res) => {
  try {
    const document = await Document.findOne({ _id: req.params.id, userId: req.user.id });
    if (!document) {
      return res.status(404).json({ message: 'Document not found' });
    }

    const result = await OcrResult.findOne({ documentId: document._id });
    if (!result) {
      return res.status(404).json({ message: 'OCR Result not found for this document' });
    }

    const { extractedText, annotations } = req.body;

    if (extractedText !== undefined) {
      result.extractedText = extractedText;
    }
    if (annotations !== undefined) {
      result.annotations = annotations;
    }

    result.isEdited = true;
    await result.save();

    res.json(result);
  } catch (error) {
    res.status(500).json({ message: error.message });
  }
});

export default router;

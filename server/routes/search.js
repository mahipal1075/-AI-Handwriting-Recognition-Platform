import express from 'express';
import protect from '../middleware/auth.js';
import Document from '../models/Document.js';
import OcrResult from '../models/OcrResult.js';

const router = express.Router();

// @desc    Get paginated history of user's documents
// @route   GET /api/history
// @access  Private
router.get('/history', protect, async (req, res) => {
  try {
    const page = parseInt(req.query.page) || 1;
    const limit = parseInt(req.query.limit) || 10;
    const skip = (page - 1) * limit;

    const count = await Document.countDocuments({ userId: req.user.id });
    const documents = await Document.find({ userId: req.user.id })
      .sort({ createdAt: -1 })
      .skip(skip)
      .limit(limit);

    res.json({
      documents,
      page,
      pages: Math.ceil(count / limit),
      totalDocuments: count
    });
  } catch (error) {
    console.error('History Query Error:', error);
    res.status(500).json({ message: error.message });
  }
});

// @desc    Full-text search over recognized OCR text
// @route   GET /api/search
// @access  Private
router.get('/search', protect, async (req, res) => {
  try {
    const { q } = req.query;

    if (!q || q.trim() === '') {
      return res.status(400).json({ message: 'Query parameter q is required' });
    }

    // 1. Text search on OcrResult
    const ocrResults = await OcrResult.find(
      { $text: { $search: q } },
      { score: { $meta: 'textScore' } }
    )
    .sort({ score: { $meta: 'textScore' } })
    .populate('documentId'); // populate document details

    // Filter results to only show the ones belonging to the current user
    const filteredResults = ocrResults.filter(
      (result) => result.documentId && result.documentId.userId.toString() === req.user.id
    );

    res.json(filteredResults);
  } catch (error) {
    console.error('Search Query Error:', error);
    res.status(500).json({ message: error.message });
  }
});

export default router;

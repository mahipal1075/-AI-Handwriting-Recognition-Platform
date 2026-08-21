import mongoose from 'mongoose';

const documentSchema = new mongoose.Schema({
  userId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: 'User',
    required: true
  },
  originalFilename: {
    type: String,
    required: true
  },
  fileType: {
    type: String,
    required: true
  },
  storagePath: {
    type: String,
    required: true
  },
  fileSizeBytes: {
    type: Number,
    required: true
  },
  status: {
    type: String,
    enum: ['pending', 'processing', 'done', 'failed'],
    default: 'pending'
  }
}, {
  timestamps: true
});

const Document = mongoose.models.Document || mongoose.model('Document', documentSchema);
export default Document;

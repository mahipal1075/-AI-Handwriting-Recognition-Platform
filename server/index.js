import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import connectDB from './config/db.js';
import authRoutes from './routes/auth.js';
import documentRoutes from './routes/documents.js';
import searchRoutes from './routes/search.js';
import exportRoutes from './routes/export.js';

// Load environment variables
dotenv.config();

// Connect to MongoDB
connectDB();

const app = express();

// Middleware
app.use(cors({
  origin: 'http://localhost:5173', // frontend Vite server URL
  credentials: true
}));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Serve uploaded images statically
app.use('/uploads', express.static('./uploads'));

// Routes
app.use('/api/auth', authRoutes);
app.use('/api/documents', documentRoutes);
app.use('/api', searchRoutes); // mounts /history and /search directly under /api
app.use('/api/export', exportRoutes);

// Root route — API info
app.get('/', (req, res) => {
  res.json({
    name: 'AI Handwriting Recognition Platform — API',
    version: '2.0.0',
    status: 'UP',
    endpoints: {
      auth:      '/api/auth',
      documents: '/api/documents',
      search:    '/api/search',
      history:   '/api/history',
      export:    '/api/export',
      health:    '/health',
    },
    mlService: 'http://localhost:8000',
    frontend:  'http://localhost:5173',
  });
});

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'UP', service: 'Node.js Express API' });
});

// Error handling middleware
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(500).json({
    message: err.message || 'An unknown error occurred on the server'
  });
});

const PORT = process.env.PORT || 5000;
app.listen(PORT, () => {
  console.log(`Server running in ${process.env.NODE_ENV || 'development'} mode on port ${PORT}`);
});

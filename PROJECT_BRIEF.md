# AI Handwriting Recognition Platform — Project Brief

This is the permanent reference for the AI-Powered Handwriting Recognition and Smart Document Processing Platform.

## Core Services & Port Mapping
- **Frontend App**: `http://localhost:5173` (Vite + React.js + Tailwind CSS)
- **Node Main API**: `http://localhost:5000` (Node.js + Express + Mongoose)
- **ML Service**: `http://localhost:8000` (Python FastAPI + PyTorch + OpenCV)
- **Database**: `mongodb://localhost:27017/handwriting_ocr_db` (Local MongoDB)

## Technologies & Directories
1. **`/frontend`**: React.js, Redux Toolkit, Tailwind CSS, RTK Query, Axios, react-webcam, Vite.
2. **`/server`**: Node.js, Express, Mongoose, JWT (jsonwebtoken), Multer, Bcrypt, express-validator.
3. **`/ml-service`**: Python 3.14, FastAPI, PyTorch (CPU-optimized), HuggingFace Transformers, OpenCV, SymSpell.

## Structural Conventions
- **Frontend**: Functional components, Redux for state management, RTK Query for backend communications.
- **Backend (Node.js)**: MVC-like routing. Models defined using Mongoose schemas. Routes secured with JWT middleware.
- **ML Service**: Python virtual environment (`.venv`). Service key authentication between Node and Python (internal traffic only).

## Database Schemas
- **User**: `email` (unique), `passwordHash`, `fullName`, `role` (user/admin), `isVerified` (default: false).
- **Document**: `userId` (ref User), `originalFilename`, `fileType`, `storagePath`, `fileSizeBytes`, `status` (pending, processing, done, failed).
- **OcrResult**: `documentId` (ref Document), `extractedText` (indexed), `confidence` (float 0-1), `modelUsed`, `processingMs`, `isEdited` (default: false), `annotations` (`[{ bboxCoords, correctedText, highlightColor }]`).

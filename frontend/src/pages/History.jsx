import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useGetHistoryQuery, useSearchDocumentsQuery } from '../features/documents/documentApi';
import { logOut } from '../features/auth/authSlice';
import { useDispatch, useSelector } from 'react-redux';
import { 
  Search, ArrowLeft, Calendar, FileText, ChevronLeft, ChevronRight, 
  Sparkles, LogOut, CheckCircle2, AlertTriangle, Loader2 
} from 'lucide-react';

const History = () => {
  const [page, setPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState('');
  
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const user = useSelector((state) => state.auth.user);

  // Queries
  const { 
    data: historyData, 
    isLoading: historyLoading,
    isFetching: historyFetching,
    error: historyErr 
  } = useGetHistoryQuery({ page, limit: 10 }, { skip: searchQuery.length > 0 });

  const {
    data: searchData,
    isLoading: searchLoading,
    error: searchErr
  } = useSearchDocumentsQuery(searchQuery, { skip: searchQuery.length === 0 });

  const handleLogout = () => {
    dispatch(logOut());
    navigate('/login');
  };

  const handleRowClick = (docId) => {
    // Navigate to dashboard and pre-select this document
    navigate('/dashboard', { state: { selectedDocId: docId } });
  };

  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (dateStr) => {
    return new Date(dateStr).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  // Decide what dataset to show
  const isSearchMode = searchQuery.length > 0;
  const isLoading = isSearchMode ? searchLoading : (historyLoading || historyFetching);
  const error = isSearchMode ? searchErr : historyErr;

  let displayItems = [];
  if (isSearchMode) {
    // Search returns list of OcrResult with documentId populated
    displayItems = (searchData || []).map(r => ({
      _id: r.documentId?._id,
      originalFilename: r.documentId?.originalFilename || 'Unknown',
      fileType: r.documentId?.fileType || 'image',
      fileSizeBytes: r.documentId?.fileSizeBytes || 0,
      status: r.documentId?.status || 'done',
      createdAt: r.documentId?.createdAt || r.createdAt,
      confidence: r.confidence,
      snippet: r.extractedText
    })).filter(item => item._id); // ensure valid documents
  } else {
    displayItems = historyData?.documents || [];
  }

  return (
    <div className="min-h-screen bg-gradient-to-tr from-slate-950 via-slate-900 to-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Top Header Navbar */}
      <header className="glass-panel border-b border-slate-800/50 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link to="/dashboard" className="flex items-center gap-2">
            <div className="h-9 w-9 rounded-lg bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center shadow-md shadow-indigo-500/10">
              <Sparkles className="h-5 w-5 text-white" />
            </div>
            <span className="font-bold text-lg bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-300">
              DataLens OCR
            </span>
          </Link>

          <div className="flex items-center gap-4">
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
        {/* Navigation & Search Area */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
          <div>
            <Link to="/dashboard" className="inline-flex items-center gap-1 text-blue-400 hover:text-blue-300 text-sm mb-2 transition-colors">
              <ArrowLeft className="h-4 w-4" />
              Back to Dashboard
            </Link>
            <h1 className="text-3xl font-bold text-white tracking-tight">
              Transcription History
            </h1>
            <p className="text-slate-400 text-sm mt-1">
              Browse previous documents and perform deep keyword searches across recognized texts
            </p>
          </div>

          {/* Search Box */}
          <div className="relative max-w-md w-full">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500 h-5 w-5" />
            <input
              type="text"
              placeholder="Search recognized text contents..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full glass-input pl-11 pr-4 py-2.5 rounded-xl text-slate-200 text-sm placeholder-slate-500 shadow-md"
            />
          </div>
        </div>

        {/* Results / List Panel */}
        <div className="glass-panel rounded-xl shadow-xl flex-1 flex flex-col overflow-hidden">
          {isLoading ? (
            <div className="flex-1 flex flex-col items-center justify-center py-24 gap-3">
              <Loader2 className="h-10 w-10 text-indigo-500 animate-spin" />
              <p className="text-slate-400 text-sm">Loading historical data...</p>
            </div>
          ) : error ? (
            <div className="flex-1 flex flex-col items-center justify-center py-20 text-center px-6">
              <AlertTriangle className="h-12 w-12 text-red-500 mb-3" />
              <p className="text-red-200 font-medium">Error loading history</p>
              <p className="text-slate-500 text-sm max-w-sm mt-1">{error.message || 'Make sure the server is reachable'}</p>
            </div>
          ) : displayItems.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center py-24 text-center px-6">
              <FileText className="h-16 w-16 text-slate-700 mb-4" />
              <p className="text-slate-300 font-semibold text-lg">No documents found</p>
              <p className="text-slate-500 text-sm max-w-sm mt-1">
                {isSearchMode 
                  ? `No transcripts match "${searchQuery}"`
                  : 'You have not uploaded any handwriting images yet.'
                }
              </p>
              {!isSearchMode && (
                <Link to="/dashboard" className="mt-4 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm transition-colors cursor-pointer shadow-md">
                  Upload First Document
                </Link>
              )}
            </div>
          ) : (
            <div className="flex-1 flex flex-col">
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-slate-800 bg-slate-900/30 text-slate-400 text-xs font-semibold uppercase tracking-wider">
                      <th className="px-6 py-4">Document Details</th>
                      <th className="px-6 py-4">Uploaded At</th>
                      <th className="px-6 py-4">File Size</th>
                      <th className="px-6 py-4">Status</th>
                      {isSearchMode && <th className="px-6 py-4">Accuracy Confidence</th>}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {displayItems.map((item) => (
                      <tr 
                        key={item._id}
                        onClick={() => handleRowClick(item._id)}
                        className="hover:bg-slate-800/30 cursor-pointer transition-colors"
                      >
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-3">
                            <div className="h-10 w-10 bg-slate-800/80 rounded-lg flex items-center justify-center border border-slate-700/50">
                              <FileText className="h-5 w-5 text-indigo-400" />
                            </div>
                            <div>
                              <span className="font-medium text-slate-100 text-sm block max-w-xs md:max-w-md truncate">
                                {item.originalFilename}
                              </span>
                              <span className="text-xs text-slate-400">
                                {item.fileType}
                              </span>
                            </div>
                          </div>
                          {isSearchMode && item.snippet && (
                            <div className="mt-2 text-xs text-slate-400 max-w-xl truncate italic border-l border-slate-700 pl-2">
                              "... {item.snippet} ..."
                            </div>
                          )}
                        </td>
                        <td className="px-6 py-4 text-sm text-slate-300">
                          <div className="flex items-center gap-1.5">
                            <Calendar className="h-4 w-4 text-slate-500" />
                            {formatDate(item.createdAt)}
                          </div>
                        </td>
                        <td className="px-6 py-4 text-sm text-slate-300">
                          {formatBytes(item.fileSizeBytes)}
                        </td>
                        <td className="px-6 py-4 text-sm">
                          {item.status === 'done' ? (
                            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                              <CheckCircle2 className="h-3.5 w-3.5" />
                              Ready
                            </span>
                          ) : item.status === 'failed' ? (
                            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-red-500/10 text-red-400 border border-red-500/20">
                              <AlertTriangle className="h-3.5 w-3.5" />
                              Failed
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20 animate-pulse">
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              Processing
                            </span>
                          )}
                        </td>
                        {isSearchMode && (
                          <td className="px-6 py-4 text-sm font-semibold">
                            <span className={
                              item.confidence >= 0.95 ? 'text-emerald-400' :
                              item.confidence >= 0.70 ? 'text-amber-400' : 'text-red-400'
                            }>
                              {(item.confidence * 100).toFixed(0)}%
                            </span>
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination controls (Only show when not in search mode) */}
              {!isSearchMode && historyData?.pages > 1 && (
                <div className="px-6 py-4 border-t border-slate-800 bg-slate-900/10 flex items-center justify-between">
                  <span className="text-xs text-slate-400">
                    Showing Page <strong>{page}</strong> of <strong>{historyData.pages}</strong> ({historyData.totalDocuments} total documents)
                  </span>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setPage(p => Math.max(p - 1, 1))}
                      disabled={page === 1}
                      className="p-1.5 rounded-lg border border-slate-800 bg-slate-900/40 hover:bg-slate-800 text-slate-400 hover:text-white disabled:opacity-30 disabled:pointer-events-none transition-colors cursor-pointer"
                    >
                      <ChevronLeft className="h-5 w-5" />
                    </button>
                    <button
                      onClick={() => setPage(p => Math.min(p + 1, historyData.pages))}
                      disabled={page === historyData.pages}
                      className="p-1.5 rounded-lg border border-slate-800 bg-slate-900/40 hover:bg-slate-800 text-slate-400 hover:text-white disabled:opacity-30 disabled:pointer-events-none transition-colors cursor-pointer"
                    >
                      <ChevronRight className="h-5 w-5" />
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

export default History;

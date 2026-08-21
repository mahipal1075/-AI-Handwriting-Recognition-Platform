import { apiSlice } from '../api/apiSlice';

export const documentApi = apiSlice.injectEndpoints({
  endpoints: (builder) => ({
    uploadDocument: builder.mutation({
      query: (formData) => ({
        url: '/documents/upload',
        method: 'POST',
        body: formData,
        // Let fetch automatically set multipart/form-data boundary
        formData: true,
      }),
      invalidatesTags: [{ type: 'Document', id: 'LIST' }],
    }),
    processDocument: builder.mutation({
      query: (id) => ({
        url: `/documents/${id}/process`,
        method: 'POST',
      }),
      invalidatesTags: (result, error, id) => [
        { type: 'Document', id },
        { type: 'Document', id: 'LIST' }
      ],
    }),
    getDocumentStatus: builder.query({
      query: (id) => `/documents/${id}/status`,
      providesTags: (result, error, id) => [{ type: 'Document', id }],
    }),
    getDocumentResult: builder.query({
      query: (id) => `/documents/${id}/result`,
      providesTags: (result, error, id) => [{ type: 'Document', id }],
    }),
    updateDocumentResult: builder.mutation({
      query: ({ id, extractedText, annotations }) => ({
        url: `/documents/${id}/result`,
        method: 'PUT',
        body: { extractedText, annotations },
      }),
      invalidatesTags: (result, error, { id }) => [
        { type: 'Document', id },
        { type: 'Document', id: 'LIST' }
      ],
    }),
    getHistory: builder.query({
      query: ({ page = 1, limit = 10 } = {}) => `/history?page=${page}&limit=${limit}`,
      providesTags: (result) =>
        result
          ? [
              ...result.documents.map(({ _id }) => ({ type: 'Document', id: _id })),
              { type: 'Document', id: 'LIST' },
            ]
          : [{ type: 'Document', id: 'LIST' }],
    }),
    searchDocuments: builder.query({
      query: (searchQuery) => `/search?q=${encodeURIComponent(searchQuery)}`,
      providesTags: [{ type: 'Document', id: 'SEARCH' }],
    }),
    exportDocument: builder.mutation({
      query: ({ resultId, format }) => ({
        url: `/export/${resultId}`,
        method: 'POST',
        body: { format },
      }),
    }),
  }),
});

export const {
  useUploadDocumentMutation,
  useProcessDocumentMutation,
  useLazyGetDocumentStatusQuery,
  useGetDocumentResultQuery,
  useUpdateDocumentResultMutation,
  useGetHistoryQuery,
  useSearchDocumentsQuery,
  useExportDocumentMutation,
} = documentApi;

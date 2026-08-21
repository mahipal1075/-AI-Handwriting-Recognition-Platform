import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react';
import { logOut, setCredentials } from '../auth/authSlice';

const baseQuery = fetchBaseQuery({
  baseUrl: 'http://localhost:5000/api',
  prepareHeaders: (headers, { getState }) => {
    const token = getState().auth.token;
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    }
    return headers;
  },
});

const baseQueryWithReauth = async (args, api, extraOptions) => {
  let result = await baseQuery(args, api, extraOptions);

  if (result?.error?.status === 401) {
    console.log('Access token expired. Attempting refresh...');
    
    // Get refresh token from auth state
    const refreshToken = api.getState().auth.refreshToken;

    if (refreshToken) {
      // Try to get a new access token
      const refreshResult = await baseQuery(
        {
          url: '/auth/refresh',
          method: 'POST',
          body: { refreshToken },
        },
        api,
        extraOptions
      );

      if (refreshResult?.data) {
        const newAccessToken = refreshResult.data.accessToken;
        
        // Save the new access token to auth state
        api.dispatch(
          setCredentials({
            token: newAccessToken,
            refreshToken,
            user: api.getState().auth.user,
          })
        );
        
        // Retry the original query with the new token
        result = await baseQuery(args, api, extraOptions);
      } else {
        // Refresh token is invalid/expired -> logout
        console.log('Refresh token expired. Logging out.');
        api.dispatch(logOut());
      }
    } else {
      // No refresh token available -> logout
      api.dispatch(logOut());
    }
  }

  return result;
};

export const apiSlice = createApi({
  baseQuery: baseQueryWithReauth,
  tagTypes: ['Document', 'User'],
  endpoints: (builder) => ({}),
});

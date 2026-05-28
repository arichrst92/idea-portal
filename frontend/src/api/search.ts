/**
 * Global search API client.
 */

import { apiClient } from './client';

export type SearchResultType = 'user' | 'employee' | 'project';

export interface SearchResult {
  type: SearchResultType;
  id: string;
  title: string;
  subtitle: string;
  url: string;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
  total: number;
}

export async function globalSearch(query: string): Promise<SearchResponse> {
  const response = await apiClient.get<SearchResponse>('/api/v1/auth/search', {
    params: { q: query },
  });
  return response.data;
}

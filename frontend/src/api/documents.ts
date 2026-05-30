/**
 * Project Documents API client — TSK-068.
 */

import { apiClient } from './client';

export interface ProjectDocument {
  id: string;
  project_id: string;
  name: string;
  folder_path: string | null;
  file_url: string;
  version: string;
  uploaded_by_user_id: string | null;
  created_at: string;
  updated_at: string;
  uploaded_by_nik: string | null;
  download_url: string | null;
  file_size: number | null;
  content_type: string | null;
}

export interface DocumentDownloadUrl {
  url: string;
  expires_in_seconds: number;
}

export async function listDocuments(
  project_id: string,
  params: { folder_path?: string } = {},
): Promise<ProjectDocument[]> {
  const r = await apiClient.get<ProjectDocument[]>(
    `/api/v1/projects/${project_id}/documents`,
    { params },
  );
  return r.data;
}

export async function listFolders(project_id: string): Promise<string[]> {
  const r = await apiClient.get<string[]>(`/api/v1/projects/${project_id}/document-folders`);
  return r.data;
}

export async function uploadDocument(
  project_id: string,
  file: File,
  metadata: { name: string; folder_path?: string; version?: string },
): Promise<ProjectDocument> {
  const form = new FormData();
  form.append('file', file);
  form.append('name', metadata.name);
  if (metadata.folder_path) form.append('folder_path', metadata.folder_path);
  form.append('version', metadata.version ?? 'v1.0');

  const r = await apiClient.post<ProjectDocument>(
    `/api/v1/projects/${project_id}/documents/upload`,
    form,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  );
  return r.data;
}

export async function getDownloadUrl(
  doc_id: string,
  expires_in: number = 3600,
): Promise<DocumentDownloadUrl> {
  const r = await apiClient.get<DocumentDownloadUrl>(
    `/api/v1/projects/documents/${doc_id}/url`,
    { params: { expires_in } },
  );
  return r.data;
}

export async function listVersions(doc_id: string): Promise<ProjectDocument[]> {
  const r = await apiClient.get<ProjectDocument[]>(
    `/api/v1/projects/documents/${doc_id}/versions`,
  );
  return r.data;
}

export async function deleteDocument(doc_id: string): Promise<void> {
  await apiClient.delete(`/api/v1/projects/documents/${doc_id}`);
}

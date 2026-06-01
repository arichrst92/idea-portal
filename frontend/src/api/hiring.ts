/**
 * Hiring domain API client — TSK-015.
 *
 * Endpoints: /api/v1/job-openings + /api/v1/applications
 */

import { apiClient } from './client';

// ─── Enums (mirror backend) ─────────────────────────────────────

export type JobOpeningStatus =
  | 'DRAFT'
  | 'PENDING_APPROVAL'
  | 'OPEN'
  | 'FILLED'
  | 'CANCELLED'
  | 'CLOSED';

export type ApplicationStage =
  | 'APPLIED'
  | 'SCREENING'
  | 'HR_INTERVIEW'
  | 'USER_INTERVIEW'
  | 'TECHNICAL_TEST'
  | 'OFFERING'
  | 'HIRED'
  | 'REJECTED'
  | 'WITHDRAWN';

export type ApplicationSource =
  | 'REFERRAL'
  | 'LINKEDIN'
  | 'JOBSTREET'
  | 'INDEED'
  | 'KARIR_COM'
  | 'COMPANY_WEBSITE'
  | 'AGENCY'
  | 'WALK_IN'
  | 'OTHER';

// ─── Types ──────────────────────────────────────────────────────

export interface JobOpeningListItem {
  id: string;
  title: string;
  department_name: string | null;
  position_name: string | null;
  status: JobOpeningStatus;
  slots_needed: number;
  slots_filled: number;
  deadline: string | null;
  application_count: number;
  created_at: string;
}

export interface JobOpening {
  id: string;
  title: string;
  description: string | null;
  requirements: string | null;
  department_id: string;
  position_id: string | null;
  slots_needed: number;
  slots_filled: number;
  min_salary: string | null;
  max_salary: string | null;
  currency: string;
  deadline: string | null;
  is_public: boolean;
  status: JobOpeningStatus;
  posted_date: string | null;
  closed_date: string | null;
  requested_by_user_id: string;
  approved_by_user_id: string | null;
  approved_at: string | null;
  rejection_reason: string | null;
  created_at: string;
  updated_at: string;

  department_name: string | null;
  position_name: string | null;
  requested_by_nik: string | null;
  application_count: number;
}

export interface JobOpeningCreateRequest {
  title: string;
  description?: string | null;
  requirements?: string | null;
  department_id: string;
  position_id?: string | null;
  slots_needed?: number;
  min_salary?: string | null;
  max_salary?: string | null;
  currency?: string;
  deadline?: string | null;
  is_public?: boolean;
}

export interface JobOpeningListResponse {
  items: JobOpeningListItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface JobApplication {
  id: string;
  job_opening_id: string;
  candidate_name: string;
  candidate_email: string;
  candidate_phone: string | null;
  resume_url: string | null;
  cover_letter: string | null;
  linkedin_url: string | null;
  source: ApplicationSource;
  referrer_user_id: string | null;
  stage: ApplicationStage;
  stage_changed_at: string | null;
  rejection_reason: string | null;
  rejection_stage: ApplicationStage | null;
  notes: string | null;
  offered_salary: string | null;
  offered_start_date: string | null;
  created_at: string;
  updated_at: string;
  job_title: string | null;
  days_in_stage: number | null;
}

export interface PipelineStageBucket {
  stage: ApplicationStage;
  label: string;
  count: number;
  applications: JobApplication[];
}

export interface PipelineResponse {
  job_opening_id: string;
  job_title: string;
  total_applications: number;
  stages: PipelineStageBucket[];
}

export interface JobApplicationCreateRequest {
  job_opening_id: string;
  candidate_name: string;
  candidate_email: string;
  candidate_phone?: string;
  resume_url?: string;
  cover_letter?: string;
  linkedin_url?: string;
  source?: ApplicationSource;
}

// ─── JobOpening API ─────────────────────────────────────────────

export async function listJobOpenings(
  params: { department_id?: string; status?: JobOpeningStatus; page?: number; page_size?: number } = {},
): Promise<JobOpeningListResponse> {
  const r = await apiClient.get<JobOpeningListResponse>('/api/v1/job-openings', {
    params: {
      department_id: params.department_id || undefined,
      status: params.status || undefined,
      page: params.page ?? 1,
      page_size: params.page_size ?? 25,
    },
  });
  return r.data;
}

export async function getJobOpening(id: string): Promise<JobOpening> {
  const r = await apiClient.get<JobOpening>(`/api/v1/job-openings/${id}`);
  return r.data;
}

export async function createJobOpening(data: JobOpeningCreateRequest): Promise<JobOpening> {
  const r = await apiClient.post<JobOpening>('/api/v1/job-openings', data);
  return r.data;
}

export async function submitJobOpening(id: string): Promise<JobOpening> {
  const r = await apiClient.post<JobOpening>(`/api/v1/job-openings/${id}/submit`);
  return r.data;
}

export async function approveJobOpening(
  id: string,
  approve: boolean,
  rejection_reason?: string,
): Promise<JobOpening> {
  const r = await apiClient.post<JobOpening>(`/api/v1/job-openings/${id}/approve`, {
    approve,
    rejection_reason,
  });
  return r.data;
}

export async function closeJobOpening(id: string): Promise<JobOpening> {
  const r = await apiClient.post<JobOpening>(`/api/v1/job-openings/${id}/close`);
  return r.data;
}

// ─── Pipeline ────────────────────────────────────────────────────

export async function getPipeline(jobOpeningId: string): Promise<PipelineResponse> {
  const r = await apiClient.get<PipelineResponse>(`/api/v1/job-openings/${jobOpeningId}/pipeline`);
  return r.data;
}

// ─── Application API ─────────────────────────────────────────────

export async function createApplication(
  data: JobApplicationCreateRequest,
): Promise<JobApplication> {
  const r = await apiClient.post<JobApplication>('/api/v1/applications', data);
  return r.data;
}

export async function transitionStage(
  appId: string,
  payload: { new_stage: ApplicationStage; notes?: string; rejection_reason?: string },
): Promise<JobApplication> {
  const r = await apiClient.post<JobApplication>(
    `/api/v1/applications/${appId}/transition`,
    payload,
  );
  return r.data;
}

// ─── Helpers ─────────────────────────────────────────────────────

export function jobStatusColor(status: JobOpeningStatus): { className: string; label: string } {
  switch (status) {
    case 'DRAFT':
      return { className: 'ide-tag-gray', label: 'Draft' };
    case 'PENDING_APPROVAL':
      return { className: 'ide-tag-orange', label: 'Pending Approval' };
    case 'OPEN':
      return { className: 'ide-tag-green', label: 'Open' };
    case 'FILLED':
      return { className: 'ide-tag-blue', label: 'Filled' };
    case 'CANCELLED':
      return { className: 'ide-tag-red', label: 'Cancelled' };
    case 'CLOSED':
      return { className: 'ide-tag-gray', label: 'Closed' };
    default:
      return { className: 'ide-tag-gray', label: status };
  }
}

export function stageColor(stage: ApplicationStage): { hex: string; soft: string; label: string } {
  switch (stage) {
    case 'APPLIED':
      return { hex: '#3C3C4360', soft: '#F2F2F7', label: 'Applied' };
    case 'SCREENING':
      return { hex: '#3C3C4399', soft: '#F2F2F7', label: 'Screening' };
    case 'HR_INTERVIEW':
      return { hex: '#007AFF', soft: '#E8F1FF', label: 'HR Interview' };
    case 'USER_INTERVIEW':
      return { hex: '#BF5AF2', soft: '#F5EEFE', label: 'User Interview' };
    case 'TECHNICAL_TEST':
      return { hex: '#FF9F0A', soft: '#FFF3E0', label: 'Technical Test' };
    case 'OFFERING':
      return { hex: '#30D158', soft: '#E5F9EC', label: 'Offering' };
    case 'HIRED':
      return { hex: '#30D158', soft: '#E5F9EC', label: 'Hired' };
    case 'REJECTED':
      return { hex: '#FF453A', soft: '#FFECEB', label: 'Rejected' };
    case 'WITHDRAWN':
      return { hex: '#3C3C4399', soft: '#F2F2F7', label: 'Withdrawn' };
    default:
      return { hex: '#3C3C4360', soft: '#F2F2F7', label: stage };
  }
}

export const SOURCE_OPTIONS: { value: ApplicationSource; label: string }[] = [
  { value: 'REFERRAL', label: 'Referral' },
  { value: 'LINKEDIN', label: 'LinkedIn' },
  { value: 'JOBSTREET', label: 'Jobstreet' },
  { value: 'INDEED', label: 'Indeed' },
  { value: 'KARIR_COM', label: 'Karir.com' },
  { value: 'COMPANY_WEBSITE', label: 'Company Website' },
  { value: 'AGENCY', label: 'Agency' },
  { value: 'WALK_IN', label: 'Walk-in' },
  { value: 'OTHER', label: 'Other' },
];

// ─── TSK-034 Offering Letter workflow ─────────────────────────────

export type OfferStatus =
  | 'DRAFT'
  | 'PENDING_APPROVAL'
  | 'APPROVED'
  | 'SENT'
  | 'ACCEPTED'
  | 'NEGOTIATING'
  | 'REJECTED';

export type CandidateResponse = 'ACCEPTED' | 'NEGOTIATING' | 'REJECTED';

export interface Offer {
  application_id: string;
  offer_status: OfferStatus;
  offer_pdf_url: string | null;
  offer_pdf_generated_at: string | null;
  offered_salary: string | null;
  offered_start_date: string | null;
  offer_submitted_at: string | null;
  offer_approved_at: string | null;
  offer_sent_at: string | null;
  candidate_response: CandidateResponse | null;
  candidate_response_at: string | null;
  salary_override_approved: boolean;
}

export async function generateOfferPdf(applicationId: string): Promise<Offer> {
  const r = await apiClient.post<Offer>(
    `/api/v1/hiring/applications/${applicationId}/offer/generate-pdf`
  );
  return r.data;
}

export async function getOfferPdfUrl(applicationId: string): Promise<{ url: string | null }> {
  const r = await apiClient.get<{ url: string | null }>(
    `/api/v1/hiring/applications/${applicationId}/offer/pdf-url`
  );
  return r.data;
}

export async function submitOfferForApproval(applicationId: string): Promise<Offer> {
  const r = await apiClient.post<Offer>(
    `/api/v1/hiring/applications/${applicationId}/offer/submit-approval`
  );
  return r.data;
}

export async function approveOffer(
  applicationId: string,
  data: { notes?: string | null; salary_override?: boolean }
): Promise<Offer> {
  const r = await apiClient.post<Offer>(
    `/api/v1/hiring/applications/${applicationId}/offer/approve`,
    {
      notes: data.notes ?? null,
      salary_override: data.salary_override ?? false,
    }
  );
  return r.data;
}

export async function rejectOffer(applicationId: string, reason: string): Promise<Offer> {
  const r = await apiClient.post<Offer>(
    `/api/v1/hiring/applications/${applicationId}/offer/reject`,
    { reason }
  );
  return r.data;
}

export async function markOfferSent(applicationId: string): Promise<Offer> {
  const r = await apiClient.post<Offer>(
    `/api/v1/hiring/applications/${applicationId}/offer/mark-sent`
  );
  return r.data;
}

export async function recordCandidateResponse(
  applicationId: string,
  response: CandidateResponse,
  notes?: string | null
): Promise<Offer> {
  const r = await apiClient.post<Offer>(
    `/api/v1/hiring/applications/${applicationId}/offer/candidate-response`,
    { response, notes: notes ?? null }
  );
  return r.data;
}

// Add offer fields to JobApplication interface so frontend can read them via list
export interface ApplicationOfferFields {
  offer_status?: OfferStatus;
  offer_pdf_url?: string | null;
  offer_pdf_generated_at?: string | null;
  offer_approved_at?: string | null;
  offer_sent_at?: string | null;
  candidate_response?: CandidateResponse | null;
  salary_override_approved?: boolean;
}

export const OFFER_STATUS_COLOR: Record<OfferStatus, { label: string; color: string }> = {
  DRAFT: { label: 'Draft', color: 'default' },
  PENDING_APPROVAL: { label: 'Pending Approval', color: 'orange' },
  APPROVED: { label: 'Approved', color: 'blue' },
  SENT: { label: 'Sent to Candidate', color: 'purple' },
  ACCEPTED: { label: 'Accepted ✓', color: 'green' },
  NEGOTIATING: { label: 'Negotiating', color: 'gold' },
  REJECTED: { label: 'Rejected', color: 'red' },
};

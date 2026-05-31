/**
 * Create Job Opening — TSK-015 FE.
 * Form RHF + Zod. Cascading dept → position dropdown.
 */

import { zodResolver } from '@hookform/resolvers/zod';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Alert, Button} from 'antd';
import { message } from '@/lib/notify';
import type { AxiosError } from 'axios';
import { useState } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { useNavigate } from 'react-router-dom';
import { z } from 'zod';

import { createJobOpening, type JobOpeningCreateRequest } from '@/api/hiring';
import { listDepartments, listPositions } from '@/api/organization';

const schema = z.object({
  title: z.string().min(3, 'Minimal 3 karakter').max(200),
  description: z.string().optional().or(z.literal('')),
  requirements: z.string().optional().or(z.literal('')),
  department_id: z.string().min(1, 'Departemen wajib dipilih'),
  position_id: z.string().optional().or(z.literal('')),
  slots_needed: z.coerce.number().int().min(1).max(999),
  min_salary: z.string().optional().or(z.literal('')),
  max_salary: z.string().optional().or(z.literal('')),
  deadline: z.string().optional().or(z.literal('')),
  is_public: z.boolean(),
});

type FormValues = z.infer<typeof schema>;

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '9px 12px',
  border: '1px solid var(--ide-border)',
  borderRadius: 'var(--ide-rs)',
  fontFamily: 'var(--ide-font)',
  fontSize: 13,
  outline: 'none',
  background: 'var(--ide-surface)',
  color: 'var(--ide-ink)',
};

function FieldRow({
  label,
  required,
  error,
  hint,
  children,
}: {
  label: string;
  required?: boolean;
  error?: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div style={{ marginBottom: 14 }}>
      <label
        style={{
          display: 'block',
          fontSize: 12,
          fontWeight: 600,
          color: 'var(--ide-ink2)',
          marginBottom: 6,
        }}
      >
        {label} {required && <span style={{ color: 'var(--ide-red)' }}>*</span>}
      </label>
      {children}
      {hint && (
        <div style={{ fontSize: 11, color: 'var(--ide-ink3)', marginTop: 4 }}>{hint}</div>
      )}
      {error && (
        <div style={{ fontSize: 11, color: 'var(--ide-red)', marginTop: 4, fontWeight: 600 }}>
          {error}
        </div>
      )}
    </div>
  );
}

export default function JobOpeningCreatePage() {
  const navigate = useNavigate();
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    control,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      title: '',
      description: '',
      requirements: '',
      department_id: '',
      position_id: '',
      slots_needed: 1,
      min_salary: '',
      max_salary: '',
      deadline: '',
      is_public: false,
    },
  });

  const selectedDept = watch('department_id');

  const deptQuery = useQuery({ queryKey: ['departments'], queryFn: listDepartments });
  const posQuery = useQuery({
    queryKey: ['positions', selectedDept],
    queryFn: () => listPositions(selectedDept || undefined),
    enabled: !!selectedDept,
  });

  const mutation = useMutation({
    mutationFn: (data: JobOpeningCreateRequest) => createJobOpening(data),
    onSuccess: (data) => {
      message.success(`Lowongan "${data.title}" dibuat sebagai DRAFT`);
      navigate(`/hiring/${data.id}`);
    },
    onError: (err: AxiosError<{ detail?: { code?: string; message?: string } }>) => {
      const detail = err.response?.data?.detail;
      setServerError(detail?.message || 'Gagal create job opening');
    },
  });

  const onSubmit = (values: FormValues) => {
    setServerError(null);
    const payload: JobOpeningCreateRequest = {
      title: values.title.trim(),
      description: values.description?.trim() || null,
      requirements: values.requirements?.trim() || null,
      department_id: values.department_id,
      position_id: values.position_id || null,
      slots_needed: values.slots_needed,
      min_salary: values.min_salary || null,
      max_salary: values.max_salary || null,
      currency: 'IDR',
      deadline: values.deadline || null,
      is_public: values.is_public,
    };
    mutation.mutate(payload);
  };

  return (
    <div className="ide-font" style={{ maxWidth: 760, margin: '0 auto' }}>
      <Button
        type="text"
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate('/hiring')}
        style={{ marginBottom: 14, fontWeight: 600 }}
      >
        Daftar Lowongan
      </Button>

      <div
        style={{
          background: 'var(--ide-surface)',
          border: '1px solid var(--ide-border)',
          borderRadius: 'var(--ide-r)',
          padding: '24px 28px',
        }}
      >
        <h2 style={{ fontSize: 20, fontWeight: 800, letterSpacing: -0.4, marginBottom: 4 }}>
          Tambah Lowongan
        </h2>
        <p style={{ fontSize: 13, color: 'var(--ide-ink2)', marginBottom: 22 }}>
          Lowongan akan dibuat sebagai DRAFT. Submit untuk approval setelah lengkap.
        </p>

        {serverError && (
          <Alert
            type="error"
            message={serverError}
            showIcon
            closable
            onClose={() => setServerError(null)}
            style={{ marginBottom: 16 }}
          />
        )}

        <form onSubmit={handleSubmit(onSubmit)}>
          <FieldRow label="Judul Posisi" required error={errors.title?.message}>
            <Controller
              name="title"
              control={control}
              render={({ field }) => (
                <input {...field} placeholder="Contoh: Senior Backend Engineer" style={inputStyle} />
              )}
            />
          </FieldRow>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            <FieldRow label="Departemen" required error={errors.department_id?.message}>
              <Controller
                name="department_id"
                control={control}
                render={({ field }) => (
                  <select {...field} style={inputStyle}>
                    <option value="">— Pilih dept —</option>
                    {(deptQuery.data || []).map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.code} · {d.name}
                      </option>
                    ))}
                  </select>
                )}
              />
            </FieldRow>
            <FieldRow label="Posisi (opsional)" hint="Bisa kosong kalau posisi baru">
              <Controller
                name="position_id"
                control={control}
                render={({ field }) => (
                  <select {...field} style={inputStyle} disabled={!selectedDept}>
                    <option value="">{selectedDept ? '— Pilih posisi —' : 'Pilih dept dulu'}</option>
                    {(posQuery.data || []).map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.code} · {p.name} (L{p.level})
                      </option>
                    ))}
                  </select>
                )}
              />
            </FieldRow>
          </div>

          <FieldRow label="Deskripsi" hint="Job description (markdown supported)">
            <Controller
              name="description"
              control={control}
              render={({ field }) => (
                <textarea
                  {...field}
                  rows={4}
                  placeholder="Tanggung jawab utama..."
                  style={{ ...inputStyle, resize: 'vertical' }}
                />
              )}
            />
          </FieldRow>

          <FieldRow label="Requirements" hint="Kualifikasi minimal kandidat">
            <Controller
              name="requirements"
              control={control}
              render={({ field }) => (
                <textarea
                  {...field}
                  rows={4}
                  placeholder="- 5+ years experience&#10;- Python, FastAPI&#10;- PostgreSQL"
                  style={{ ...inputStyle, resize: 'vertical' }}
                />
              )}
            />
          </FieldRow>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 14 }}>
            <FieldRow label="Jumlah Slot" required error={errors.slots_needed?.message}>
              <Controller
                name="slots_needed"
                control={control}
                render={({ field }) => (
                  <input
                    {...field}
                    type="number"
                    min={1}
                    max={999}
                    style={inputStyle}
                    onChange={(e) => field.onChange(parseInt(e.target.value, 10) || 1)}
                  />
                )}
              />
            </FieldRow>
            <FieldRow label="Salary Min (IDR)">
              <Controller
                name="min_salary"
                control={control}
                render={({ field }) => (
                  <input
                    {...field}
                    placeholder="18000000"
                    style={{ ...inputStyle, fontFamily: 'var(--ide-font-mono)' }}
                  />
                )}
              />
            </FieldRow>
            <FieldRow label="Salary Max (IDR)">
              <Controller
                name="max_salary"
                control={control}
                render={({ field }) => (
                  <input
                    {...field}
                    placeholder="30000000"
                    style={{ ...inputStyle, fontFamily: 'var(--ide-font-mono)' }}
                  />
                )}
              />
            </FieldRow>
          </div>

          <FieldRow label="Deadline (opsional)" hint="Tanggal terakhir kandidat bisa apply">
            <Controller
              name="deadline"
              control={control}
              render={({ field }) => <input type="date" {...field} style={inputStyle} />}
            />
          </FieldRow>

          <div style={{ marginBottom: 14 }}>
            <Controller
              name="is_public"
              control={control}
              render={({ field }) => (
                <label
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    cursor: 'pointer',
                    fontSize: 12,
                    color: 'var(--ide-ink2)',
                  }}
                >
                  <input
                    type="checkbox"
                    checked={field.value}
                    onChange={(e) => field.onChange(e.target.checked)}
                  />
                  Tampilkan di public career page (setelah approved)
                </label>
              )}
            />
          </div>

          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 22 }}>
            <Button onClick={() => navigate('/hiring')}>Batal</Button>
            <Button
              type="primary"
              htmlType="submit"
              loading={mutation.isPending}
              style={{ background: 'var(--ide-blue)', borderColor: 'var(--ide-blue)' }}
            >
              Simpan sebagai DRAFT
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

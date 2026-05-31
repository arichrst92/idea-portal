/**
 * Employee Create Page — TSK-013 FE Chunk C
 *
 * Form untuk tambah karyawan baru dengan validasi React Hook Form + Zod.
 * Field sesuai EmployeeCreateRequest schema backend.
 *
 * Aturan (knowledge.md):
 * - NIK = login identifier, harus unique (backend validate, 409 kalau duplicate)
 * - Default password = NIK reversed kalau tidak di-set di field initial_password
 * - employee_type: A=internal, B=outsource-IDEA, C=outsource-eksternal
 * - status default PROBATION untuk karyawan baru
 *
 * Dropdown cascade: dept dipilih dulu → position dropdown auto-filter by dept.
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

import {
  createEmployee,
  listDepartments,
  listPositions,
  type EmployeeCreateRequest,
} from '@/api/organization';

const schema = z.object({
  nik: z.string().min(3, 'NIK minimal 3 karakter').max(30, 'NIK maksimal 30 karakter'),
  full_name: z.string().min(1, 'Nama tidak boleh kosong').max(200),
  email: z.string().email('Email tidak valid').optional().or(z.literal('')),
  employee_type: z.enum(['A', 'B', 'C']),
  status: z.enum(['PROBATION', 'ACTIVE', 'ON_LEAVE']).default('PROBATION'),
  department_id: z.string().optional().or(z.literal('')),
  position_id: z.string().optional().or(z.literal('')),
  phone_number: z.string().max(20).optional().or(z.literal('')),
  joined_date: z.string().optional().or(z.literal('')),
  initial_password: z.string().min(8, 'Password min 8 karakter').optional().or(z.literal('')),
});

type FormValues = z.infer<typeof schema>;

function FieldRow({
  label,
  required,
  error,
  children,
}: {
  label: string;
  required?: boolean;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div style={{ marginBottom: 14 }}>
      <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--ide-ink2)', marginBottom: 6 }}>
        {label} {required && <span style={{ color: 'var(--ide-red)' }}>*</span>}
      </label>
      {children}
      {error && (
        <div style={{ fontSize: 11, color: 'var(--ide-red)', marginTop: 4, fontWeight: 600 }}>
          {error}
        </div>
      )}
    </div>
  );
}

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

const selectStyle: React.CSSProperties = {
  ...inputStyle,
  appearance: 'auto',
};

export default function EmployeeCreatePage() {
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
      nik: '',
      full_name: '',
      email: '',
      employee_type: 'A',
      status: 'PROBATION',
      department_id: '',
      position_id: '',
      phone_number: '',
      joined_date: '',
      initial_password: '',
    },
  });

  const selectedDept = watch('department_id');

  const deptQuery = useQuery({ queryKey: ['departments'], queryFn: listDepartments });
  const posQuery = useQuery({
    queryKey: ['positions', selectedDept],
    queryFn: () => listPositions(selectedDept || undefined),
  });

  const mutation = useMutation({
    mutationFn: (data: EmployeeCreateRequest) => createEmployee(data),
    onSuccess: (data) => {
      message.success(`Karyawan ${data.nik} berhasil dibuat`);
      navigate(`/employees/${data.nik}`);
    },
    onError: (err: AxiosError<{ detail?: { code?: string; message?: string } }>) => {
      const detail = err.response?.data?.detail;
      if (detail?.code === 'DUPLICATE_NIK') {
        setServerError(`NIK sudah terdaftar: ${detail.message}`);
      } else if (detail?.code === 'INVALID_FK') {
        setServerError(`Data tidak valid: ${detail.message}`);
      } else {
        setServerError(detail?.message || 'Gagal create employee');
      }
    },
  });

  const onSubmit = (values: FormValues) => {
    setServerError(null);
    // Strip empty strings → null untuk backend
    const payload: EmployeeCreateRequest = {
      nik: values.nik.trim(),
      full_name: values.full_name.trim(),
      email: values.email || null,
      employee_type: values.employee_type,
      status: values.status,
      department_id: values.department_id || null,
      position_id: values.position_id || null,
      phone_number: values.phone_number || null,
      joined_date: values.joined_date || null,
      initial_password: values.initial_password || undefined,
    };
    mutation.mutate(payload);
  };

  return (
    <div className="ide-font" style={{ maxWidth: 720, margin: '0 auto' }}>
      <Button
        type="text"
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate('/employees')}
        style={{ marginBottom: 14, fontWeight: 600 }}
      >
        Daftar Karyawan
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
          Tambah Karyawan
        </h2>
        <p style={{ fontSize: 13, color: 'var(--ide-ink2)', marginBottom: 22 }}>
          NIK akan menjadi identifier login. Password default = NIK reversed jika tidak diisi.
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
          {/* NIK + Email */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            <FieldRow label="NIK" required error={errors.nik?.message}>
              <Controller
                name="nik"
                control={control}
                render={({ field }) => (
                  <input
                    {...field}
                    placeholder="EMP-XXX"
                    style={{ ...inputStyle, fontFamily: 'var(--ide-font-mono)' }}
                  />
                )}
              />
            </FieldRow>
            <FieldRow label="Email" error={errors.email?.message}>
              <Controller
                name="email"
                control={control}
                render={({ field }) => (
                  <input {...field} placeholder="nama@ide.asia" style={inputStyle} />
                )}
              />
            </FieldRow>
          </div>

          <FieldRow label="Nama Lengkap" required error={errors.full_name?.message}>
            <Controller
              name="full_name"
              control={control}
              render={({ field }) => (
                <input {...field} placeholder="Nama lengkap karyawan" style={inputStyle} />
              )}
            />
          </FieldRow>

          {/* Type + Status */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            <FieldRow label="Tipe Karyawan" required error={errors.employee_type?.message}>
              <Controller
                name="employee_type"
                control={control}
                render={({ field }) => (
                  <select {...field} style={selectStyle}>
                    <option value="A">A - Internal IDEA</option>
                    <option value="B">B - Outsource IDEA</option>
                    <option value="C">C - Outsource Eksternal</option>
                  </select>
                )}
              />
            </FieldRow>
            <FieldRow label="Status" required error={errors.status?.message}>
              <Controller
                name="status"
                control={control}
                render={({ field }) => (
                  <select {...field} style={selectStyle}>
                    <option value="PROBATION">Probation</option>
                    <option value="ACTIVE">Active</option>
                    <option value="ON_LEAVE">On Leave</option>
                  </select>
                )}
              />
            </FieldRow>
          </div>

          {/* Department + Position (cascading) */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            <FieldRow label="Departemen" error={errors.department_id?.message}>
              <Controller
                name="department_id"
                control={control}
                render={({ field }) => (
                  <select {...field} style={selectStyle} disabled={deptQuery.isLoading}>
                    <option value="">— Pilih dept —</option>
                    {deptQuery.data?.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.code} · {d.name}
                      </option>
                    ))}
                  </select>
                )}
              />
            </FieldRow>
            <FieldRow label="Posisi" error={errors.position_id?.message}>
              <Controller
                name="position_id"
                control={control}
                render={({ field }) => (
                  <select {...field} style={selectStyle} disabled={!selectedDept || posQuery.isLoading}>
                    <option value="">{selectedDept ? '— Pilih posisi —' : 'Pilih dept dulu'}</option>
                    {posQuery.data?.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.code} · {p.name} (L{p.level})
                      </option>
                    ))}
                  </select>
                )}
              />
            </FieldRow>
          </div>

          {/* Phone + Joined date */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            <FieldRow label="Nomor HP" error={errors.phone_number?.message}>
              <Controller
                name="phone_number"
                control={control}
                render={({ field }) => (
                  <input {...field} placeholder="08xx-xxxx-xxxx" style={inputStyle} />
                )}
              />
            </FieldRow>
            <FieldRow label="Tanggal Bergabung" error={errors.joined_date?.message}>
              <Controller
                name="joined_date"
                control={control}
                render={({ field }) => <input type="date" {...field} style={inputStyle} />}
              />
            </FieldRow>
          </div>

          <FieldRow
            label="Initial Password (opsional, default = NIK reversed)"
            error={errors.initial_password?.message}
          >
            <Controller
              name="initial_password"
              control={control}
              render={({ field }) => (
                <input {...field} type="password" placeholder="Min 8 karakter" style={inputStyle} />
              )}
            />
          </FieldRow>

          {/* Submit */}
          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 22 }}>
            <Button onClick={() => navigate('/employees')}>Batal</Button>
            <Button
              type="primary"
              htmlType="submit"
              loading={mutation.isPending}
              style={{ background: 'var(--ide-blue)', borderColor: 'var(--ide-blue)' }}
            >
              Simpan
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

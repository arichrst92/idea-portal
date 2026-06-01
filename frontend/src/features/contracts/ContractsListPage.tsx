/**
 * Contracts List + Expiring Dashboard — TSK-018.
 */

import {
  AlertOutlined,
  ExclamationCircleFilled,
  PlusOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert, Button, DatePicker, Empty, Form, Input, InputNumber, Modal, Select, Spin} from 'antd';
import { message } from '@/lib/notify';
import dayjs from 'dayjs';
import { useState } from 'react';

import {
  contractStatusBadge,
  contractTypeLabel,
  createContract,
  getExpiringAlerts,
  listContracts,
  renewContract,
  terminateContract,
  type ContractCreateRequest,
  type ContractListItem,
  type ContractType,
} from '@/api/contracts';
import { listEmployees } from '@/api/organization';

const { TextArea } = Input;

function formatDate(value: string | null): string {
  if (!value) return 'open-ended';
  try {
    return new Date(value).toLocaleDateString('id-ID', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    });
  } catch {
    return value;
  }
}

function formatIDR(value: string | null): string {
  if (!value) return '—';
  const n = parseFloat(value);
  if (!isFinite(n)) return value;
  return `Rp ${n.toLocaleString('id-ID')}`;
}

// ─── Create Modal ────────────────────────────────────────────────

function CreateModal({
  open,
  onClose,
  onSuccess,
}: {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [form] = Form.useForm();
  const empQuery = useQuery({
    queryKey: ['employees-for-contract'],
    queryFn: () => listEmployees({ page_size: 200 }),
    enabled: open,
  });

  const mutation = useMutation({
    mutationFn: createContract,
    onSuccess: () => {
      message.success('Contract dibuat');
      form.resetFields();
      onSuccess();
      onClose();
    },
    onError: (err: any) =>
      message.error(err?.response?.data?.detail?.message || 'Gagal create contract'),
  });

  const contractType = Form.useWatch('contract_type', form);

  return (
    <Modal
      title="Create Employment Contract"
      open={open}
      onCancel={onClose}
      footer={[
        <Button key="c" onClick={onClose}>
          Batal
        </Button>,
        <Button
          key="s"
          type="primary"
          loading={mutation.isPending}
          onClick={async () => {
            const v = await form.validateFields();
            const payload: ContractCreateRequest = {
              employee_id: v.employee_id,
              contract_type: v.contract_type,
              start_date: dayjs(v.start_date).format('YYYY-MM-DD'),
              end_date: v.end_date ? dayjs(v.end_date).format('YYYY-MM-DD') : undefined,
              salary: v.salary ? String(v.salary) : undefined,
              document_url: v.document_url,
            };
            mutation.mutate(payload);
          }}
        >
          Create
        </Button>,
      ]}
      destroyOnHidden
      width={560}
    >
      <Form form={form} layout="vertical" initialValues={{ contract_type: 'PKWT' }}>
        <Form.Item
          label="Karyawan"
          name="employee_id"
          rules={[{ required: true, message: 'Pilih karyawan' }]}
        >
          <Select
            placeholder="Cari NIK / nama"
            showSearch
            optionFilterProp="label"
            loading={empQuery.isLoading}
            options={(empQuery.data?.items || []).map((e) => ({
              value: e.id,
              label: `${e.nik} · ${e.full_name} (${e.department_name || 'no dept'})`,
            }))}
          />
        </Form.Item>

        <Form.Item label="Tipe Contract" name="contract_type">
          <Select
            options={[
              { value: 'PKWT', label: 'PKWT (Fixed-term, ada end date)' },
              { value: 'PKWTT', label: 'PKWTT (Permanent, open-ended)' },
            ]}
          />
        </Form.Item>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <Form.Item
            label="Start Date"
            name="start_date"
            rules={[{ required: true, message: 'Wajib diisi' }]}
          >
            <DatePicker style={{ width: '100%' }} format="DD MMM YYYY" />
          </Form.Item>
          <Form.Item
            label={`End Date ${contractType === 'PKWT' ? '(wajib untuk PKWT)' : '(opsional)'}`}
            name="end_date"
            rules={[
              {
                required: contractType === 'PKWT',
                message: 'PKWT wajib punya end date',
              },
            ]}
          >
            <DatePicker style={{ width: '100%' }} format="DD MMM YYYY" />
          </Form.Item>
        </div>

        <Form.Item label="Salary (IDR)" name="salary">
          <InputNumber
            min={0}
            style={{ width: '100%', fontFamily: 'var(--ide-font-mono)' }}
            formatter={(v) => (v ? `Rp ${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, '.') : '')}
            parser={(v) => (v ? Number(v.replace(/[^0-9]/g, '')) : 0)}
          />
        </Form.Item>

        <Form.Item label="Document URL (opsional)" name="document_url">
          <Input placeholder="https://drive.google.com/..." />
        </Form.Item>
      </Form>
    </Modal>
  );
}

// ─── Renew Modal ─────────────────────────────────────────────────

function RenewModal({
  contract,
  open,
  onClose,
  onSuccess,
}: {
  contract: ContractListItem | null;
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [form] = Form.useForm();
  // useWatch HARUS dipanggil sebelum conditional return (Rules of Hooks)
  const newType = Form.useWatch('new_contract_type', form);
  const mutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => renewContract(id, data),
    onSuccess: () => {
      message.success('Contract renewed — new contract created');
      form.resetFields();
      onSuccess();
      onClose();
    },
    onError: (err: any) =>
      message.error(err?.response?.data?.detail?.message || 'Gagal renew'),
  });

  if (!contract) return null;

  return (
    <Modal
      title={`Renew Contract — ${contract.employee_name}`}
      open={open}
      onCancel={onClose}
      footer={[
        <Button key="c" onClick={onClose}>
          Batal
        </Button>,
        <Button
          key="s"
          type="primary"
          loading={mutation.isPending}
          onClick={async () => {
            const v = await form.validateFields();
            mutation.mutate({
              id: contract.id,
              data: {
                new_start_date: dayjs(v.new_start_date).format('YYYY-MM-DD'),
                new_end_date: v.new_end_date
                  ? dayjs(v.new_end_date).format('YYYY-MM-DD')
                  : undefined,
                new_contract_type: v.new_contract_type,
                new_salary: v.new_salary ? String(v.new_salary) : undefined,
                notes: v.notes,
              },
            });
          }}
        >
          Renew
        </Button>,
      ]}
      destroyOnHidden
      width={560}
    >
      <Alert
        type="info"
        message={`Contract lama berakhir ${formatDate(contract.end_date)}. New contract akan auto-set old contract is_active=false.`}
        style={{ marginBottom: 16 }}
      />

      <Form form={form} layout="vertical" initialValues={{ new_contract_type: 'PKWT' }}>
        <Form.Item
          label="New Contract Type"
          name="new_contract_type"
          rules={[{ required: true }]}
        >
          <Select
            options={[
              { value: 'PKWT', label: 'PKWT (Extend fixed-term)' },
              { value: 'PKWTT', label: 'PKWTT (Convert ke permanent)' },
            ]}
          />
        </Form.Item>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <Form.Item
            label="New Start Date"
            name="new_start_date"
            rules={[{ required: true, message: 'Wajib diisi' }]}
          >
            <DatePicker style={{ width: '100%' }} format="DD MMM YYYY" />
          </Form.Item>
          <Form.Item
            label={`New End Date ${newType === 'PKWT' ? '(wajib)' : '(opsional)'}`}
            name="new_end_date"
            rules={[
              {
                required: newType === 'PKWT',
                message: 'PKWT wajib punya end date',
              },
            ]}
          >
            <DatePicker style={{ width: '100%' }} format="DD MMM YYYY" />
          </Form.Item>
        </div>

        <Form.Item label="New Salary (opsional, kalau ada penyesuaian)" name="new_salary">
          <InputNumber
            min={0}
            style={{ width: '100%', fontFamily: 'var(--ide-font-mono)' }}
            formatter={(v) => (v ? `Rp ${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, '.') : '')}
            parser={(v) => (v ? Number(v.replace(/[^0-9]/g, '')) : 0)}
          />
        </Form.Item>

        <Form.Item
          label="Catatan Renewal (min 10 karakter)"
          name="notes"
          rules={[
            { required: true, message: 'Wajib diisi' },
            { min: 10, message: 'Min 10 karakter' },
          ]}
        >
          <TextArea
            rows={3}
            placeholder="Performance excellent, perpanjang 1 tahun + salary increase 10%..."
          />
        </Form.Item>
      </Form>
    </Modal>
  );
}

// ─── Terminate Modal ─────────────────────────────────────────────

function TerminateModal({
  contract,
  open,
  onClose,
  onSuccess,
}: {
  contract: ContractListItem | null;
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [form] = Form.useForm();
  const mutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => terminateContract(id, data),
    onSuccess: () => {
      message.success('Contract terminated');
      form.resetFields();
      onSuccess();
      onClose();
    },
    onError: (err: any) =>
      message.error(err?.response?.data?.detail?.message || 'Gagal terminate'),
  });

  if (!contract) return null;

  return (
    <Modal
      title={`Terminate Contract — ${contract.employee_name}`}
      open={open}
      onCancel={onClose}
      footer={[
        <Button key="c" onClick={onClose}>
          Batal
        </Button>,
        <Button
          key="s"
          type="primary"
          danger
          loading={mutation.isPending}
          onClick={async () => {
            const v = await form.validateFields();
            mutation.mutate({
              id: contract.id,
              data: {
                termination_date: dayjs(v.termination_date).format('YYYY-MM-DD'),
                reason: v.reason,
              },
            });
          }}
        >
          Terminate
        </Button>,
      ]}
      destroyOnHidden
    >
      <Form form={form} layout="vertical">
        <Form.Item
          label="Termination Date"
          name="termination_date"
          rules={[{ required: true, message: 'Wajib diisi' }]}
        >
          <DatePicker style={{ width: '100%' }} format="DD MMM YYYY" />
        </Form.Item>
        <Form.Item
          label="Reason (min 10 karakter)"
          name="reason"
          rules={[
            { required: true, message: 'Wajib diisi' },
            { min: 10, message: 'Min 10 karakter' },
          ]}
        >
          <TextArea rows={3} placeholder="Alasan terminasi contract..." />
        </Form.Item>
      </Form>
    </Modal>
  );
}

// ─── Table Row ───────────────────────────────────────────────────

function ContractRow({
  item,
  onRenew,
  onTerminate,
}: {
  item: ContractListItem;
  onRenew: () => void;
  onTerminate: () => void;
}) {
  const badge = contractStatusBadge(item.derived_status);
  const showAction = item.is_active && item.derived_status !== 'ENDED';

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '2fr 1fr 1.2fr 1.2fr 1fr 1fr',
        gap: 14,
        padding: '14px 20px',
        borderBottom: '1px solid var(--ide-border2)',
        fontSize: 13,
        alignItems: 'center',
      }}
    >
      <div>
        <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--ide-ink)' }}>
          {item.employee_name || '—'}
        </div>
        <div
          style={{
            fontSize: 11,
            color: 'var(--ide-ink3)',
            fontFamily: 'var(--ide-font-mono)',
          }}
        >
          {item.employee_nik} · {item.employee_department || 'No dept'}
        </div>
      </div>
      <div>
        <span
          style={{
            fontSize: 11,
            fontWeight: 600,
            padding: '2px 8px',
            borderRadius: 4,
            background:
              item.contract_type === 'PKWT' ? 'var(--ide-orange-soft)' : 'var(--ide-blue-soft)',
            color:
              item.contract_type === 'PKWT' ? 'var(--ide-orange)' : 'var(--ide-blue)',
          }}
        >
          {item.contract_type}
        </span>
      </div>
      <div style={{ fontSize: 12 }}>
        <div style={{ color: 'var(--ide-ink)' }}>{formatDate(item.start_date)}</div>
        <div style={{ color: 'var(--ide-ink3)', fontSize: 11 }}>
          → {formatDate(item.end_date)}
        </div>
      </div>
      <div>
        <span className={`ide-tag ${badge.className}`}>{badge.label}</span>
        {item.days_until_expiry !== null && item.days_until_expiry >= 0 && item.is_active && (
          <div style={{ fontSize: 10, color: badge.color, marginTop: 4, fontWeight: 600 }}>
            {item.days_until_expiry}d lagi
          </div>
        )}
      </div>
      <div
        style={{
          fontSize: 11,
          color: item.is_active ? 'var(--ide-green)' : 'var(--ide-ink3)',
          fontWeight: 600,
        }}
      >
        {item.is_active ? '● Active' : '○ Inactive'}
      </div>
      <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
        {showAction && (
          <>
            <Button size="small" onClick={onRenew}>
              Renew
            </Button>
            <Button size="small" danger onClick={onTerminate}>
              Terminate
            </Button>
          </>
        )}
      </div>
    </div>
  );
}

// ─── Main Page ───────────────────────────────────────────────────

export default function ContractsListPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState<ContractType | undefined>();
  const [activeFilter, setActiveFilter] = useState<boolean | undefined>(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [renewTarget, setRenewTarget] = useState<ContractListItem | null>(null);
  const [terminateTarget, setTerminateTarget] = useState<ContractListItem | null>(null);

  const alertsQuery = useQuery({
    queryKey: ['contracts-expiring'],
    queryFn: () => getExpiringAlerts(30),
  });

  // TSK-199 AC-07 — dashboard widget contracts expiring 60 days
  const alerts60Query = useQuery({
    queryKey: ['contracts-expiring-60'],
    queryFn: () => getExpiringAlerts(60),
  });

  const listQuery = useQuery({
    queryKey: ['contracts', typeFilter, activeFilter],
    queryFn: () =>
      listContracts({
        contract_type: typeFilter,
        is_active: activeFilter,
        page_size: 200,
      }),
  });

  const items = listQuery.data?.items || [];
  const filtered = search
    ? items.filter(
        (c) =>
          (c.employee_name || '').toLowerCase().includes(search.toLowerCase()) ||
          (c.employee_nik || '').toLowerCase().includes(search.toLowerCase()),
      )
    : items;

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['contracts'] });
    queryClient.invalidateQueries({ queryKey: ['contracts-expiring'] });
  };

  return (
    <div className="ide-font" style={{ maxWidth: 1400, margin: '0 auto' }}>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          marginBottom: 18,
          gap: 12,
          flexWrap: 'wrap',
        }}
      >
        <div>
          <h2 style={{ fontSize: 22, fontWeight: 800, letterSpacing: -0.5, marginBottom: 4 }}>
            Employment Contracts
          </h2>
          <p style={{ fontSize: 13, color: 'var(--ide-ink2)' }}>
            PKWT/PKWTT management dengan H-30/H-7 alert + renewal flow.
          </p>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setCreateOpen(true)}
          style={{ background: 'var(--ide-blue)', borderColor: 'var(--ide-blue)', fontWeight: 600 }}
        >
          Create Contract
        </Button>
      </div>

      {/* Expiring Alert Banner */}
      {alertsQuery.data && (alertsQuery.data.total_h7 > 0 || alertsQuery.data.total_expired_unrenewed > 0) && (
        <Alert
          type="error"
          showIcon
          icon={<ExclamationCircleFilled />}
          message={
            <strong>
              ⚠ CRITICAL: {alertsQuery.data.total_h7} contract(s) expiring dalam 7 hari +{' '}
              {alertsQuery.data.total_expired_unrenewed} expired tanpa renewal
            </strong>
          }
          style={{ marginBottom: 14 }}
        />
      )}

      {/* KPIs — TSK-199 AC-07 widget */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(5, 1fr)',
          gap: 12,
          marginBottom: 18,
        }}
      >
        <div className="ide-kpi">
          <div className="ide-kpi-val">{items.filter((c) => c.is_active).length}</div>
          <div className="ide-kpi-lbl">Active Contracts</div>
        </div>
        <div className="ide-kpi">
          <div
            className="ide-kpi-val"
            style={{ color: 'var(--ide-blue, #0071E3)' }}
          >
            {(alerts60Query.data?.total_h30 ?? 0) -
              (alertsQuery.data?.total_h30 ?? 0) +
              (alerts60Query.data?.total_h7 ?? 0) -
              (alertsQuery.data?.total_h7 ?? 0)}
          </div>
          <div className="ide-kpi-lbl">H-60 (31-60 hari)</div>
        </div>
        <div className="ide-kpi">
          <div
            className="ide-kpi-val"
            style={{ color: 'var(--ide-orange)' }}
          >
            {alertsQuery.data?.total_h30 || 0}
          </div>
          <div className="ide-kpi-lbl">H-30 (8-30 hari)</div>
        </div>
        <div className="ide-kpi">
          <div
            className="ide-kpi-val"
            style={{ color: 'var(--ide-red)' }}
          >
            {alertsQuery.data?.total_h7 || 0}
          </div>
          <div className="ide-kpi-lbl">CRITICAL H-7</div>
        </div>
        <div className="ide-kpi">
          <div
            className="ide-kpi-val"
            style={{ color: 'var(--ide-red)' }}
          >
            {alertsQuery.data?.total_expired_unrenewed || 0}
          </div>
          <div className="ide-kpi-lbl">Expired (no renewal)</div>
        </div>
      </div>

      {/* Toolbar */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 14, flexWrap: 'wrap' }}>
        <Input
          prefix={<SearchOutlined style={{ color: 'var(--ide-ink3)' }} />}
          placeholder="Cari NIK / nama..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ width: 280 }}
          allowClear
        />
        <Select
          placeholder="Semua Tipe"
          style={{ width: 200 }}
          allowClear
          value={typeFilter}
          onChange={(v) => setTypeFilter(v as ContractType)}
          options={[
            { value: 'PKWT', label: 'PKWT' },
            { value: 'PKWTT', label: 'PKWTT' },
          ]}
        />
        <Select
          placeholder="Active/All"
          style={{ width: 160 }}
          value={activeFilter}
          onChange={(v) => setActiveFilter(v)}
          options={[
            { value: true, label: 'Active only' },
            { value: false, label: 'Inactive only' },
            { value: undefined, label: 'All' },
          ]}
        />
      </div>

      {/* Table */}
      <div
        style={{
          background: 'var(--ide-surface)',
          border: '1px solid var(--ide-border)',
          borderRadius: 'var(--ide-r)',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '2fr 1fr 1.2fr 1.2fr 1fr 1fr',
            gap: 14,
            padding: '12px 20px',
            background: 'var(--ide-bg)',
            borderBottom: '1px solid var(--ide-border)',
            fontSize: 10,
            fontWeight: 700,
            color: 'var(--ide-ink3)',
            textTransform: 'uppercase',
            letterSpacing: '0.8px',
          }}
        >
          <div>Karyawan</div>
          <div>Type</div>
          <div>Period</div>
          <div>Status</div>
          <div>Active</div>
          <div style={{ textAlign: 'right' }}>Actions</div>
        </div>

        {listQuery.isLoading && (
          <div style={{ padding: 40, textAlign: 'center' }}>
            <Spin />
          </div>
        )}

        {listQuery.data && filtered.length === 0 && (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={
              <span style={{ color: 'var(--ide-ink2)' }}>
                {search ? `Tidak ada match "${search}"` : 'Belum ada contract'}
              </span>
            }
            style={{ padding: '40px 20px' }}
          />
        )}

        {filtered.map((c) => (
          <ContractRow
            key={c.id}
            item={c}
            onRenew={() => setRenewTarget(c)}
            onTerminate={() => setTerminateTarget(c)}
          />
        ))}
      </div>

      {/* Modals */}
      <CreateModal open={createOpen} onClose={() => setCreateOpen(false)} onSuccess={refresh} />
      <RenewModal
        contract={renewTarget}
        open={renewTarget !== null}
        onClose={() => setRenewTarget(null)}
        onSuccess={refresh}
      />
      <TerminateModal
        contract={terminateTarget}
        open={terminateTarget !== null}
        onClose={() => setTerminateTarget(null)}
        onSuccess={refresh}
      />
    </div>
  );
}

/**
 * Finance Page — TSK-023 + TSK-022D.
 * Tabs: Invoices (AR), Reimbursement, Procurement, Vendor.
 */

import InvoicesTab from './InvoicesTab';

import { CheckOutlined, CloseOutlined, PlusOutlined, SendOutlined, StopOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert, Button, DatePicker, Empty, Form, Input, InputNumber, Modal, Select, Spin, Tabs, Tag} from 'antd';
import { message, modal } from '@/lib/notify';
import dayjs from 'dayjs';
import { useState } from 'react';

import {
  approveProcL1,
  approveProcL2,
  approveReimbL1,
  approveReimbL2,
  cancelReimb,
  createProcurement,
  createReimbursement,
  createVendor,
  deliverProc,
  listProcurements,
  listReimbursements,
  listVendors,
  orderProc,
  procStatusColor,
  PROC_CATEGORIES,
  reimbStatusColor,
  REIMB_CATEGORIES,
  rejectProc,
  rejectReimb,
  transferReimb,
  type ProcurementListItem,
  type ProcStatus,
  type ReimbStatus,
  type ReimbursementListItem,
} from '@/api/finance';
import { listEmployees } from '@/api/organization';
import { useAuthStore } from '@/store/auth';

const { TextArea } = Input;

function formatDate(value: string | null): string {
  if (!value) return '—';
  return new Date(value).toLocaleDateString('id-ID', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

function formatIDR(value: string | null): string {
  if (!value) return '—';
  const n = parseFloat(value);
  if (!isFinite(n)) return value;
  return `Rp ${n.toLocaleString('id-ID')}`;
}

// ─── REIMBURSEMENT TAB ──────────────────────────────────────────

function ReimbursementTab() {
  const queryClient = useQueryClient();
  const user = useAuthStore((s) => s.user);
  const [statusFilter, setStatusFilter] = useState<ReimbStatus | undefined>();
  const [createOpen, setCreateOpen] = useState(false);

  const isApprover =
    user?.roles.some((r) =>
      ['DIREKTUR_UTAMA', 'WAKIL_DIREKTUR_UTAMA', 'C_LEVEL', 'GM', 'MANAGER'].includes(r.code),
    ) ?? false;

  const query = useQuery({
    queryKey: ['reimbursements', statusFilter],
    queryFn: () => listReimbursements({ status: statusFilter, page_size: 100 }),
  });

  const items = query.data?.items || [];
  const pending = items.filter((r) => r.status === 'PENDING_L1' || r.status === 'PENDING_L2').length;
  const approved = items.filter((r) => r.status === 'APPROVED').length;
  const transferred = items.filter((r) => r.status === 'TRANSFERRED').length;
  const totalAmount = items.reduce((acc, r) => acc + parseFloat(r.amount), 0);

  return (
    <div>
      <div style={{ display: 'flex', gap: 10, marginBottom: 14, flexWrap: 'wrap' }}>
        <Select
          placeholder="All Status"
          style={{ width: 220 }}
          allowClear
          value={statusFilter}
          onChange={(v) => setStatusFilter(v as ReimbStatus)}
          options={[
            { value: 'PENDING_L1', label: 'Pending L1' },
            { value: 'PENDING_L2', label: 'Pending L2' },
            { value: 'APPROVED', label: 'Approved (siap transfer)' },
            { value: 'TRANSFERRED', label: 'Transferred' },
            { value: 'REJECTED', label: 'Rejected' },
            { value: 'CANCELLED', label: 'Cancelled' },
          ]}
        />
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setCreateOpen(true)}
          style={{ background: 'var(--ide-blue)', borderColor: 'var(--ide-blue)' }}
        >
          Submit Reimbursement
        </Button>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 12,
          marginBottom: 18,
        }}
      >
        <div className="ide-kpi">
          <div className="ide-kpi-val">{items.length}</div>
          <div className="ide-kpi-lbl">Total Requests</div>
        </div>
        <div className="ide-kpi">
          <div className="ide-kpi-val" style={{ color: 'var(--ide-orange)' }}>
            {pending}
          </div>
          <div className="ide-kpi-lbl">Pending Approval</div>
        </div>
        <div className="ide-kpi">
          <div className="ide-kpi-val" style={{ color: 'var(--ide-blue)' }}>
            {approved}
          </div>
          <div className="ide-kpi-lbl">Approved (siap transfer)</div>
        </div>
        <div className="ide-kpi">
          <div className="ide-kpi-val" style={{ fontSize: 16 }}>
            Rp {(totalAmount / 1_000_000).toFixed(1)}M
          </div>
          <div className="ide-kpi-lbl">Total Amount ({transferred} transferred)</div>
        </div>
      </div>

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
            gridTemplateColumns: '1.4fr 1fr 0.8fr 0.8fr 1fr 1.6fr',
            gap: 12,
            padding: '12px 20px',
            background: 'var(--ide-bg)',
            borderBottom: '1px solid var(--ide-border)',
            fontSize: 10,
            fontWeight: 700,
            color: 'var(--ide-ink3)',
            textTransform: 'uppercase',
          }}
        >
          <div>Karyawan</div>
          <div>Category</div>
          <div>Date</div>
          <div style={{ textAlign: 'right' }}>Amount</div>
          <div>Status</div>
          <div style={{ textAlign: 'right' }}>Actions</div>
        </div>

        {query.isLoading && <Spin style={{ display: 'block', margin: 40 }} />}
        {query.data && items.length === 0 && <Empty style={{ padding: 40 }} />}

        {items.map((r) => (
          <ReimbRow key={r.id} r={r} onAction={() => queryClient.invalidateQueries({ queryKey: ['reimbursements'] })} isApprover={isApprover} />
        ))}
      </div>

      <CreateReimbModal open={createOpen} onClose={() => setCreateOpen(false)} onSuccess={() => queryClient.invalidateQueries({ queryKey: ['reimbursements'] })} />
    </div>
  );
}

function ReimbRow({ r, onAction, isApprover }: { r: ReimbursementListItem; onAction: () => void; isApprover: boolean }) {
  const badge = reimbStatusColor(r.status);

  const approveL1Mut = useMutation({
    mutationFn: () => approveReimbL1(r.id),
    onSuccess: () => { message.success('Approved L1'); onAction(); },
    onError: (e: any) => message.error(e?.response?.data?.detail?.message || 'Gagal'),
  });
  const approveL2Mut = useMutation({
    mutationFn: () => approveReimbL2(r.id),
    onSuccess: () => { message.success('Approved L2 (siap transfer)'); onAction(); },
    onError: (e: any) => message.error(e?.response?.data?.detail?.message || 'Gagal'),
  });
  const cancelMut = useMutation({
    mutationFn: () => cancelReimb(r.id),
    onSuccess: () => { message.success('Cancelled'); onAction(); },
  });

  const handleReject = () => {
    modal.confirm({
      title: 'Reject Reimbursement',
      content: <Form layout="vertical"><Form.Item label="Alasan (min 10 char)"><TextArea id={`rej-${r.id}`} rows={3} /></Form.Item></Form>,
      okText: 'Reject',
      okType: 'danger',
      onOk: async () => {
        const el = document.getElementById(`rej-${r.id}`) as HTMLTextAreaElement;
        if (!el?.value || el.value.length < 10) {
          message.warning('Min 10 karakter');
          return Promise.reject();
        }
        await rejectReimb(r.id, el.value);
        message.success('Rejected');
        onAction();
      },
    });
  };

  const handleTransfer = () => {
    modal.confirm({
      title: 'Mark as Transferred',
      content: <Form layout="vertical"><Form.Item label="Transfer Reference (e.g. bank ref no)"><Input id={`tx-${r.id}`} /></Form.Item></Form>,
      okText: 'Transfer',
      onOk: async () => {
        const el = document.getElementById(`tx-${r.id}`) as HTMLInputElement;
        if (!el?.value || el.value.length < 3) {
          message.warning('Min 3 karakter');
          return Promise.reject();
        }
        await transferReimb(r.id, el.value);
        message.success('Marked transferred');
        onAction();
      },
    });
  };

  const btns: React.ReactNode[] = [];
  if (r.status === 'PENDING_L1' && isApprover) {
    btns.push(
      <Button key="al1" size="small" type="primary" icon={<CheckOutlined />} loading={approveL1Mut.isPending} onClick={() => approveL1Mut.mutate()} style={{ background: 'var(--ide-green)', borderColor: 'var(--ide-green)' }}>L1</Button>,
      <Button key="r" size="small" danger icon={<CloseOutlined />} onClick={handleReject}>Reject</Button>,
    );
  }
  if (r.status === 'PENDING_L2' && isApprover) {
    btns.push(
      <Button key="al2" size="small" type="primary" icon={<CheckOutlined />} loading={approveL2Mut.isPending} onClick={() => approveL2Mut.mutate()} style={{ background: 'var(--ide-green)', borderColor: 'var(--ide-green)' }}>L2</Button>,
      <Button key="r" size="small" danger icon={<CloseOutlined />} onClick={handleReject}>Reject</Button>,
    );
  }
  if (r.status === 'APPROVED' && isApprover) {
    btns.push(<Button key="tx" size="small" type="primary" icon={<SendOutlined />} onClick={handleTransfer}>Transfer</Button>);
  }
  if (['PENDING_L1', 'PENDING_L2', 'APPROVED'].includes(r.status)) {
    btns.push(<Button key="c" size="small" icon={<StopOutlined />} loading={cancelMut.isPending} onClick={() => cancelMut.mutate()}>Cancel</Button>);
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr 0.8fr 0.8fr 1fr 1.6fr', gap: 12, padding: '14px 20px', borderBottom: '1px solid var(--ide-border2)', fontSize: 13, alignItems: 'center' }}>
      <div>
        <div style={{ fontWeight: 700 }}>{r.employee_name}</div>
        <div style={{ fontSize: 11, color: 'var(--ide-ink3)', fontFamily: 'var(--ide-font-mono)' }}>{r.employee_nik}</div>
      </div>
      <div>
        <Tag>{r.category}</Tag>
        {r.project_name && <div style={{ fontSize: 10, color: 'var(--ide-ink3)', marginTop: 2 }}>📍 {r.project_name}</div>}
      </div>
      <div style={{ fontSize: 12 }}>{formatDate(r.request_date)}</div>
      <div style={{ textAlign: 'right', fontFamily: 'var(--ide-font-mono)', fontWeight: 700 }}>{formatIDR(r.amount)}</div>
      <div><span className={`ide-tag ${badge.className}`}>{badge.label}</span></div>
      <div style={{ display: 'flex', gap: 4, justifyContent: 'flex-end' }}>{btns}</div>
    </div>
  );
}

function CreateReimbModal({ open, onClose, onSuccess }: { open: boolean; onClose: () => void; onSuccess: () => void }) {
  const [form] = Form.useForm();
  const empQuery = useQuery({ queryKey: ['emp-reimb'], queryFn: () => listEmployees({ page_size: 200 }), enabled: open });

  const mutation = useMutation({
    mutationFn: createReimbursement,
    onSuccess: () => { message.success('Reimbursement submitted'); form.resetFields(); onSuccess(); onClose(); },
    onError: (e: any) => message.error(e?.response?.data?.detail?.message || 'Gagal'),
  });

  return (
    <Modal
      title="Submit Reimbursement"
      open={open}
      onCancel={onClose}
      width={560}
      footer={[<Button key="c" onClick={onClose}>Batal</Button>,
        <Button key="s" type="primary" loading={mutation.isPending} onClick={async () => {
          const v = await form.validateFields();
          mutation.mutate({
            employee_id: v.employee_id,
            request_date: dayjs(v.request_date).format('YYYY-MM-DD'),
            category: v.category,
            amount: v.amount,
            description: v.description,
            currency: 'IDR',
          });
        }}>Submit</Button>]}
      destroyOnHidden
    >
      <Form form={form} layout="vertical" initialValues={{ category: 'OTHER', request_date: dayjs() }}>
        <Form.Item label="Karyawan" name="employee_id" rules={[{ required: true }]}>
          <Select showSearch optionFilterProp="label" options={(empQuery.data?.items || []).map((e) => ({ value: e.id, label: `${e.nik} · ${e.full_name}` }))} />
        </Form.Item>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <Form.Item label="Category" name="category" rules={[{ required: true }]}>
            <Select options={REIMB_CATEGORIES.map((c) => ({ value: c, label: c }))} />
          </Form.Item>
          <Form.Item label="Request Date" name="request_date" rules={[{ required: true }]}>
            <DatePicker style={{ width: '100%' }} format="DD MMM YYYY" />
          </Form.Item>
        </div>
        <Form.Item label="Amount (IDR)" name="amount" rules={[{ required: true }]}>
          <InputNumber min={0} style={{ width: '100%', fontFamily: 'var(--ide-font-mono)' }} formatter={(v) => v ? `Rp ${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, '.') : ''} parser={(v) => v ? Number(v.replace(/[^0-9]/g, '')) : 0} />
        </Form.Item>
        <Form.Item label="Description (min 10 char)" name="description" rules={[{ required: true }, { min: 10 }]}>
          <TextArea rows={3} placeholder="Detail expense, lokasi, peserta..." />
        </Form.Item>
      </Form>
    </Modal>
  );
}

// ─── PROCUREMENT TAB ────────────────────────────────────────────

function ProcurementTab() {
  const queryClient = useQueryClient();
  const user = useAuthStore((s) => s.user);
  const [statusFilter, setStatusFilter] = useState<ProcStatus | undefined>();
  const [createOpen, setCreateOpen] = useState(false);

  const isApprover =
    user?.roles.some((r) =>
      ['DIREKTUR_UTAMA', 'WAKIL_DIREKTUR_UTAMA', 'C_LEVEL', 'GM'].includes(r.code),
    ) ?? false;

  const query = useQuery({
    queryKey: ['procurements', statusFilter],
    queryFn: () => listProcurements({ status: statusFilter, page_size: 100 }),
  });

  const items = query.data?.items || [];
  const pending = items.filter((p) => ['PENDING_L1', 'PENDING_L2'].includes(p.status)).length;
  const ordered = items.filter((p) => p.status === 'ORDERED').length;
  const delivered = items.filter((p) => p.status === 'DELIVERED').length;
  const totalEstimate = items.reduce((acc, p) => acc + (p.estimated_amount ? parseFloat(p.estimated_amount) : 0), 0);

  return (
    <div>
      <div style={{ display: 'flex', gap: 10, marginBottom: 14, flexWrap: 'wrap' }}>
        <Select
          placeholder="All Status"
          style={{ width: 220 }}
          allowClear
          value={statusFilter}
          onChange={(v) => setStatusFilter(v as ProcStatus)}
          options={[
            { value: 'PENDING_L1', label: 'Pending L1' },
            { value: 'PENDING_L2', label: 'Pending L2' },
            { value: 'APPROVED', label: 'Approved (siap PO)' },
            { value: 'ORDERED', label: 'Ordered' },
            { value: 'DELIVERED', label: 'Delivered' },
            { value: 'REJECTED', label: 'Rejected' },
          ]}
        />
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setCreateOpen(true)}
          style={{ background: 'var(--ide-blue)', borderColor: 'var(--ide-blue)' }}
        >
          Request Procurement
        </Button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 18 }}>
        <div className="ide-kpi">
          <div className="ide-kpi-val">{items.length}</div>
          <div className="ide-kpi-lbl">Total Requests</div>
        </div>
        <div className="ide-kpi">
          <div className="ide-kpi-val" style={{ color: 'var(--ide-orange)' }}>{pending}</div>
          <div className="ide-kpi-lbl">Pending Approval</div>
        </div>
        <div className="ide-kpi">
          <div className="ide-kpi-val" style={{ color: 'var(--ide-purple)' }}>{ordered}</div>
          <div className="ide-kpi-lbl">Ordered (waiting delivery)</div>
        </div>
        <div className="ide-kpi">
          <div className="ide-kpi-val" style={{ fontSize: 16 }}>Rp {(totalEstimate / 1_000_000).toFixed(1)}M</div>
          <div className="ide-kpi-lbl">Total Estimate ({delivered} delivered)</div>
        </div>
      </div>

      <div style={{ background: 'var(--ide-surface)', border: '1px solid var(--ide-border)', borderRadius: 'var(--ide-r)', overflow: 'hidden' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 0.6fr 1fr 1fr 1.6fr', gap: 12, padding: '12px 20px', background: 'var(--ide-bg)', borderBottom: '1px solid var(--ide-border)', fontSize: 10, fontWeight: 700, color: 'var(--ide-ink3)', textTransform: 'uppercase' }}>
          <div>Item</div>
          <div>Category</div>
          <div style={{ textAlign: 'center' }}>Qty</div>
          <div style={{ textAlign: 'right' }}>Estimate</div>
          <div>Status</div>
          <div style={{ textAlign: 'right' }}>Actions</div>
        </div>

        {query.isLoading && <Spin style={{ display: 'block', margin: 40 }} />}
        {query.data && items.length === 0 && <Empty style={{ padding: 40 }} />}

        {items.map((p) => (
          <ProcRow key={p.id} p={p} onAction={() => queryClient.invalidateQueries({ queryKey: ['procurements'] })} isApprover={isApprover} />
        ))}
      </div>

      <CreateProcModal open={createOpen} onClose={() => setCreateOpen(false)} onSuccess={() => queryClient.invalidateQueries({ queryKey: ['procurements'] })} />
    </div>
  );
}

function ProcRow({ p, onAction, isApprover }: { p: ProcurementListItem; onAction: () => void; isApprover: boolean }) {
  const badge = procStatusColor(p.status);

  const approveL1Mut = useMutation({ mutationFn: () => approveProcL1(p.id), onSuccess: () => { message.success('Approved L1'); onAction(); }, onError: (e: any) => message.error(e?.response?.data?.detail?.message || 'Gagal') });
  const approveL2Mut = useMutation({ mutationFn: () => approveProcL2(p.id), onSuccess: () => { message.success('Approved L2'); onAction(); }, onError: (e: any) => message.error(e?.response?.data?.detail?.message || 'Gagal') });

  const handleOrder = () => {
    modal.confirm({
      title: 'Mark as Ordered',
      content: (
        <Form layout="vertical">
          <Form.Item label="PO Number" required><Input id={`po-${p.id}`} /></Form.Item>
        </Form>
      ),
      okText: 'Mark Ordered',
      onOk: async () => {
        const el = document.getElementById(`po-${p.id}`) as HTMLInputElement;
        if (!el?.value || el.value.length < 3) {
          message.warning('PO number min 3 char');
          return Promise.reject();
        }
        await orderProc(p.id, { po_number: el.value });
        message.success('Marked as ORDERED');
        onAction();
      },
    });
  };

  const handleDeliver = () => {
    modal.confirm({
      title: 'Mark as Delivered',
      content: <p>Mark item delivered hari ini ({dayjs().format('DD MMM YYYY')})?</p>,
      onOk: async () => {
        await deliverProc(p.id, dayjs().format('YYYY-MM-DD'));
        message.success('DELIVERED');
        onAction();
      },
    });
  };

  const btns: React.ReactNode[] = [];
  if (p.status === 'PENDING_L1' && isApprover) {
    btns.push(
      <Button key="al1" size="small" type="primary" icon={<CheckOutlined />} loading={approveL1Mut.isPending} onClick={() => approveL1Mut.mutate()} style={{ background: 'var(--ide-green)', borderColor: 'var(--ide-green)' }}>L1</Button>,
    );
  }
  if (p.status === 'PENDING_L2' && isApprover) {
    btns.push(
      <Button key="al2" size="small" type="primary" icon={<CheckOutlined />} loading={approveL2Mut.isPending} onClick={() => approveL2Mut.mutate()} style={{ background: 'var(--ide-green)', borderColor: 'var(--ide-green)' }}>L2</Button>,
    );
  }
  if (p.status === 'APPROVED' && isApprover) {
    btns.push(<Button key="o" size="small" type="primary" onClick={handleOrder}>Order (PO)</Button>);
  }
  if (p.status === 'ORDERED') {
    btns.push(<Button key="d" size="small" type="primary" onClick={handleDeliver} style={{ background: 'var(--ide-green)', borderColor: 'var(--ide-green)' }}>Deliver</Button>);
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 0.6fr 1fr 1fr 1.6fr', gap: 12, padding: '14px 20px', borderBottom: '1px solid var(--ide-border2)', fontSize: 13, alignItems: 'center' }}>
      <div>
        <div style={{ fontWeight: 600, color: 'var(--ide-ink)' }}>{p.item_description}</div>
        <div style={{ fontSize: 11, color: 'var(--ide-ink3)', fontFamily: 'var(--ide-font-mono)', marginTop: 2 }}>
          by {p.requested_by_nik} {p.is_asset && <Tag color="purple">ASSET</Tag>}
          {p.vendor_name && ` · ${p.vendor_name}`}
        </div>
      </div>
      <div><Tag>{p.item_category}</Tag></div>
      <div style={{ textAlign: 'center', fontFamily: 'var(--ide-font-mono)', fontWeight: 700 }}>{p.quantity}</div>
      <div style={{ textAlign: 'right', fontFamily: 'var(--ide-font-mono)' }}>{formatIDR(p.estimated_amount)}</div>
      <div><span className={`ide-tag ${badge.className}`}>{badge.label}</span></div>
      <div style={{ display: 'flex', gap: 4, justifyContent: 'flex-end' }}>{btns}</div>
    </div>
  );
}

function CreateProcModal({ open, onClose, onSuccess }: { open: boolean; onClose: () => void; onSuccess: () => void }) {
  const [form] = Form.useForm();
  const vendorQuery = useQuery({ queryKey: ['vendors'], queryFn: listVendors, enabled: open });

  const mutation = useMutation({
    mutationFn: createProcurement,
    onSuccess: () => { message.success('Procurement request submitted'); form.resetFields(); onSuccess(); onClose(); },
    onError: (e: any) => message.error(e?.response?.data?.detail?.message || 'Gagal'),
  });

  return (
    <Modal
      title="Request Procurement"
      open={open}
      onCancel={onClose}
      width={560}
      footer={[<Button key="c" onClick={onClose}>Batal</Button>,
        <Button key="s" type="primary" loading={mutation.isPending} onClick={async () => {
          const v = await form.validateFields();
          mutation.mutate({
            item_description: v.item_description,
            item_category: v.item_category,
            quantity: v.quantity,
            estimated_amount: v.estimated_amount,
            vendor_id: v.vendor_id,
            is_asset: v.is_asset || false,
            expected_delivery_date: v.expected_delivery_date ? dayjs(v.expected_delivery_date).format('YYYY-MM-DD') : undefined,
            notes: v.notes,
          });
        }}>Submit</Button>]}
      destroyOnHidden
    >
      <Form form={form} layout="vertical" initialValues={{ item_category: 'OTHER', quantity: 1, is_asset: false }}>
        <Form.Item label="Item Description (min 10 char)" name="item_description" rules={[{ required: true }, { min: 10 }]}>
          <TextArea rows={2} placeholder="Macbook Pro 14 M3 untuk Engineer baru" />
        </Form.Item>
        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr', gap: 12 }}>
          <Form.Item label="Category" name="item_category" rules={[{ required: true }]}>
            <Select options={PROC_CATEGORIES.map((c) => ({ value: c, label: c }))} />
          </Form.Item>
          <Form.Item label="Quantity" name="quantity" rules={[{ required: true }]}>
            <InputNumber min={1} max={9999} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item label="Is Asset?" name="is_asset" valuePropName="checked">
            <Select options={[{ value: false, label: 'No' }, { value: true, label: 'Yes (CAPEX)' }]} />
          </Form.Item>
        </div>
        <Form.Item label="Estimated Amount (IDR)" name="estimated_amount">
          <InputNumber min={0} style={{ width: '100%', fontFamily: 'var(--ide-font-mono)' }} formatter={(v) => v ? `Rp ${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, '.') : ''} parser={(v) => v ? Number(v.replace(/[^0-9]/g, '')) : 0} />
        </Form.Item>
        <Form.Item label="Preferred Vendor (opsional)" name="vendor_id">
          <Select allowClear options={(vendorQuery.data || []).map((v) => ({ value: v.id, label: `${v.code} · ${v.name}` }))} />
        </Form.Item>
        <Form.Item label="Expected Delivery" name="expected_delivery_date">
          <DatePicker style={{ width: '100%' }} format="DD MMM YYYY" />
        </Form.Item>
        <Form.Item label="Notes" name="notes">
          <TextArea rows={2} />
        </Form.Item>
      </Form>
    </Modal>
  );
}

// ─── VENDOR TAB ──────────────────────────────────────────────────

function VendorTab() {
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const query = useQuery({ queryKey: ['vendors'], queryFn: listVendors });
  const vendors = query.data || [];

  const mutation = useMutation({
    mutationFn: createVendor,
    onSuccess: () => {
      message.success('Vendor created');
      queryClient.invalidateQueries({ queryKey: ['vendors'] });
      setCreateOpen(false);
    },
    onError: (e: any) => message.error(e?.response?.data?.detail?.message || 'Gagal'),
  });

  return (
    <div>
      <div style={{ marginBottom: 14 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
          Add Vendor
        </Button>
      </div>

      {vendors.length === 0 && <Empty description="Belum ada vendor" />}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 10 }}>
        {vendors.map((v) => (
          <div key={v.id} style={{ background: 'var(--ide-surface)', border: '1px solid var(--ide-border)', borderRadius: 'var(--ide-rm)', padding: 14 }}>
            <div style={{ fontFamily: 'var(--ide-font-mono)', fontSize: 11, color: 'var(--ide-blue)', fontWeight: 700 }}>{v.code}</div>
            <div style={{ fontSize: 15, fontWeight: 700, marginTop: 2 }}>{v.name}</div>
            {v.contact_info && <div style={{ fontSize: 12, color: 'var(--ide-ink2)', marginTop: 6, whiteSpace: 'pre-wrap' }}>{v.contact_info}</div>}
          </div>
        ))}
      </div>

      <Modal title="Add Vendor" open={createOpen} onCancel={() => setCreateOpen(false)} footer={null} destroyOnHidden>
        <Form layout="vertical" onFinish={(v) => mutation.mutate(v)}>
          <Form.Item label="Code" name="code" rules={[{ required: true, min: 2 }]}>
            <Input placeholder="VND-001" style={{ fontFamily: 'var(--ide-font-mono)' }} />
          </Form.Item>
          <Form.Item label="Name" name="name" rules={[{ required: true }]}>
            <Input placeholder="PT. Tokopedia Indonesia" />
          </Form.Item>
          <Form.Item label="Contact Info" name="contact_info">
            <TextArea rows={3} placeholder="Email, phone, address..." />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={mutation.isPending}>Add</Button>
        </Form>
      </Modal>
    </div>
  );
}

// ─── Main Page ───────────────────────────────────────────────────

export default function FinancePage() {
  return (
    <div className="ide-font" style={{ maxWidth: 1400, margin: '0 auto' }}>
      <div style={{ marginBottom: 18 }}>
        <h2 style={{ fontSize: 22, fontWeight: 800, letterSpacing: -0.5, marginBottom: 4 }}>
          Finance Operations
        </h2>
        <p style={{ fontSize: 13, color: 'var(--ide-ink2)' }}>
          Invoices/AR (billing termin) · Reimbursement (transfer terpisah dari payroll) · Procurement · Vendor master.
        </p>
      </div>

      <Tabs
        defaultActiveKey="invoices"
        items={[
          { key: 'invoices', label: 'Invoices / AR', children: <InvoicesTab /> },
          { key: 'reimb', label: 'Reimbursement', children: <ReimbursementTab /> },
          { key: 'proc', label: 'Procurement', children: <ProcurementTab /> },
          { key: 'vendor', label: 'Vendors', children: <VendorTab /> },
        ]}
      />
    </div>
  );
}

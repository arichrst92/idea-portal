/**
 * DocumentsTab — TSK-068 Technical Documentation Module.
 *
 * Per project: folder navigation, file upload (multipart → MinIO),
 * download via presigned URL, version history drawer, soft delete.
 */

import {
  CloudDownloadOutlined,
  DeleteOutlined,
  FileOutlined,
  FolderOpenOutlined,
  HistoryOutlined,
  InboxOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Button,
  Drawer,
  Empty,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Spin,
  Table,
  Tag,
  Tooltip,
  Typography,
  Upload,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { UploadFile } from 'antd/es/upload/interface';
import dayjs from 'dayjs';
import { useState } from 'react';

import {
  deleteDocument,
  getDownloadUrl,
  listDocuments,
  listFolders,
  listVersions,
  uploadDocument,
  type ProjectDocument,
} from '@/api/documents';

const { Text } = Typography;
const { Dragger } = Upload;

interface DocumentsTabProps {
  projectId: string;
}

export function DocumentsTab({ projectId }: DocumentsTabProps) {
  const queryClient = useQueryClient();
  const [activeFolder, setActiveFolder] = useState<string | undefined>(undefined);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [historyDoc, setHistoryDoc] = useState<ProjectDocument | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [uploadForm] = Form.useForm();
  const [uploadFile, setUploadFile] = useState<File | null>(null);

  const foldersQ = useQuery({
    queryKey: ['doc-folders', projectId],
    queryFn: () => listFolders(projectId),
  });

  const docsQ = useQuery({
    queryKey: ['documents', projectId, activeFolder],
    queryFn: () => listDocuments(projectId, { folder_path: activeFolder }),
  });

  const uploadMut = useMutation({
    mutationFn: async (v: { name: string; folder_path?: string; version?: string }) => {
      if (!uploadFile) throw new Error('File belum dipilih');
      return uploadDocument(projectId, uploadFile, v);
    },
    onSuccess: () => {
      message.success('Document uploaded');
      queryClient.invalidateQueries({ queryKey: ['documents', projectId] });
      queryClient.invalidateQueries({ queryKey: ['doc-folders', projectId] });
      setUploadOpen(false);
      setUploadFile(null);
      uploadForm.resetFields();
    },
    onError: (e: any) =>
      message.error(e?.response?.data?.detail?.message ?? 'Gagal upload'),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteDocument(id),
    onSuccess: () => {
      message.success('Document dihapus');
      queryClient.invalidateQueries({ queryKey: ['documents', projectId] });
    },
  });

  const handleDownload = async (doc: ProjectDocument) => {
    try {
      const { url } = await getDownloadUrl(doc.id);
      window.open(url, '_blank');
    } catch (e: any) {
      message.error(e?.response?.data?.detail?.message ?? 'Gagal generate URL');
    }
  };

  const columns: ColumnsType<ProjectDocument> = [
    {
      title: 'Name', key: 'name',
      render: (_, r) => (
        <Space>
          <FileOutlined style={{ color: 'var(--ide-blue, #0071E3)' }} />
          <div>
            <div style={{ fontWeight: 600 }}>{r.name}</div>
            {r.folder_path && (
              <Text type="secondary" style={{ fontSize: 11 }}>
                📁 {r.folder_path}
              </Text>
            )}
          </div>
        </Space>
      ),
    },
    {
      title: 'Version', dataIndex: 'version', key: 'version', width: 90,
      render: (v: string) => <Tag color="blue">{v}</Tag>,
    },
    {
      title: 'Uploaded By', key: 'uploader', width: 140,
      render: (_, r) => (
        <Text type="secondary" style={{ fontSize: 12 }}>
          {r.uploaded_by_nik ?? '—'}
        </Text>
      ),
    },
    {
      title: 'Uploaded', dataIndex: 'created_at', key: 'created', width: 120,
      render: (v: string) => (
        <Tooltip title={dayjs(v).format('DD MMM YYYY HH:mm')}>
          <Text style={{ fontSize: 12 }}>{dayjs(v).format('DD MMM YY')}</Text>
        </Tooltip>
      ),
    },
    {
      title: 'Actions', key: 'act', width: 130, align: 'center',
      render: (_, r) => (
        <Space size={4}>
          <Tooltip title="Download">
            <Button
              type="text" size="small" icon={<CloudDownloadOutlined />}
              onClick={() => handleDownload(r)}
            />
          </Tooltip>
          <Tooltip title="Version history">
            <Button
              type="text" size="small" icon={<HistoryOutlined />}
              onClick={() => { setHistoryDoc(r); setHistoryOpen(true); }}
            />
          </Tooltip>
          <Popconfirm title="Hapus document?" onConfirm={() => deleteMut.mutate(r.id)}>
            <Button type="text" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
        <Space>
          <Text type="secondary" style={{ fontSize: 12 }}>Filter folder:</Text>
          <Select
            allowClear placeholder="Semua folder" style={{ width: 220 }}
            value={activeFolder} onChange={setActiveFolder}
            options={(foldersQ.data ?? []).map((f) => ({ value: f, label: f }))}
            suffixIcon={<FolderOpenOutlined />}
          />
        </Space>
        <Button type="primary" icon={<InboxOutlined />} onClick={() => setUploadOpen(true)}>
          Upload Document
        </Button>
      </div>

      {docsQ.isLoading ? (
        <Spin />
      ) : (docsQ.data ?? []).length === 0 ? (
        <Empty description={
          activeFolder
            ? `Belum ada document di folder "${activeFolder}"`
            : 'Belum ada document'
        } />
      ) : (
        <Table
          rowKey="id" columns={columns} dataSource={docsQ.data ?? []}
          size="small" pagination={{ pageSize: 20 }}
        />
      )}

      {/* Upload Modal */}
      <Modal
        title="Upload Document" open={uploadOpen}
        onCancel={() => { setUploadOpen(false); setUploadFile(null); uploadForm.resetFields(); }}
        footer={null} destroyOnClose width={520}
      >
        <Form
          form={uploadForm} layout="vertical"
          initialValues={{ version: 'v1.0' }}
          onFinish={(v) => uploadMut.mutate(v)}
        >
          <Form.Item label="File" required>
            <Dragger
              maxCount={1} multiple={false}
              beforeUpload={(file) => {
                setUploadFile(file as any);
                // Auto-suggest name dari filename
                if (!uploadForm.getFieldValue('name')) {
                  uploadForm.setFieldValue('name', (file as any).name);
                }
                return false; // prevent auto-upload, handle manually
              }}
              onRemove={() => setUploadFile(null)}
              fileList={uploadFile ? [{
                uid: '1', name: uploadFile.name, status: 'done',
              } as UploadFile] : []}
            >
              <p className="ant-upload-drag-icon"><InboxOutlined /></p>
              <p style={{ fontSize: 13 }}>Klik atau drag file ke sini</p>
              <p className="ant-upload-hint" style={{ fontSize: 11 }}>
                Max 1 file per upload. Mendukung semua format.
              </p>
            </Dragger>
          </Form.Item>
          <Form.Item label="Display Name" name="name" rules={[{ required: true }]}>
            <Input placeholder="Architecture Diagram.pdf" />
          </Form.Item>
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 10 }}>
            <Form.Item label="Folder Path (optional)" name="folder_path">
              <Input placeholder="design / api-specs / contracts" />
            </Form.Item>
            <Form.Item label="Version" name="version">
              <Input placeholder="v1.0" />
            </Form.Item>
          </div>
          <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 10 }}>
            Tip: kalau version masih default v1.0 dan name+folder sudah ada di project ini,
            version akan auto-bump (v1.1 → v1.2 dst).
          </Text>
          <Button type="primary" htmlType="submit" loading={uploadMut.isPending} block disabled={!uploadFile}>
            Upload
          </Button>
        </Form>
      </Modal>

      {/* Version History Drawer */}
      <VersionHistoryDrawer
        doc={historyDoc} open={historyOpen}
        onClose={() => { setHistoryOpen(false); setHistoryDoc(null); }}
        onDownload={handleDownload}
      />
    </div>
  );
}

function VersionHistoryDrawer({
  doc, open, onClose, onDownload,
}: {
  doc: ProjectDocument | null;
  open: boolean;
  onClose: () => void;
  onDownload: (doc: ProjectDocument) => void;
}) {
  const query = useQuery({
    queryKey: ['versions', doc?.id],
    queryFn: () => listVersions(doc!.id),
    enabled: !!doc && open,
  });

  return (
    <Drawer
      title={doc ? `Version History — ${doc.name}` : 'Version History'}
      open={open} onClose={onClose} width={520}
    >
      {doc && (
        <>
          {doc.folder_path && (
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 12 }}>
              📁 {doc.folder_path}
            </Text>
          )}
          {query.isLoading ? <Spin /> : (
            <Space direction="vertical" size={12} style={{ width: '100%' }}>
              {(query.data ?? []).map((v, idx) => (
                <div
                  key={v.id}
                  style={{
                    background: idx === 0 ? 'rgba(0,113,227,0.05)' : 'rgba(0,0,0,0.02)',
                    border: idx === 0 ? '1px solid var(--ide-blue, #0071E3)' : '1px solid transparent',
                    borderRadius: 8, padding: 12,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Space>
                      <Tag color={idx === 0 ? 'blue' : 'default'}>{v.version}</Tag>
                      {idx === 0 && <Text type="success" style={{ fontSize: 11 }}>LATEST</Text>}
                    </Space>
                    <Button size="small" icon={<CloudDownloadOutlined />} onClick={() => onDownload(v)}>
                      Download
                    </Button>
                  </div>
                  <div style={{ marginTop: 6, fontSize: 11, color: 'var(--ide-ink3, #6e6e73)' }}>
                    Uploaded by <strong>{v.uploaded_by_nik ?? '—'}</strong>{' · '}
                    {dayjs(v.created_at).format('DD MMM YYYY HH:mm')}
                  </div>
                </div>
              ))}
            </Space>
          )}
        </>
      )}
    </Drawer>
  );
}

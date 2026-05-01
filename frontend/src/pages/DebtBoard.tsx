import React, { useEffect, useState } from 'react';
import {
  Card,
  Table,
  Tag,
  Typography,
  Select,
  Row,
  Col,
  Statistic,
  Button,
  Modal,
  Descriptions,
  message,
} from 'antd';
import {
  BugOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';
import axios from 'axios';

const { Title } = Typography;

interface DebtItem {
  id: number;
  debt_id: string;
  title: string;
  category: string | null;
  priority: string | null;
  status: string;
  affected_files: string[] | null;
  estimated_hours: number | null;
  risk_level: string | null;
  description: string | null;
  created_at: string | null;
}

interface DebtStats {
  total_open: number;
  by_priority: Record<string, number>;
  by_category: Record<string, number>;
  trend: {
    this_week_new: number;
    this_week_resolved: number;
    net_change: number;
  };
  estimated_remaining_hours: number;
}

const DebtBoard: React.FC = () => {
  const [debts, setDebts] = useState<DebtItem[]>([]);
  const [stats, setStats] = useState<DebtStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    status: undefined as string | undefined,
    priority: undefined as string | undefined,
    category: undefined as string | undefined,
  });
  const [selectedDebt, setSelectedDebt] = useState<DebtItem | null>(null);
  const [detailVisible, setDetailVisible] = useState(false);

  useEffect(() => {
    fetchData();
  }, [filters]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filters.status) params.append('status', filters.status);
      if (filters.priority) params.append('priority', filters.priority);
      if (filters.category) params.append('category', filters.category);

      const [debtsRes, statsRes] = await Promise.all([
        axios.get(`/api/v1/debt?${params.toString()}`),
        axios.get('/api/v1/debt/statistics'),
      ]);
      setDebts(debtsRes.data.items || []);
      setStats(statsRes.data);
    } catch (error) {
      console.error('Failed to fetch debt data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleStatusChange = async (debtId: string, newStatus: string) => {
    try {
      await axios.patch(`/api/v1/debt/${debtId}`, { status: newStatus });
      message.success(`技术债 ${debtId} 状态已更新为 ${newStatus}`);
      fetchData();
    } catch (error) {
      message.error('状态更新失败');
    }
  };

  const priorityColor = (p: string | null) => {
    const map: Record<string, string> = {
      critical: 'red',
      high: 'orange',
      medium: 'blue',
      low: 'green',
    };
    return map[p || ''] || 'default';
  };

  const categoryColor = (c: string | null) => {
    const map: Record<string, string> = {
      security: 'red',
      architecture: 'purple',
      quality: 'blue',
      compliance: 'cyan',
    };
    return map[c || ''] || 'default';
  };

  const statusColor = (s: string) => {
    const map: Record<string, string> = {
      open: 'blue',
      in_progress: 'processing',
      resolved: 'green',
      wontfix: 'default',
    };
    return map[s] || 'default';
  };

  const columns = [
    {
      title: 'ID',
      dataIndex: 'debt_id',
      key: 'debt_id',
      width: 180,
      render: (text: string, record: DebtItem) => (
        <a onClick={() => { setSelectedDebt(record); setDetailVisible(true); }}>
          {text}
        </a>
      ),
    },
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
    },
    {
      title: '优先级',
      dataIndex: 'priority',
      key: 'priority',
      width: 100,
      render: (p: string | null) => (
        <Tag color={priorityColor(p)}>{p || '-'}</Tag>
      ),
    },
    {
      title: '类别',
      dataIndex: 'category',
      key: 'category',
      width: 120,
      render: (c: string | null) => (
        <Tag color={categoryColor(c)}>{c || '-'}</Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (s: string, record: DebtItem) => (
        <Select
          value={s}
          size="small"
          style={{ width: 100 }}
          onChange={(val) => handleStatusChange(record.debt_id, val)}
          options={[
            { value: 'open', label: '待处理' },
            { value: 'in_progress', label: '进行中' },
            { value: 'resolved', label: '已修复' },
            { value: 'wontfix', label: '不修复' },
          ]}
        />
      ),
    },
    {
      title: '预估工时',
      dataIndex: 'estimated_hours',
      key: 'estimated_hours',
      width: 100,
      render: (h: number | null) => (h ? `${h}h` : '-'),
    },
    {
      title: '风险',
      dataIndex: 'risk_level',
      key: 'risk_level',
      width: 80,
      render: (r: string | null) => (
        <Tag color={r === 'high' ? 'red' : r === 'medium' ? 'orange' : 'green'}>
          {r || '-'}
        </Tag>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
    },
  ];

  return (
    <div>
      <Title level={3}>技术债看板</Title>

      {stats && (
        <Row gutter={16} style={{ marginBottom: 24 }}>
          <Col span={6}>
            <Card>
              <Statistic
                title="待处理"
                value={stats.total_open}
                prefix={<BugOutlined />}
                valueStyle={{ color: stats.total_open > 0 ? '#cf1322' : '#3f8600' }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="本周新增"
                value={stats.trend?.this_week_new || 0}
                prefix={<ExclamationCircleOutlined />}
                valueStyle={{ color: '#fa8c16' }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="本周修复"
                value={stats.trend?.this_week_resolved || 0}
                prefix={<CheckCircleOutlined />}
                valueStyle={{ color: '#3f8600' }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="剩余工时"
                value={stats.estimated_remaining_hours}
                suffix="h"
              />
            </Card>
          </Col>
        </Row>
      )}

      <Card
        title="技术债列表"
        extra={
          <div style={{ display: 'flex', gap: 8 }}>
            <Select
              placeholder="状态"
              allowClear
              style={{ width: 120 }}
              value={filters.status}
              onChange={(v) => setFilters({ ...filters, status: v })}
              options={[
                { value: 'open', label: '待处理' },
                { value: 'in_progress', label: '进行中' },
                { value: 'resolved', label: '已修复' },
              ]}
            />
            <Select
              placeholder="优先级"
              allowClear
              style={{ width: 120 }}
              value={filters.priority}
              onChange={(v) => setFilters({ ...filters, priority: v })}
              options={[
                { value: 'critical', label: 'Critical' },
                { value: 'high', label: 'High' },
                { value: 'medium', label: 'Medium' },
                { value: 'low', label: 'Low' },
              ]}
            />
            <Select
              placeholder="类别"
              allowClear
              style={{ width: 120 }}
              value={filters.category}
              onChange={(v) => setFilters({ ...filters, category: v })}
              options={[
                { value: 'security', label: '安全' },
                { value: 'architecture', label: '架构' },
                { value: 'quality', label: '质量' },
                { value: 'compliance', label: '规范' },
              ]}
            />
          </div>
        }
      >
        <Table
          columns={columns}
          dataSource={debts}
          rowKey="debt_id"
          loading={loading}
          pagination={{ pageSize: 20 }}
          size="middle"
        />
      </Card>

      <Modal
        title={selectedDebt?.debt_id}
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        footer={null}
        width={700}
      >
        {selectedDebt && (
          <Descriptions bordered column={1}>
            <Descriptions.Item label="标题">{selectedDebt.title}</Descriptions.Item>
            <Descriptions.Item label="优先级">
              <Tag color={priorityColor(selectedDebt.priority)}>
                {selectedDebt.priority}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="类别">
              <Tag color={categoryColor(selectedDebt.category)}>
                {selectedDebt.category}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={statusColor(selectedDebt.status)}>
                {selectedDebt.status}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="受影响文件">
              {selectedDebt.affected_files?.join(', ') || '-'}
            </Descriptions.Item>
            <Descriptions.Item label="预估工时">
              {selectedDebt.estimated_hours ? `${selectedDebt.estimated_hours}h` : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="风险等级">
              {selectedDebt.risk_level || '-'}
            </Descriptions.Item>
            <Descriptions.Item label="描述">
              {selectedDebt.description || '-'}
            </Descriptions.Item>
          </Descriptions>
        )}
      </Modal>
    </div>
  );
};

export default DebtBoard;

import React, { useEffect, useState } from 'react';
import { Card, Col, Row, Statistic, Table, Tag, Typography, Spin } from 'antd';
import {
  BugOutlined,
  WarningOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

const { Title } = Typography;

interface ReviewItem {
  review_id: string;
  pr_id: string;
  status: string;
  total_issues: number;
  critical: number;
  warning: number;
  info: number;
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

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const [reviews, setReviews] = useState<ReviewItem[]>([]);
  const [debtStats, setDebtStats] = useState<DebtStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [reviewsRes, debtRes] = await Promise.all([
        axios.get('/api/v1/reviews?page=1&page_size=10'),
        axios.get('/api/v1/debt/statistics'),
      ]);
      setReviews(reviewsRes.data.items || []);
      setDebtStats(debtRes.data);
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  const statusColorMap: Record<string, string> = {
    completed: 'green',
    pending: 'blue',
    scanning: 'processing',
    failed: 'red',
  };

  const columns = [
    {
      title: '审查 ID',
      dataIndex: 'review_id',
      key: 'review_id',
      render: (text: string) => (
        <a onClick={() => navigate(`/review/${text}`)}>{text}</a>
      ),
    },
    {
      title: 'PR ID',
      dataIndex: 'pr_id',
      key: 'pr_id',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag color={statusColorMap[status] || 'default'}>{status}</Tag>
      ),
    },
    {
      title: '问题数',
      dataIndex: 'total_issues',
      key: 'total_issues',
    },
    {
      title: 'Critical',
      dataIndex: 'critical',
      key: 'critical',
      render: (v: number) => v > 0 ? <Tag color="red">{v}</Tag> : v,
    },
    {
      title: 'Warning',
      dataIndex: 'warning',
      key: 'warning',
      render: (v: number) => v > 0 ? <Tag color="orange">{v}</Tag> : v,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
    },
  ];

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 100 }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div>
      <Title level={3}>总览看板</Title>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="待处理技术债"
              value={debtStats?.total_open || 0}
              prefix={<BugOutlined />}
              valueStyle={{ color: debtStats?.total_open ? '#cf1322' : '#3f8600' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="本周新增"
              value={debtStats?.trend?.this_week_new || 0}
              prefix={<WarningOutlined />}
              valueStyle={{ color: '#fa8c16' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="本周修复"
              value={debtStats?.trend?.this_week_resolved || 0}
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: '#3f8600' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="预估剩余工时"
              value={debtStats?.estimated_remaining_hours || 0}
              prefix={<ClockCircleOutlined />}
              suffix="小时"
            />
          </Card>
        </Col>
      </Row>

      <Card title="最近代码审查" style={{ marginBottom: 24 }}>
        <Table
          columns={columns}
          dataSource={reviews}
          rowKey="review_id"
          pagination={false}
          size="middle"
        />
      </Card>

      {debtStats && (
        <Row gutter={16}>
          <Col span={12}>
            <Card title="技术债 - 按优先级分布">
              {Object.entries(debtStats.by_priority || {}).map(([key, value]) => (
                <div key={key} style={{ marginBottom: 8 }}>
                  <Tag
                    color={
                      key === 'critical'
                        ? 'red'
                        : key === 'high'
                        ? 'orange'
                        : key === 'medium'
                        ? 'blue'
                        : 'green'
                    }
                  >
                    {key}
                  </Tag>
                  <span style={{ marginLeft: 8 }}>{value} 项</span>
                </div>
              ))}
            </Card>
          </Col>
          <Col span={12}>
            <Card title="技术债 - 按类别分布">
              {Object.entries(debtStats.by_category || {}).map(([key, value]) => (
                <div key={key} style={{ marginBottom: 8 }}>
                  <Tag
                    color={
                      key === 'security'
                        ? 'red'
                        : key === 'architecture'
                        ? 'purple'
                        : key === 'quality'
                        ? 'blue'
                        : 'cyan'
                    }
                  >
                    {key}
                  </Tag>
                  <span style={{ marginLeft: 8 }}>{value} 项</span>
                </div>
              ))}
            </Card>
          </Col>
        </Row>
      )}
    </div>
  );
};

export default Dashboard;

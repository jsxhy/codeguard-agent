import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Card, Descriptions, Tag, Typography, Spin, Collapse, List, Empty } from 'antd';
import axios from 'axios';

const { Title, Paragraph } = Typography;

interface ReviewDetailData {
  review_id: string;
  pr_id: string;
  repo_url: string;
  branch: string | null;
  status: string;
  summary: {
    total_issues: number;
    critical: number;
    warning: number;
    info: number;
    compliance_violations: number;
    refactoring_items: number;
  };
  reports: {
    scan_report: any;
    compliance_report: any;
    refactoring_plan: any;
    test_result: any;
  };
  created_at: string | null;
}

const ReviewDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<ReviewDetailData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (id) fetchDetail();
  }, [id]);

  const fetchDetail = async () => {
    try {
      const res = await axios.get(`/api/v1/reviews/${id}`);
      setData(res.data);
    } catch (error) {
      console.error('Failed to fetch review detail:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 100 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!data) {
    return <Empty description="未找到审查记录" />;
  }

  const severityColor = (s: string) => {
    const map: Record<string, string> = {
      critical: 'red',
      warning: 'orange',
      info: 'blue',
    };
    return map[s] || 'default';
  };

  const scanIssues = data.reports?.scan_report?.issues || [];
  const violations = data.reports?.compliance_report?.violations || [];
  const refactoringItems = data.reports?.refactoring_plan?.items || [];

  return (
    <div>
      <Title level={3}>审查详情 - {data.review_id}</Title>

      <Card style={{ marginBottom: 16 }}>
        <Descriptions bordered column={2}>
          <Descriptions.Item label="PR ID">{data.pr_id}</Descriptions.Item>
          <Descriptions.Item label="仓库">{data.repo_url}</Descriptions.Item>
          <Descriptions.Item label="分支">{data.branch}</Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag color={data.status === 'completed' ? 'green' : 'blue'}>
              {data.status}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="总问题数">
            {data.summary.total_issues}
          </Descriptions.Item>
          <Descriptions.Item label="Critical">
            <Tag color="red">{data.summary.critical}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Warning">
            <Tag color="orange">{data.summary.warning}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Info">
            <Tag color="blue">{data.summary.info}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="规范违反">
            {data.summary.compliance_violations}
          </Descriptions.Item>
          <Descriptions.Item label="重构建议">
            {data.summary.refactoring_items}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Collapse
        defaultActiveKey={['scan', 'compliance', 'refactor']}
        style={{ marginBottom: 16 }}
      >
        <Collapse.Panel header={`代码扫描结果 (${scanIssues.length})`} key="scan">
          <List
            dataSource={scanIssues}
            renderItem={(item: any) => (
              <List.Item>
                <List.Item.Meta
                  title={
                    <span>
                      <Tag color={severityColor(item.severity)}>{item.severity}</Tag>
                      <Tag>{item.category}</Tag>
                      {item.file}:{item.line}
                    </span>
                  }
                  description={
                    <div>
                      <Paragraph>{item.description}</Paragraph>
                      {item.suggestion && (
                        <Paragraph type="secondary">
                          建议: {item.suggestion}
                        </Paragraph>
                      )}
                    </div>
                  }
                />
              </List.Item>
            )}
          />
        </Collapse.Panel>

        <Collapse.Panel header={`规范比对结果 (${violations.length})`} key="compliance">
          <List
            dataSource={violations}
            renderItem={(item: any) => (
              <List.Item>
                <List.Item.Meta
                  title={
                    <span>
                      <Tag color={severityColor(item.severity)}>{item.severity}</Tag>
                      <Tag>{item.rule}</Tag>
                      {item.file}:{item.line}
                    </span>
                  }
                  description={
                    <div>
                      <Paragraph>{item.description}</Paragraph>
                      {item.reference && (
                        <Paragraph type="secondary">参考: {item.reference}</Paragraph>
                      )}
                      {item.suggestion && (
                        <Paragraph type="success">建议: {item.suggestion}</Paragraph>
                      )}
                    </div>
                  }
                />
              </List.Item>
            )}
          />
        </Collapse.Panel>

        <Collapse.Panel header={`重构建议 (${refactoringItems.length})`} key="refactor">
          <List
            dataSource={refactoringItems}
            renderItem={(item: any) => (
              <List.Item>
                <List.Item.Meta
                  title={
                    <span>
                      <Tag
                        color={
                          item.priority === 'critical'
                            ? 'red'
                            : item.priority === 'high'
                            ? 'orange'
                            : item.priority === 'medium'
                            ? 'blue'
                            : 'green'
                        }
                      >
                        {item.priority}
                      </Tag>
                      {item.id} - {item.title}
                    </span>
                  }
                  description={
                    <div>
                      <Paragraph>{item.description}</Paragraph>
                      {item.refactoring_steps && (
                        <div>
                          <strong>重构步骤:</strong>
                          <ol>
                            {item.refactoring_steps.map((step: string, i: number) => (
                              <li key={i}>{step}</li>
                            ))}
                          </ol>
                        </div>
                      )}
                      {item.estimated_hours && (
                        <Paragraph type="secondary">
                          预估工时: {item.estimated_hours}h | 风险: {item.risk_level}
                        </Paragraph>
                      )}
                    </div>
                  }
                />
              </List.Item>
            )}
          />
        </Collapse.Panel>
      </Collapse>
    </div>
  );
};

export default ReviewDetail;

import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Layout, Menu } from 'antd';
import {
  DashboardOutlined,
  FileSearchOutlined,
  AlertOutlined,
} from '@ant-design/icons';
import Dashboard from './pages/Dashboard';
import ReviewDetail from './pages/ReviewDetail';
import DebtBoard from './pages/DebtBoard';
import { useNavigate, useLocation } from 'react-router-dom';

const { Header, Sider, Content } = Layout;

const App: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const menuItems = [
    {
      key: '/',
      icon: <DashboardOutlined />,
      label: '总览看板',
    },
    {
      key: '/debt',
      icon: <AlertOutlined />,
      label: '技术债看板',
    },
  ];

  const selectedKey = location.pathname === '/debt' ? '/debt' : '/';

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider theme="dark" width={200}>
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            fontSize: 18,
            fontWeight: 'bold',
          }}
        >
          <FileSearchOutlined style={{ marginRight: 8 }} />
          CodeGuard
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            background: '#fff',
            padding: '0 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            boxShadow: '0 1px 4px rgba(0,0,0,0.1)',
          }}
        >
          <span style={{ fontSize: 16, fontWeight: 500 }}>
            智能代码审查与技术债治理系统
          </span>
        </Header>
        <Content style={{ margin: 24 }}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/review/:id" element={<ReviewDetail />} />
            <Route path="/debt" element={<DebtBoard />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  );
};

export default App;

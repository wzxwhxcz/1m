import { useEffect, useState } from 'react';
import { Card, Row, Col, Statistic, Spin, App } from 'antd';
import { 
  ApiOutlined, 
  CheckCircleOutlined, 
  ThunderboltOutlined,
  ClockCircleOutlined,
  UserOutlined,
  CloudOutlined,
} from '@ant-design/icons';
import * as echarts from 'echarts';
import { statsApi } from '../api/client';
import type { DashboardStats, QPSData } from '../types';

export default function DashboardPage() {
  const { message } = App.useApp();
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [qpsData, setQpsData] = useState<QPSData[]>([]);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000); // 每10秒刷新
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (qpsData.length > 0) {
      renderQPSChart();
    }
  }, [qpsData]);

  const loadData = async () => {
    try {
      const [statsRes, qpsRes] = await Promise.all([
        statsApi.dashboard(),
        statsApi.qps(60),
      ]);
      setStats(statsRes.data);
      setQpsData(qpsRes.data);
    } catch (error: any) {
      message.error('加载数据失败');
    } finally {
      setLoading(false);
    }
  };

  const renderQPSChart = () => {
    const chartDom = document.getElementById('qps-chart');
    if (!chartDom) return;

    const chart = echarts.init(chartDom);
    const option = {
      backgroundColor: 'transparent',
      grid: {
        left: 50,
        right: 20,
        top: 30,
        bottom: 30,
      },
      xAxis: {
        type: 'time',
        axisLine: { lineStyle: { color: '#374151' } },
        axisLabel: { color: '#9CA3AF' },
      },
      yAxis: {
        type: 'value',
        name: 'QPS',
        nameTextStyle: { color: '#9CA3AF' },
        axisLine: { lineStyle: { color: '#374151' } },
        axisLabel: { color: '#9CA3AF' },
        splitLine: { lineStyle: { color: '#1E222E' } },
      },
      series: [{
        type: 'line',
        data: qpsData.map(d => [d.timestamp, d.qps]),
        smooth: true,
        symbol: 'none',
        lineStyle: { color: '#5B8CFF', width: 2 },
        areaStyle: { 
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(91, 140, 255, 0.3)' },
            { offset: 1, color: 'rgba(91, 140, 255, 0)' }
          ])
        },
      }],
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#1E222E',
        borderColor: '#374151',
        textStyle: { color: '#F3F4F6' },
      },
    };
    chart.setOption(option);

    return () => chart.dispose();
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 100 }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div>
      <h1 style={{ fontSize: 24, fontWeight: 600, marginBottom: 24, color: '#F3F4F6' }}>
        仪表盘
      </h1>

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={8}>
          <Card style={{ background: '#0F1117', border: '1px solid #1E222E' }}>
            <Statistic
              title={<span style={{ color: '#9CA3AF' }}>今日请求数</span>}
              value={stats?.today_requests || 0}
              prefix={<ApiOutlined style={{ color: '#5B8CFF' }} />}
              styles={{ value: { color: '#F3F4F6' } }}
            />
          </Card>
        </Col>

        <Col xs={24} sm={12} lg={8}>
          <Card style={{ background: '#0F1117', border: '1px solid #1E222E' }}>
            <Statistic
              title={<span style={{ color: '#9CA3AF' }}>成功率</span>}
              value={stats?.success_rate || 0}
              suffix="%"
              precision={1}
              prefix={<CheckCircleOutlined style={{ color: '#10B981' }} />}
              styles={{ value: { color: '#F3F4F6' } }}
            />
          </Card>
        </Col>

        <Col xs={24} sm={12} lg={8}>
          <Card style={{ background: '#0F1117', border: '1px solid #1E222E' }}>
            <Statistic
              title={<span style={{ color: '#9CA3AF' }}>平均延迟</span>}
              value={stats?.avg_latency || 0}
              suffix="ms"
              prefix={<ClockCircleOutlined style={{ color: '#3B82F6' }} />}
              styles={{ value: { color: '#F3F4F6' } }}
            />
          </Card>
        </Col>

        <Col xs={24} sm={12} lg={8}>
          <Card style={{ background: '#0F1117', border: '1px solid #1E222E' }}>
            <Statistic
              title={<span style={{ color: '#9CA3AF' }}>召回触发次数</span>}
              value={stats?.recall_triggered || 0}
              prefix={<ThunderboltOutlined style={{ color: '#22D3EE' }} />}
              styles={{ value: { color: '#F3F4F6' } }}
            />
          </Card>
        </Col>

        <Col xs={24} sm={12} lg={8}>
          <Card style={{ background: '#0F1117', border: '1px solid #1E222E' }}>
            <Statistic
              title={<span style={{ color: '#9CA3AF' }}>活跃用户</span>}
              value={stats?.active_users || 0}
              prefix={<UserOutlined style={{ color: '#8B5CF6' }} />}
              styles={{ value: { color: '#F3F4F6' } }}
            />
          </Card>
        </Col>

        <Col xs={24} sm={12} lg={8}>
          <Card style={{ background: '#0F1117', border: '1px solid #1E222E' }}>
            <Statistic
              title={<span style={{ color: '#9CA3AF' }}>错误率</span>}
              value={stats?.error_rate || 0}
              suffix="%"
              precision={1}
              prefix={<CloudOutlined style={{ color: '#F87171' }} />}
              styles={{ value: { color: '#F3F4F6' } }}
            />
          </Card>
        </Col>
      </Row>

      <Card 
        title={<span style={{ color: '#F3F4F6', fontSize: 16, fontWeight: 600 }}>实时QPS</span>}
        style={{ 
          marginTop: 24,
          background: '#0F1117', 
          border: '1px solid #1E222E',
        }}
      >
        <div id="qps-chart" style={{ height: 400 }} />
      </Card>
    </div>
  );
}

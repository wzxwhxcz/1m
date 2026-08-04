import { useEffect, useState } from 'react';
import { Card, Row, Col, Spin, App } from 'antd';
import * as echarts from 'echarts';
import { statsApi } from '../api/client';
import type { TrendData } from '../types';

export default function StatisticsPage() {
  const { message } = App.useApp();
  const [loading, setLoading] = useState(true);
  const [trendData, setTrendData] = useState<TrendData[]>([]);

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (trendData.length > 0) {
      renderTrendChart();
      renderSuccessRateChart();
    }
  }, [trendData]);

  const loadData = async () => {
    try {
      const response = await statsApi.trend(7);
      setTrendData(response.data);
    } catch (error) {
      message.error('加载统计数据失败');
    } finally {
      setLoading(false);
    }
  };

  const renderTrendChart = () => {
    const chartDom = document.getElementById('trend-chart');
    if (!chartDom) return;

    const chart = echarts.init(chartDom);
    const option = {
      backgroundColor: 'transparent',
      grid: { left: 50, right: 20, top: 30, bottom: 30 },
      xAxis: {
        type: 'category',
        data: trendData.map(d => d.date),
        axisLine: { lineStyle: { color: '#374151' } },
        axisLabel: { color: '#9CA3AF' },
      },
      yAxis: {
        type: 'value',
        name: '请求数',
        nameTextStyle: { color: '#9CA3AF' },
        axisLine: { lineStyle: { color: '#374151' } },
        axisLabel: { color: '#9CA3AF' },
        splitLine: { lineStyle: { color: '#1E222E' } },
      },
      series: [{
        type: 'bar',
        data: trendData.map(d => d.requests),
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#5B8CFF' },
            { offset: 1, color: '#3B82F6' }
          ]),
          borderRadius: [4, 4, 0, 0],
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

  const renderSuccessRateChart = () => {
    const chartDom = document.getElementById('success-rate-chart');
    if (!chartDom) return;

    const chart = echarts.init(chartDom);
    const option = {
      backgroundColor: 'transparent',
      grid: { left: 50, right: 20, top: 30, bottom: 30 },
      xAxis: {
        type: 'category',
        data: trendData.map(d => d.date),
        axisLine: { lineStyle: { color: '#374151' } },
        axisLabel: { color: '#9CA3AF' },
      },
      yAxis: {
        type: 'value',
        name: '成功率 (%)',
        min: 0,
        max: 100,
        nameTextStyle: { color: '#9CA3AF' },
        axisLine: { lineStyle: { color: '#374151' } },
        axisLabel: { color: '#9CA3AF' },
        splitLine: { lineStyle: { color: '#1E222E' } },
      },
      series: [{
        type: 'line',
        data: trendData.map(d => d.success_rate),
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        lineStyle: { color: '#10B981', width: 2 },
        itemStyle: { color: '#10B981' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(16, 185, 129, 0.3)' },
            { offset: 1, color: 'rgba(16, 185, 129, 0)' }
          ])
        },
      }],
      tooltip: {
        trigger: 'axis',
        backgroundColor: '#1E222E',
        borderColor: '#374151',
        textStyle: { color: '#F3F4F6' },
        formatter: (params: any) => {
          const data = params[0];
          return `${data.name}<br/>${data.seriesName}: ${data.value.toFixed(1)}%`;
        },
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
        统计分析
      </h1>

      <Row gutter={[16, 16]}>
        <Col xs={24}>
          <Card
            title={<span style={{ color: '#F3F4F6', fontSize: 16, fontWeight: 600 }}>
              请求趋势（近7天）
            </span>}
            style={{ background: '#171A23', border: '1px solid #1E222E' }}
          >
            <div id="trend-chart" style={{ height: 400 }} />
          </Card>
        </Col>

        <Col xs={24}>
          <Card
            title={<span style={{ color: '#F3F4F6', fontSize: 16, fontWeight: 600 }}>
              成功率趋势（近7天）
            </span>}
            style={{ background: '#171A23', border: '1px solid #1E222E' }}
          >
            <div id="success-rate-chart" style={{ height: 400 }} />
          </Card>
        </Col>
      </Row>
    </div>
  );
}

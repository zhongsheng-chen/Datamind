// datamind/static/js/charts.js

// 图表管理模块
const ChartManager = {
    charts: {},

    // 初始化所有图表
    init: function() {
        this.initCallsChart();
        this.initModelTypeChart();
        this.initPerformanceChart();
        this.initResponseTimeChart();
        this.initModelDistributionChart();
    },

    // 初始化调用趋势图表
    initCallsChart: function() {
        const chartDom = document.getElementById('callsChart');
        if (!chartDom) return;

        this.charts.callsChart = echarts.init(chartDom);

        // 从data属性获取数据
        const dates = JSON.parse(chartDom.dataset.dates || '[]');
        const scoringData = JSON.parse(chartDom.dataset.scoring || '[]');
        const fraudData = JSON.parse(chartDom.dataset.fraud || '[]');

        const option = {
            title: {
                text: '近7天调用趋势',
                left: 'center',
                top: 0
            },
            tooltip: {
                trigger: 'axis',
                axisPointer: {
                    type: 'shadow'
                }
            },
            legend: {
                data: ['评分卡', '反欺诈'],
                bottom: 0,
                left: 'center'
            },
            grid: {
                left: '3%',
                right: '4%',
                bottom: '15%',
                top: '15%',
                containLabel: true
            },
            xAxis: {
                type: 'category',
                data: dates,
                axisLabel: {
                    rotate: 0,
                    interval: 0
                }
            },
            yAxis: {
                type: 'value',
                name: '调用次数',
                nameLocation: 'middle',
                nameGap: 40
            },
            series: [
                {
                    name: '评分卡',
                    type: 'bar',
                    data: scoringData,
                    itemStyle: {
                        color: '#4361ee',
                        borderRadius: [4, 4, 0, 0]
                    },
                    barWidth: 20,
                    label: {
                        show: true,
                        position: 'top',
                        color: '#4361ee'
                    }
                },
                {
                    name: '反欺诈',
                    type: 'bar',
                    data: fraudData,
                    itemStyle: {
                        color: '#06d6a0',
                        borderRadius: [4, 4, 0, 0]
                    },
                    barWidth: 20,
                    label: {
                        show: true,
                        position: 'top',
                        color: '#06d6a0'
                    }
                }
            ]
        };

        this.charts.callsChart.setOption(option);

        // 响应式
        window.addEventListener('resize', () => {
            this.charts.callsChart.resize();
        });
    },

    // 初始化模型类型分布图表
    initModelTypeChart: function() {
        const chartDom = document.getElementById('modelTypeChart');
        if (!chartDom) return;

        this.charts.modelTypeChart = echarts.init(chartDom);

        // 从data属性获取数据
        const data = JSON.parse(chartDom.dataset.types || '[]');

        const option = {
            title: {
                text: '模型类型分布',
                left: 'center',
                top: 0
            },
            tooltip: {
                trigger: 'item',
                formatter: '{a} <br/>{b}: {c} ({d}%)'
            },
            legend: {
                orient: 'vertical',
                left: 'left',
                top: 'center'
            },
            series: [
                {
                    name: '模型类型',
                    type: 'pie',
                    radius: ['40%', '70%'],
                    center: ['60%', '50%'],
                    avoidLabelOverlap: false,
                    itemStyle: {
                        borderRadius: 10,
                        borderColor: '#fff',
                        borderWidth: 2
                    },
                    label: {
                        show: false
                    },
                    emphasis: {
                        label: {
                            show: true,
                            fontSize: '12',
                            fontWeight: 'bold'
                        }
                    },
                    data: data,
                    color: ['#4361ee', '#06d6a0', '#ffb703', '#ef476f', '#4cc9f0', '#2b2d42']
                }
            ]
        };

        this.charts.modelTypeChart.setOption(option);
    },

    // 初始化性能图表
    initPerformanceChart: function() {
        const chartDom = document.getElementById('performanceChart');
        if (!chartDom) return;

        this.charts.performanceChart = echarts.init(chartDom);

        const times = JSON.parse(chartDom.dataset.times || '[]');
        const responseData = JSON.parse(chartDom.dataset.response || '[]');

        const option = {
            title: {
                text: '响应时间趋势',
                left: 'center'
            },
            tooltip: {
                trigger: 'axis'
            },
            xAxis: {
                type: 'category',
                data: times,
                axisLabel: {
                    rotate: 30
                }
            },
            yAxis: {
                type: 'value',
                name: '响应时间 (ms)'
            },
            series: [
                {
                    name: '平均响应时间',
                    type: 'line',
                    data: responseData,
                    smooth: true,
                    lineStyle: {
                        color: '#4361ee',
                        width: 3
                    },
                    areaStyle: {
                        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                            { offset: 0, color: 'rgba(67, 97, 238, 0.3)' },
                            { offset: 1, color: 'rgba(67, 97, 238, 0.01)' }
                        ])
                    },
                    symbol: 'circle',
                    symbolSize: 8
                }
            ]
        };

        this.charts.performanceChart.setOption(option);
    },

    // 初始化响应时间分布图表
    initResponseTimeChart: function() {
        const chartDom = document.getElementById('responseTimeChart');
        if (!chartDom) return;

        this.charts.responseTimeChart = echarts.init(chartDom);

        const data = JSON.parse(chartDom.dataset.distribution || '[]');

        const option = {
            title: {
                text: '响应时间分布',
                left: 'center'
            },
            tooltip: {
                trigger: 'axis',
                axisPointer: {
                    type: 'shadow'
                }
            },
            grid: {
                left: '3%',
                right: '4%',
                bottom: '3%',
                containLabel: true
            },
            xAxis: {
                type: 'category',
                data: data.map(d => d.range),
                axisLabel: {
                    rotate: 30
                }
            },
            yAxis: {
                type: 'value',
                name: '请求数'
            },
            series: [
                {
                    name: '请求数',
                    type: 'bar',
                    data: data.map(d => d.count),
                    itemStyle: {
                        color: '#4361ee',
                        borderRadius: [4, 4, 0, 0]
                    },
                    label: {
                        show: true,
                        position: 'top',
                        color: '#4361ee'
                    }
                }
            ]
        };

        this.charts.responseTimeChart.setOption(option);
    },

    // 初始化模型分布图表
    initModelDistributionChart: function() {
        const chartDom = document.getElementById('modelDistributionChart');
        if (!chartDom) return;

        this.charts.modelDistributionChart = echarts.init(chartDom);

        const data = JSON.parse(chartDom.dataset.distribution || '[]');

        const option = {
            title: {
                text: '模型状态分布',
                left: 'center'
            },
            tooltip: {
                trigger: 'item',
                formatter: '{a} <br/>{b}: {c} ({d}%)'
            },
            series: [
                {
                    name: '模型状态',
                    type: 'pie',
                    radius: ['50%', '70%'],
                    data: data,
                    color: ['#06d6a0', '#ffb703', '#ef476f', '#2b2d42'],
                    label: {
                        show: true,
                        formatter: '{b}: {d}%'
                    },
                    emphasis: {
                        scale: true
                    }
                }
            ]
        };

        this.charts.modelDistributionChart.setOption(option);
    },

    // 更新图表数据
    updateCharts: function(data) {
        if (this.charts.callsChart) {
            this.charts.callsChart.setOption({
                xAxis: { data: data.dates },
                series: [
                    { data: data.scoring },
                    { data: data.fraud }
                ]
            });
        }

        if (this.charts.modelTypeChart) {
            this.charts.modelTypeChart.setOption({
                series: [{ data: data.modelTypes }]
            });
        }

        if (this.charts.performanceChart) {
            this.charts.performanceChart.setOption({
                xAxis: { data: data.times },
                series: [{ data: data.responseTimes }]
            });
        }
    },

    // 销毁所有图表
    destroy: function() {
        Object.values(this.charts).forEach(chart => {
            if (chart) {
                chart.dispose();
            }
        });
        this.charts = {};
    }
};

// 自动初始化
$(document).ready(function() {
    // 等待DOM完全加载
    setTimeout(() => {
        ChartManager.init();
    }, 100);
});

// 页面卸载时销毁图表
$(window).on('unload', function() {
    ChartManager.destroy();
});
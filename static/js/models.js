// datamind/static/js/models.js

// 模型管理模块
const ModelManager = {
    // 初始化
    init: function() {
        this.bindEvents();
        this.loadModelStats();
    },

    // 绑定事件
    bindEvents: function() {
        // 筛选表单提交
        $('#filterForm').on('submit', (e) => {
            e.preventDefault();
            this.filterModels();
        });

        // 筛选条件变化
        $('#taskType, #status, #framework, #isProduction').on('change', () => {
            this.filterModels();
        });

        // 搜索输入防抖
        let searchTimer;
        $('#searchInput').on('input', () => {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(() => this.filterModels(), 300);
        });

        // 模型操作按钮
        $(document).on('click', '.activate-btn', function() {
            const modelId = $(this).data('id');
            ModelManager.activateModel(modelId);
        });

        $(document).on('click', '.deactivate-btn', function() {
            const modelId = $(this).data('id');
            ModelManager.deactivateModel(modelId);
        });

        $(document).on('click', '.promote-btn', function() {
            const modelId = $(this).data('id');
            ModelManager.promoteModel(modelId);
        });

        $(document).on('click', '.load-btn', function() {
            const modelId = $(this).data('id');
            ModelManager.loadModel(modelId);
        });

        $(document).on('click', '.unload-btn', function() {
            const modelId = $(this).data('id');
            ModelManager.unloadModel(modelId);
        });

        $(document).on('click', '.delete-btn', function() {
            const modelId = $(this).data('id');
            ModelManager.deleteModel(modelId);
        });
    },

    // 加载模型统计
    loadModelStats: function() {
        api.get('/models/stats')
            .then(data => {
                $('#totalModels').text(data.total || 0);
                $('#activeModels').text(data.active || 0);
                $('#productionModels').text(data.production || 0);
                $('#loadedModels').text(data.loaded || 0);
            })
            .catch(error => utils.handleError(error));
    },

    // 筛选模型
    filterModels: function() {
        const filters = {
            task_type: $('#taskType').val(),
            status: $('#status').val(),
            framework: $('#framework').val(),
            is_production: $('#isProduction').val() === 'true' ? true :
                           $('#isProduction').val() === 'false' ? false : null,
            search: $('#searchInput').val()
        };

        // 移除空值
        Object.keys(filters).forEach(key => {
            if (filters[key] === null || filters[key] === '') {
                delete filters[key];
            }
        });

        this.renderModelList(filters);
    },

    // 渲染模型列表
    renderModelList: function(filters = {}) {
        const params = new URLSearchParams(filters);

        $('#modelTableBody').html(`
            <tr>
                <td colspan="9" class="text-center py-4">
                    <div class="spinner-border spinner-border-sm text-primary me-2"></div>
                    加载中...
                </td>
            </tr>
        `);

        api.get(`/models?${params.toString()}`)
            .then(data => {
                if (data.models.length === 0) {
                    $('#modelTableBody').html(`
                        <tr>
                            <td colspan="9" class="text-center text-muted py-4">
                                <i class="fas fa-inbox fa-2x mb-2"></i>
                                <p>暂无模型数据</p>
                            </td>
                        </tr>
                    `);
                    return;
                }

                let html = '';
                data.models.forEach(model => {
                    html += this.renderModelRow(model);
                });
                $('#modelTableBody').html(html);

                // 更新统计
                $('#totalModels').text(data.total || data.models.length);
            })
            .catch(error => {
                $('#modelTableBody').html(`
                    <tr>
                        <td colspan="9" class="text-center text-danger py-4">
                            <i class="fas fa-exclamation-circle fa-2x mb-2"></i>
                            <p>加载失败: ${error.message}</p>
                        </td>
                    </tr>
                `);
            });
    },

    // 渲染模型行
    renderModelRow: function(model) {
        const statusBadge = this.getStatusBadge(model.status);
        const taskTypeBadge = this.getTaskTypeBadge(model.task_type);
        const productionStar = model.is_production ?
            '<span class="badge bg-warning text-dark ms-1" title="生产模型">⭐</span>' : '';
        const loadedBadge = model.is_loaded ?
            '<span class="badge bg-info ms-1" title="已加载内存">📦</span>' : '';

        return `
            <tr>
                <td>
                    ${statusBadge}
                    ${productionStar}
                    ${loadedBadge}
                </td>
                <td>
                    <a href="/ui/models/${model.model_id}" class="fw-bold text-primary">
                        ${model.model_name}
                    </a>
                </td>
                <td><span class="badge bg-secondary">v${model.model_version}</span></td>
                <td>${taskTypeBadge}</td>
                <td>${this.formatModelType(model.model_type)}</td>
                <td>${this.formatFramework(model.framework)}</td>
                <td>${utils.formatDate(model.created_at)}</td>
                <td>${model.created_by}</td>
                <td>
                    <div class="btn-group btn-group-sm">
                        <a href="/ui/models/${model.model_id}" class="btn btn-outline-info" title="详情">
                            <i class="fas fa-eye"></i>
                        </a>
                        ${this.getActionButtons(model)}
                    </div>
                </td>
            </tr>
        `;
    },

    // 获取状态徽章
    getStatusBadge: function(status) {
        const badges = {
            'active': '<span class="badge bg-success" title="已激活">✅</span>',
            'inactive': '<span class="badge bg-secondary" title="未激活">⏸️</span>',
            'deprecated': '<span class="badge bg-danger" title="已废弃">⚠️</span>',
            'archived': '<span class="badge bg-dark" title="已归档">📦</span>'
        };
        return badges[status] || '<span class="badge bg-secondary">❓</span>';
    },

    // 获取任务类型徽章
    getTaskTypeBadge: function(taskType) {
        const badges = {
            'scoring': '<span class="badge bg-primary">评分卡</span>',
            'fraud_detection': '<span class="badge bg-danger">反欺诈</span>'
        };
        return badges[taskType] || '<span class="badge bg-secondary">未知</span>';
    },

    // 格式化模型类型
    formatModelType: function(type) {
        const types = {
            'decision_tree': '决策树',
            'random_forest': '随机森林',
            'xgboost': 'XGBoost',
            'lightgbm': 'LightGBM',
            'logistic_regression': '逻辑回归',
            'catboost': 'CatBoost',
            'neural_network': '神经网络'
        };
        return types[type] || type;
    },

    // 格式化框架
    formatFramework: function(framework) {
        const frameworks = {
            'sklearn': 'Scikit-learn',
            'xgboost': 'XGBoost',
            'lightgbm': 'LightGBM',
            'torch': 'PyTorch',
            'tensorflow': 'TensorFlow',
            'onnx': 'ONNX',
            'catboost': 'CatBoost'
        };
        return frameworks[framework] || framework;
    },

    // 获取操作按钮
    getActionButtons: function(model) {
        let buttons = '';

        if (model.status === 'inactive') {
            buttons += `<button class="btn btn-outline-success activate-btn" data-id="${model.model_id}" title="激活">
                <i class="fas fa-play"></i>
            </button>`;
        } else {
            buttons += `<button class="btn btn-outline-warning deactivate-btn" data-id="${model.model_id}" title="停用">
                <i class="fas fa-pause"></i>
            </button>`;
        }

        if (!model.is_production && model.status === 'active') {
            buttons += `<button class="btn btn-outline-primary promote-btn" data-id="${model.model_id}" title="设为生产">
                <i class="fas fa-star"></i>
            </button>`;
        }

        if (!model.is_loaded) {
            buttons += `<button class="btn btn-outline-secondary load-btn" data-id="${model.model_id}" title="加载内存">
                <i class="fas fa-download"></i>
            </button>`;
        } else {
            buttons += `<button class="btn btn-outline-danger unload-btn" data-id="${model.model_id}" title="卸载内存">
                <i class="fas fa-upload"></i>
            </button>`;
        }

        buttons += `<button class="btn btn-outline-danger delete-btn" data-id="${model.model_id}" title="删除">
            <i class="fas fa-trash"></i>
        </button>`;

        return buttons;
    },

    // 激活模型
    activateModel: function(modelId) {
        utils.confirm('确定要激活此模型吗？').then(confirmed => {
            if (confirmed) {
                api.post(`/models/${modelId}/activate`, {})
                    .then(data => {
                        if (data.success) {
                            utils.showToast('模型激活成功');
                            setTimeout(() => location.reload(), 1000);
                        }
                    })
                    .catch(error => utils.handleError(error));
            }
        });
    },

    // 停用模型
    deactivateModel: function(modelId) {
        utils.confirm('确定要停用此模型吗？').then(confirmed => {
            if (confirmed) {
                api.post(`/models/${modelId}/deactivate`, {})
                    .then(data => {
                        if (data.success) {
                            utils.showToast('模型已停用');
                            setTimeout(() => location.reload(), 1000);
                        }
                    })
                    .catch(error => utils.handleError(error));
            }
        });
    },

    // 设为生产模型
    promoteModel: function(modelId) {
        utils.confirm('确定要将此模型设为生产模型吗？\n这将自动停用其他同类型的生产模型。').then(confirmed => {
            if (confirmed) {
                api.post(`/models/${modelId}/promote`, {})
                    .then(data => {
                        if (data.success) {
                            utils.showToast('已设为生产模型');
                            setTimeout(() => location.reload(), 1000);
                        }
                    })
                    .catch(error => utils.handleError(error));
            }
        });
    },

    // 加载模型到内存
    loadModel: function(modelId) {
        api.post(`/models/${modelId}/load`, {})
            .then(data => {
                if (data.success) {
                    utils.showToast('模型加载成功');
                    setTimeout(() => location.reload(), 1000);
                }
            })
            .catch(error => utils.handleError(error));
    },

    // 从内存卸载模型
    unloadModel: function(modelId) {
        utils.confirm('确定要从内存中卸载此模型吗？').then(confirmed => {
            if (confirmed) {
                api.post(`/models/${modelId}/unload`, {})
                    .then(data => {
                        if (data.success) {
                            utils.showToast('模型已卸载');
                            setTimeout(() => location.reload(), 1000);
                        }
                    })
                    .catch(error => utils.handleError(error));
            }
        });
    },

    // 删除模型
    deleteModel: function(modelId) {
        utils.confirm('确定要删除此模型吗？\n此操作不可恢复！', '警告').then(confirmed => {
            if (confirmed) {
                api.delete(`/models/${modelId}`)
                    .then(data => {
                        if (data.success) {
                            utils.showToast('模型已删除');
                            setTimeout(() => location.reload(), 1000);
                        }
                    })
                    .catch(error => utils.handleError(error));
            }
        });
    }
};

// 初始化
$(document).ready(function() {
    ModelManager.init();
});
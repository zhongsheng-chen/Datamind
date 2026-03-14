// datamind/static/js/register.js

// 模型注册模块
const RegisterManager = {
    // 初始化
    init: function() {
        this.bindEvents();
        this.loadModelTypes();
        this.setupValidation();
        this.setupPreview();
    },

    // 绑定事件
    bindEvents: function() {
        // 任务类型变化时更新模型类型选项
        $('#taskType').on('change', () => this.loadModelTypes());

        // 框架变化时更新模型类型选项
        $('#framework').on('change', () => this.loadModelTypes());

        // 表单提交
        $('#registerForm').on('submit', (e) => {
            e.preventDefault();
            this.submitForm();
        });

        // 文件选择
        $('#modelFile').on('change', (e) => this.handleFileSelect(e));

        // JSON编辑器变化
        $('#inputFeatures, #outputSchema, #modelParams, #tags').on('input', () => {
            this.validateJSON();
        });

        // 预览按钮
        $('#previewBtn').on('click', () => this.showPreview());

        // 清空按钮
        $('#clearBtn').on('click', () => this.clearForm());
    },

    // 设置表单验证
    setupValidation: function() {
        // 自定义验证规则
        $.validator.addMethod('json', function(value, element) {
            if (!value) return true;
            try {
                JSON.parse(value);
                return true;
            } catch (e) {
                return false;
            }
        }, '请输入有效的JSON格式');

        $('#registerForm').validate({
            rules: {
                model_name: {
                    required: true,
                    minlength: 2,
                    maxlength: 100,
                    pattern: /^[a-z0-9_]+$/
                },
                model_version: {
                    required: true,
                    pattern: /^\d+\.\d+\.\d+$/
                },
                task_type: {
                    required: true
                },
                model_type: {
                    required: true
                },
                framework: {
                    required: true
                },
                model_file: {
                    required: true,
                    extension: 'pkl|json|txt|pt|h5|onnx|cbm|bin'
                },
                input_features: {
                    required: true,
                    json: true
                },
                output_schema: {
                    required: true,
                    json: true
                },
                model_params: {
                    json: true
                },
                tags: {
                    json: true
                }
            },
            messages: {
                model_name: {
                    required: '请输入模型名称',
                    minlength: '模型名称至少2个字符',
                    maxlength: '模型名称不能超过100个字符',
                    pattern: '只能包含小写字母、数字和下划线'
                },
                model_version: {
                    required: '请输入版本号',
                    pattern: '版本号格式应为 x.y.z (如 1.0.0)'
                },
                model_file: {
                    required: '请选择模型文件',
                    extension: '不支持的文件类型'
                },
                input_features: '请输入有效的JSON数组',
                output_schema: '请输入有效的JSON对象'
            },
            errorElement: 'div',
            errorClass: 'invalid-feedback',
            highlight: function(element) {
                $(element).addClass('is-invalid');
            },
            unhighlight: function(element) {
                $(element).removeClass('is-invalid');
            }
        });
    },

    // 设置预览功能
    setupPreview: function() {
        // 实时预览示例特征
        $('#exampleFeatures').on('input', () => {
            this.updatePreview();
        });
    },

    // 加载模型类型选项
    loadModelTypes: function() {
        const taskType = $('#taskType').val();
        const framework = $('#framework').val();

        if (!taskType || !framework) {
            $('#modelType').html('<option value="">请先选择任务类型和框架</option>');
            return;
        }

        api.get(`/models/types/model?framework=${framework}`)
            .then(data => {
                let options = '<option value="">请选择模型类型</option>';
                data.model_types.forEach(type => {
                    options += `<option value="${type.value}">${type.name}</option>`;
                });
                $('#modelType').html(options);
            })
            .catch(error => {
                utils.showToast('加载模型类型失败', 'danger');
            });
    },

    // 处理文件选择
    handleFileSelect: function(e) {
        const file = e.target.files[0];
        if (!file) return;

        // 显示文件信息
        const fileSize = (file.size / 1024 / 1024).toFixed(2);
        $('#fileInfo').html(`
            <div class="alert alert-info mt-2">
                <i class="fas fa-file me-2"></i>
                ${file.name} (${fileSize} MB)
            </div>
        `);

        // 检查文件大小
        const maxSize = $('#maxFileSize').data('max-size') || 1024;
        if (file.size > maxSize * 1024 * 1024) {
            utils.showToast(`文件大小不能超过 ${maxSize}MB`, 'danger');
            $('#modelFile').val('');
            $('#fileInfo').empty();
        }
    },

    // 验证JSON
    validateJSON: function() {
        const fields = ['inputFeatures', 'outputSchema', 'modelParams', 'tags'];
        fields.forEach(field => {
            const $field = $(`#${field}`);
            const value = $field.val();
            if (value) {
                try {
                    JSON.parse(value);
                    $field.removeClass('is-invalid').addClass('is-valid');
                } catch (e) {
                    $field.removeClass('is-valid').addClass('is-invalid');
                }
            } else {
                $field.removeClass('is-valid is-invalid');
            }
        });
    },

    // 显示预览
    showPreview: function() {
        const formData = {
            model_name: $('#modelName').val(),
            model_version: $('#modelVersion').val(),
            task_type: $('#taskType').find('option:selected').text(),
            model_type: $('#modelType').find('option:selected').text(),
            framework: $('#framework').find('option:selected').text(),
            description: $('#description').val(),
            input_features: this.parseJSON($('#inputFeatures').val(), []),
            output_schema: this.parseJSON($('#outputSchema').val(), {}),
            model_params: this.parseJSON($('#modelParams').val(), {}),
            tags: this.parseJSON($('#tags').val(), {})
        };

        const previewHtml = `
            <div class="mb-3">
                <h6>基本信息</h6>
                <table class="table table-sm">
                    <tr><th>模型名称</th><td>${formData.model_name || '-'}</td></tr>
                    <tr><th>版本</th><td>${formData.model_version || '-'}</td></tr>
                    <tr><th>任务类型</th><td>${formData.task_type || '-'}</td></tr>
                    <tr><th>模型类型</th><td>${formData.model_type || '-'}</td></tr>
                    <tr><th>框架</th><td>${formData.framework || '-'}</td></tr>
                    <tr><th>描述</th><td>${formData.description || '-'}</td></tr>
                </table>
            </div>
            <div class="mb-3">
                <h6>输入特征 (${formData.input_features.length})</h6>
                <div class="feature-badge-container">
                    ${formData.input_features.map(f => 
                        `<span class="feature-badge">${f}</span>`
                    ).join('')}
                </div>
            </div>
            <div class="mb-3">
                <h6>输出格式</h6>
                <pre class="json-viewer">${JSON.stringify(formData.output_schema, null, 2)}</pre>
            </div>
        `;

        $('#previewContent').html(previewHtml);
        new bootstrap.Modal(document.getElementById('previewModal')).show();
    },

    // 更新预览
    updatePreview: function() {
        // 实时预览逻辑
    },

    // 提交表单
    submitForm: function() {
        if (!$('#registerForm').valid()) {
            utils.showToast('请填写所有必填项', 'warning');
            return;
        }

        const formData = new FormData();
        formData.append('model_name', $('#modelName').val());
        formData.append('model_version', $('#modelVersion').val());
        formData.append('task_type', $('#taskType').val());
        formData.append('model_type', $('#modelType').val());
        formData.append('framework', $('#framework').val());
        formData.append('description', $('#description').val());
        formData.append('input_features', $('#inputFeatures').val());
        formData.append('output_schema', $('#outputSchema').val());
        formData.append('model_params', $('#modelParams').val() || '{}');
        formData.append('tags', $('#tags').val() || '{}');
        formData.append('model_file', $('#modelFile')[0].files[0]);

        // 显示进度
        this.showProgress();

        api.upload('/models/register', formData)
            .then(data => {
                if (data.success) {
                    this.hideProgress();
                    utils.showToast('模型注册成功');

                    // 显示成功对话框
                    $('#successModelId').text(data.model_id);
                    $('#successModelName').text(data.model_name);
                    $('#successModelVersion').text(data.model_version);
                    new bootstrap.Modal(document.getElementById('successModal')).show();

                    // 清空表单
                    this.clearForm();
                }
            })
            .catch(error => {
                this.hideProgress();
                utils.handleError(error);
            });
    },

    // 显示上传进度
    showProgress: function() {
        const progressModal = new bootstrap.Modal(document.getElementById('progressModal'));
        progressModal.show();

        let progress = 0;
        const interval = setInterval(() => {
            progress += 5;
            if (progress <= 90) {
                $('#progressBar').css('width', progress + '%').text(progress + '%');
            }
            if (progress >= 90) {
                clearInterval(interval);
            }
        }, 200);

        // 保存interval以便清除
        this.progressInterval = interval;
    },

    // 隐藏进度
    hideProgress: function() {
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
        }
        $('#progressBar').css('width', '100%').text('100%');
        setTimeout(() => {
            bootstrap.Modal.getInstance(document.getElementById('progressModal')).hide();
            $('#progressBar').css('width', '0%').text('0%');
        }, 500);
    },

    // 清空表单
    clearForm: function() {
        $('#registerForm')[0].reset();
        $('#fileInfo').empty();
        $('.is-valid, .is-invalid').removeClass('is-valid is-invalid');
    },

    // 解析JSON
    parseJSON: function(str, defaultValue) {
        if (!str) return defaultValue;
        try {
            return JSON.parse(str);
        } catch (e) {
            return defaultValue;
        }
    }
};

// 初始化
$(document).ready(function() {
    RegisterManager.init();
});
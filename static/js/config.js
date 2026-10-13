// static/js/config.js
// 配置页面JavaScript

// 监控类型配置模板
const configTemplates = {
    cpu: {
        target: { type: 'hidden', value: 'system' },
        threshold: [
            { name: 'warning', label: '警告阈值(%)', type: 'number', default: 80 },
            { name: 'critical', label: '严重阈值(%)', type: 'number', default: 90 }
        ]
    },
    memory: {
        target: { type: 'hidden', value: 'system' },
        threshold: [
            { name: 'warning', label: '警告阈值(%)', type: 'number', default: 80 },
            { name: 'critical', label: '严重阈值(%)', type: 'number', default: 90 }
        ]
    },
    disk: {
        target: { 
            type: 'select', 
            label: '挂载点', 
            options: [],  // 动态填充
            default: '/' 
        },
        threshold: [
            { name: 'warning', label: '警告阈值(%)', type: 'number', default: 80 },
            { name: 'critical', label: '严重阈值(%)', type: 'number', default: 90 }
        ]
    },
    network: {
        target: { 
            type: 'select', 
            label: '网络接口', 
            options: [],  // 动态填充
            default: '' 
        },
        threshold: [
            { name: 'warning', label: '警告阈值(B/s)', type: 'number', default: 1000000 },
            { name: 'critical', label: '严重阈值(B/s)', type: 'number', default: 5000000 }
        ]
    },
    ssl: {
        target: { type: 'text', label: '域名', placeholder: 'example.com', default: '' },
        threshold: [
            { name: 'warning_days', label: '警告天数', type: 'number', default: 30 },
            { name: 'critical_days', label: '严重天数', type: 'number', default: 7 }
        ]
    },
    api: {
        target: { type: 'text', label: 'API地址', placeholder: 'https://api.example.com/health', default: '' },
        threshold: [
            { name: 'expected_status', label: '期望状态码', type: 'number', default: 200 },
            { name: 'timeout', label: '超时时间(秒)', type: 'number', default: 10 },
            { name: 'max_response_time', label: '最大响应时间(秒)', type: 'number', default: 5 }
        ],
        extra: [
            { name: 'method', label: '请求方法', type: 'select', options: ['GET', 'POST', 'PUT', 'DELETE'], default: 'GET' },
            { 
                name: 'headers', 
                label: '请求头(JSON)', 
                type: 'textarea', 
                placeholder: '{"Content-Type": "application/json"}', 
                default: '',
                formText: '请输入有效的JSON格式，例如: {"Content-Type": "application/json", "Authorization": "Bearer token"}'
            }
        ]
    },
    component: {
        target: { type: 'select', label: '组件类型', options: ['redis', 'rabbitmq'], default: 'redis' },
        extra: [
            { name: 'host', label: '主机', type: 'text', default: 'localhost' },
            { name: 'port', label: '端口', type: 'number', default: '' },
            { name: 'username', label: '用户名', type: 'text', default: '' },
            { name: 'password', label: '密码', type: 'password', default: '' }
        ]
    }
};

let editModalInstance = null;

// 初始化配置表单
function initConfigForms() {
    // 初始化添加配置模态框
    initAddConfigModal();

    // 初始化编辑配置模态框
    initEditConfigModal();
    
    // 添加磁盘刷新按钮
    addDiskRefreshButton();    

    // 监控类型变化事件
    /*
    document.querySelectorAll('select[name="type"]').forEach(select => {
        select.addEventListener('change', function() {
            updateConfigForm(this);
        });
    });
    */
    // 移除原来的事件绑定代码，现在使用全局事件委托
    
    // 项目名称表单提交
    document.getElementById('project-name-form').addEventListener('submit', function(e) {
        e.preventDefault();
        updateProjectName();
    });

    // 邮箱配置表单提交
    document.getElementById('email-config-form').addEventListener('submit', function(e) {
        e.preventDefault();
        saveEmailConfig();
    });
    
    // 添加配置表单提交
    document.getElementById('add-config-form').addEventListener('submit', function(e) {
        e.preventDefault();
        saveMonitorConfig('add');
    });
    
    // 编辑配置表单提交
    document.getElementById('edit-config-form').addEventListener('submit', function(e) {
        e.preventDefault();
        saveMonitorConfig('edit');
    });
    
    // 切换开关事件
    document.querySelectorAll('.toggle-switch').forEach(switchEl => {
        switchEl.addEventListener('change', function() {
            toggleMonitorConfig(this.dataset.configId, this.checked);
        });
    });
    
    // 删除配置事件
    document.querySelectorAll('.delete-config').forEach(button => {
        button.addEventListener('click', function() {
            deleteMonitorConfig(this.dataset.configId, this.dataset.configName);
        });
    });
    
    // 编辑配置事件
    document.querySelectorAll('.edit-config').forEach(button => {
        button.addEventListener('click', function() {
            loadConfigForEdit(this.dataset.configId);
        });
    });
    
    // 邮箱配置表单提交前的验证
    document.getElementById('email-config-form').addEventListener('submit', function(e) {
        if (!validateEmailConfig()) {
            e.preventDefault();
            showMessage('请修正表单中的错误', 'error');
        }
    });
    
    // 实时验证邮箱格式
    document.querySelectorAll('#email-config-form input[type="email"], #email-config-form input[name="receivers"]').forEach(input => {
        input.addEventListener('blur', function() {
            validateEmailConfig();
        });
    });
	
	// 监听模态框显示事件，添加 JSON 验证
    document.addEventListener('shown.bs.modal', function(e) {
        if (e.target.id === 'addConfigModal' || e.target.id === 'editConfigModal') {
            setupJsonValidation();
        }
    });
	
}

// 在 config.js 中添加刷新磁盘分区的函数
async function refreshDiskPartitions() {
    try {
        const response = await fetch('/api/disk-partitions');
        const result = await response.json();
        
        if (result.success) {
            // 更新全局磁盘分区信息
            window.diskPartitions = result.data;
            showMessage(`刷新成功，找到 ${result.data.length} 个磁盘分区`, 'success');
            
            // 如果当前正在编辑或添加磁盘监控，刷新表单
            const activeModal = document.querySelector('.modal.show');
            if (activeModal) {
                const typeSelect = activeModal.querySelector('select[name="type"]');
                if (typeSelect && typeSelect.value === 'disk') {
                    updateConfigForm(typeSelect);
                }
            }
        } else {
            showMessage('刷新磁盘分区失败: ' + (result.error || '未知错误'), 'error');
        }
    } catch (error) {
        handleAjaxError(error);
    }
}

// 在 config.js 中添加刷新网络接口的函数
async function refreshNetworkInterfaces() {
    try {
        const response = await fetch('/api/network-interfaces');
        const result = await response.json();
        
        if (result.success) {
            // 更新全局网络接口信息
            window.networkInterfaces = result.data;
            showMessage(`刷新成功，找到 ${result.data.length} 个网络接口`, 'success');
            
            // 如果当前正在编辑或添加网络监控，刷新表单
            const activeModal = document.querySelector('.modal.show');
            if (activeModal) {
                const typeSelect = activeModal.querySelector('select[name="type"]');
                if (typeSelect && typeSelect.value === 'network') {
                    updateConfigForm(typeSelect);
                }
            }
        } else {
            showMessage('刷新网络接口失败: ' + (result.error || '未知错误'), 'error');
        }
    } catch (error) {
        console.error('刷新网络接口错误:', error);
        showMessage('刷新网络接口失败: ' + error.message, 'error');
        // 设置默认网络接口列表作为降级方案
        window.networkInterfaces = [
            { name: 'eth0', bytes_sent: 0, bytes_recv: 0, is_active: false },
            { name: 'wlan0', bytes_sent: 0, bytes_recv: 0, is_active: false }
        ];
    }
}

// 在配置页面添加刷新按钮
function addDiskRefreshButton() {
    const diskConfigSection = document.querySelector('select[name="type"]');
    if (diskConfigSection) {
        // 在磁盘配置部分附近添加刷新按钮
        const refreshButton = document.createElement('button');
        refreshButton.type = 'button';
        refreshButton.className = 'btn btn-outline-info btn-sm ms-2';
        refreshButton.innerHTML = '<i class="bi bi-arrow-clockwise"></i> 刷新分区';
        refreshButton.onclick = refreshDiskPartitions;
        
        // 找到合适的位置插入按钮
        const diskRow = diskConfigSection.closest('.row');
        if (diskRow) {
            const col = diskRow.querySelector('.col-12');
            if (col) {
                col.appendChild(refreshButton);
            }
        }
    }
}

// 更新项目名称
async function updateProjectName() {
    const form = document.getElementById('project-name-form');
    const formData = new FormData(form);
    const projectName = formData.get('project_name').trim();
    
    if (!projectName) {
        showMessage('请输入项目名称', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/project-name', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ project_name: projectName })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showMessage('项目名称更新成功', 'success');
            // 更新页面显示
            document.querySelectorAll('.project-name').forEach(el => {
                el.textContent = projectName;
            });
            // 更新页面标题
            document.title = projectName;
        } else {
            showMessage('更新失败: ' + (result.error || '未知错误'), 'error');
        }
    } catch (error) {
        handleAjaxError(error);
    }
}

// 设置 JSON 验证
function setupJsonValidation() {
    // 找到所有 JSON 文本区域
    const jsonTextareas = document.querySelectorAll('textarea[name="extra_config[headers]"]');
    
    jsonTextareas.forEach(textarea => {
        // 移除之前的事件监听器
        textarea.removeEventListener('input', validateJson);
        textarea.removeEventListener('blur', validateJson);
        
        // 添加新的事件监听器
        textarea.addEventListener('input', validateJson);
        textarea.addEventListener('blur', validateJson);
        
        // 初始验证
        validateJson.call(textarea);
    });
}

// JSON 验证函数
function validateJson() {
    const textarea = this;
    const value = textarea.value.trim();
    
    // 移除之前的验证样式
    textarea.classList.remove('is-valid', 'is-invalid');
    
    // 移除之前的反馈信息
    let existingFeedback = textarea.nextElementSibling;
    if (existingFeedback && existingFeedback.classList.contains('json-feedback')) {
        existingFeedback.remove();
    }
    
    // 如果为空，不验证
    if (!value) {
        return;
    }
    
    try {
        // 尝试解析 JSON
        JSON.parse(value);
        
        // 验证成功
        textarea.classList.add('is-valid');
        
        // 添加成功反馈
        const feedback = document.createElement('div');
        feedback.className = 'valid-feedback json-feedback';
        feedback.textContent = 'JSON 格式正确';
        textarea.parentNode.appendChild(feedback);
        
    } catch (error) {
        // 验证失败
        textarea.classList.add('is-invalid');
        
        // 添加错误反馈
        const feedback = document.createElement('div');
        feedback.className = 'invalid-feedback json-feedback';
        feedback.textContent = `JSON 格式错误: ${error.message}`;
        textarea.parentNode.appendChild(feedback);
    }
}

// 初始化添加配置模态框
function initAddConfigModal() {
    const addConfigModal = document.getElementById('addConfigModal');
    if (addConfigModal) {
        addConfigModal.addEventListener('show.bs.modal', function () {
            // 默认选择第一个监控类型
            const defaultType = Object.keys(configTemplates)[0];
            const formContent = document.getElementById('add-config-form-content');
            formContent.innerHTML = generateConfigForm(defaultType, configTemplates[defaultType], 'add');
        });
    }
}

// 初始化编辑配置模态框
function initEditConfigModal() {
    const editModalElement = document.getElementById('editConfigModal');
    if (editModalElement) {
        // 创建模态框实例
        editModalInstance = new bootstrap.Modal(editModalElement);
        
        // 监听隐藏事件，清理数据
        editModalElement.addEventListener('hidden.bs.modal', function () {
            // 清理表单数据
            const form = document.getElementById('edit-config-form');
            if (form) {
                form.reset();
                delete form.dataset.configId;
            }
            // 清理表单内容
            const formContent = document.getElementById('edit-config-form-content');
            if (formContent) {
                formContent.innerHTML = `
                    <div class="text-center text-muted py-4">
                        <div class="spinner-border" role="status">
                            <span class="visually-hidden">加载中...</span>
                        </div>
                        <p class="mt-2">加载配置中...</p>
                    </div>
                `;
            }
        });
        
        // 监听显示事件
        editModalElement.addEventListener('show.bs.modal', function () {
            console.log('编辑模态框正在显示');
        });
    }
}


// 更新配置表单
function updateConfigForm(selectElement) {
    const form = selectElement.closest('form');
    const formType = form.id.includes('add') ? 'add' : 'edit';
    const monitorType = selectElement.value;
    const template = configTemplates[monitorType];
    
    if (!template) {
        console.error('未找到监控类型模板:', monitorType);
        return;
    }
    
    const formContent = document.getElementById(`${formType}-config-form-content`);
    if (!formContent) {
        console.error('未找到表单内容容器:', `${formType}-config-form-content`);
        return;
    }
    
    formContent.innerHTML = generateConfigForm(monitorType, template, formType);
}

// 生成配置表单HTML
// 生成配置表单HTML
function generateConfigForm(monitorType, template, formType, configData = null) {
    // 使用配置数据或默认值
    const data = configData || {};
    
    let html = `
        <div class="row g-3">
            <div class="col-12">
                <label class="form-label">监控名称</label>
                <input type="text" class="form-control" name="name" value="${escapeHtml(data.name || '')}" required>
            </div>
            
            <div class="col-12">
                <label class="form-label">监控类型</label>
                <select class="form-select" name="type" required>
                    <option value="">请选择监控类型</option>
    `;
    
    // 添加监控类型选项
    Object.keys(configTemplates).forEach(type => {
        const selected = type === monitorType ? 'selected' : '';
        html += `<option value="${type}" ${selected}>${type.toUpperCase()}</option>`;
    });
    
    html += `
                </select>
            </div>
    `;
    
    // 目标字段
    // 目标字段 - 特别处理磁盘监控
    if (monitorType === 'disk') {
        html += `
            <div class="col-12">
                <label class="form-label">${escapeHtml(template.target.label)}</label>
                <select class="form-select" name="target" required>
        `;
        
        // 动态填充磁盘分区选项
        let options = [];
        if (typeof diskPartitions !== 'undefined' && diskPartitions.length > 0) {
            options = diskPartitions.map(p => p.mountpoint);
        } else {
            // 备用选项
            options = ['/', '/home', '/var', '/opt', '/usr'];
        }
        
        const currentTarget = data.target || template.target.default;
        
        options.forEach(opt => {
            const selected = opt === currentTarget ? 'selected' : '';
            // 为选项添加详细信息提示
            const partitionInfo = diskPartitions?.find(p => p.mountpoint === opt);
            const displayText = partitionInfo ? 
                `${opt} (${partitionInfo.total_gb.toFixed(1)}GB, ${partitionInfo.fstype})` : 
                opt;
                
            html += `<option value="${escapeHtml(opt)}" ${selected} 
                    title="${partitionInfo ? `设备: ${partitionInfo.device}, 已用: ${partitionInfo.percent.toFixed(1)}%` : opt}">
                    ${escapeHtml(displayText)}</option>`;
        });
        
        html += `
                </select>
                <div class="form-text">
                    ${options.length > 0 ? 
                    `检测到 ${options.length} 个分区` : 
                    '无法获取分区信息，请确保系统支持'}
                </div>
            </div>
        `;
    } else if (monitorType === 'network') {
        html += `
            <div class="col-12">
                <label class="form-label">${escapeHtml(template.target.label)}</label>
                <select class="form-select" name="target" required>
        `;
        
        // 动态填充网络接口选项
        let options = [];
        let networkInterfacesData = window.networkInterfaces || [];
        
        if (networkInterfacesData && networkInterfacesData.length > 0) {
            options = networkInterfacesData.map(n => n.name);
        } else {
            // 备用选项 - 常见的网络接口名称
            options = ['eth0', 'wlan0', 'en0', 'en1', 'eth1', 'wlan1'];
        }
        
        const currentTarget = data.target || template.target.default;
        
        options.forEach(opt => {
            const selected = opt === currentTarget ? 'selected' : '';
            // 为选项添加详细信息提示
            const interfaceInfo = networkInterfacesData.find ? 
                networkInterfacesData.find(n => n.name === opt) : null;
            
            let displayText = opt;
            let titleText = opt;
            
            if (interfaceInfo) {
                const sentMB = (interfaceInfo.bytes_sent / (1024 * 1024)).toFixed(2);
                const recvMB = (interfaceInfo.bytes_recv / (1024 * 1024)).toFixed(2);
                const status = interfaceInfo.is_active ? '活跃' : '闲置';
                
                displayText = `${opt} (${status}, 发送:${sentMB}MB, 接收:${recvMB}MB)`;
                titleText = `接口: ${opt}, 状态: ${status}, 发送: ${sentMB}MB, 接收: ${recvMB}MB`;
            }
                
            html += `<option value="${escapeHtml(opt)}" ${selected} 
                     title="${titleText}">
                     ${escapeHtml(displayText)}</option>`;
        });
        
        html += `
                </select>
                <div class="form-text">
                    ${options.length > 0 ? 
                      `检测到 ${options.length} 个网络接口` : 
                      '无法获取网络接口信息，请确保系统支持'}
                    <button type="button" class="btn btn-sm btn-outline-info ms-2" onclick="refreshNetworkInterfaces()">
                        <i class="bi bi-arrow-clockwise"></i> 刷新接口
                    </button>
                </div>
            </div>
        `;
    }    
    else if (template.target.type === 'hidden') {
        html += `<input type="hidden" name="target" value="${escapeHtml(data.target || template.target.value)}">`;
    } else if (template.target.type === 'text') {
        html += `
            <div class="col-12">
                <label class="form-label">${escapeHtml(template.target.label)}</label>
                <input type="text" class="form-control" name="target" 
                       placeholder="${escapeHtml(template.target.placeholder)}" 
                       value="${escapeHtml(data.target || template.target.default)}" required>
            </div>
        `;
    } else if (template.target.type === 'select') {
        html += `
            <div class="col-12">
                <label class="form-label">${escapeHtml(template.target.label)}</label>
                <select class="form-select" name="target" required>
        `;
        
        template.target.options.forEach(opt => {
            const selected = opt === (data.target || template.target.default) ? 'selected' : '';
            html += `<option value="${escapeHtml(opt)}" ${selected}>${escapeHtml(opt)}</option>`;
        });
        
        html += `
                </select>
            </div>
        `;
    }
    
    // 阈值配置
    if (template.threshold && template.threshold.length > 0) {
        html += `<div class="col-12"><h6 class="mt-3">阈值配置</h6></div>`;
        
        template.threshold.forEach(item => {
            // 从配置数据中获取阈值，如果没有则使用默认值
            const thresholdValue = data.threshold && data.threshold[item.name] !== undefined 
                ? data.threshold[item.name] 
                : item.default;
                
            html += `
                <div class="col-md-6">
                    <label class="form-label">${escapeHtml(item.label)}</label>
                    <input type="${item.type}" class="form-control threshold-input" 
                           name="threshold[${item.name}]" value="${escapeHtml(thresholdValue)}" 
                           ${item.type === 'number' ? 'step="0.1"' : ''}>
                </div>
            `;
        });
    }
    
    // 额外配置
    if (template.extra && template.extra.length > 0) {
        html += `<div class="col-12"><h6 class="mt-3">额外配置</h6></div>`;
        
        template.extra.forEach(item => {
            // 从配置数据中获取额外配置值
            let extraValue = '';
            if (data.extra_config && data.extra_config[item.name] !== undefined) {
                extraValue = data.extra_config[item.name];
                // 如果是对象，转换为JSON字符串
                if (typeof extraValue === 'object') {
                    extraValue = JSON.stringify(extraValue, null, 2);
                }
            } else {
                extraValue = item.default || '';
            }
            
            if (item.type === 'textarea') {
                // 处理文本区域，特别注意 placeholder 属性
                const placeholder = item.placeholder ? `placeholder="${escapeHtml(item.placeholder)}"` : '';
                const formText = item.formText ? `<div class="form-text">${escapeHtml(item.formText)}</div>` : '';
                
                html += `
                    <div class="col-12">
                        <label class="form-label">${escapeHtml(item.label)}</label>
                        <textarea class="form-control" name="extra_config[${item.name}]" 
                                  rows="3" ${placeholder}>${escapeHtml(extraValue)}</textarea>
                        ${formText}
                    </div>
                `;
            } else if (item.type === 'select') {
                html += `
                    <div class="col-12">
                        <label class="form-label">${escapeHtml(item.label)}</label>
                        <select class="form-select" name="extra_config[${item.name}]">
                `;
                
                item.options.forEach(opt => {
                    const selected = opt === extraValue ? 'selected' : '';
                    html += `<option value="${escapeHtml(opt)}" ${selected}>${escapeHtml(opt)}</option>`;
                });
                
                html += `
                        </select>
                    </div>
                `;
            } else {
                html += `
                    <div class="col-md-6">
                        <label class="form-label">${escapeHtml(item.label)}</label>
                        <input type="${item.type}" class="form-control" 
                               name="extra_config[${item.name}]" value="${escapeHtml(extraValue)}" 
                               placeholder="${escapeHtml(item.placeholder || '')}">
                    </div>
                `;
            }
        });
    }
    
    // 间隔和启用状态
    html += `
        <div class="col-md-6">
            <label class="form-label">监测间隔(秒)</label>
            <input type="number" class="form-control" name="interval_seconds" 
                   value="${data.interval_seconds || 60}" min="10" required>
        </div>
        <div class="col-md-6">
            <label class="form-label">启用状态</label>
            <div class="form-check form-switch mt-2">
                <input class="form-check-input" type="checkbox" name="enabled" 
                       ${data.enabled !== false ? 'checked' : ''}>
                <label class="form-check-label">启用监控</label>
            </div>
        </div>
    </div>
    `;
    
    return html;
}

// HTML 转义函数
function escapeHtml(text) {
    if (text === null || text === undefined) {
        return '';
    }
    
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    
    return String(text).replace(/[&<>"']/g, function(m) { 
        return map[m]; 
    });
}

// 保存邮箱配置
async function saveEmailConfig() {
    const form = document.getElementById('email-config-form');
    const formData = new FormData(form);
    
    const config = {
        smtp_server: formData.get('smtp_server'),
        smtp_port: parseInt(formData.get('smtp_port')),
        username: formData.get('username'),
        password: formData.get('password'),
        sender: formData.get('sender'),
        receivers: formData.get('receivers').split(';').map(r => r.trim()),
        ssl_enabled: formData.get('ssl_enabled') === 'on'
    };
    
    try {
        const response = await fetch('/api/email-config', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(config)
        });
        
        const result = await response.json();
        
        if (result.success) {
            showMessage('邮箱配置保存成功', 'success');
        } else {
            showMessage('保存失败: ' + (result.error || '未知错误'), 'error');
        }
    } catch (error) {
        handleAjaxError(error);
    }
}

// 保存监控配置
async function saveMonitorConfig(action) {
    const form = document.getElementById(`${action}-config-form`);
    const formData = new FormData(form);
    
    // 验证 JSON 字段
    const jsonFields = form.querySelectorAll('textarea[name="extra_config[headers]"]');
    for (const field of jsonFields) {
        if (field.value.trim()) {
            try {
                JSON.parse(field.value);
            } catch (error) {
                showMessage(`JSON 格式错误: ${error.message}`, 'error');
                field.focus();
                return;
            }
        }
    }
    
    // 构建配置对象
    const config = {
        name: formData.get('name'),
        type: formData.get('type'),
        target: formData.get('target'),
        enabled: formData.get('enabled') === 'on',
        interval_seconds: parseInt(formData.get('interval_seconds'))
    };
    
    // 处理阈值
    const threshold = {};
    for (let [key, value] of formData.entries()) {
        if (key.startsWith('threshold[')) {
            const thresholdKey = key.match(/threshold\[(.*?)\]/)[1];
            threshold[thresholdKey] = isNaN(Number(value)) ? value : Number(value);
        }
    }
    if (Object.keys(threshold).length > 0) {
        config.threshold = threshold;
    }
    
    // 处理额外配置
    const extraConfig = {};
    for (let [key, value] of formData.entries()) {
        if (key.startsWith('extra_config[')) {
            const extraKey = key.match(/extra_config\[(.*?)\]/)[1];
            
            // 对于 headers 字段，尝试解析 JSON
            if (extraKey === 'headers' && value.trim()) {
                try {
                    extraConfig[extraKey] = JSON.parse(value);
                } catch (error) {
                    showMessage(`请求头 JSON 格式错误: ${error.message}`, 'error');
                    return;
                }
            } else {
                // 其他字段直接使用
                extraConfig[extraKey] = value;
            }
        }
    }
    if (Object.keys(extraConfig).length > 0) {
        config.extra_config = extraConfig;
    }
    
    try {
        const url = action === 'add' ? '/api/monitor-configs' : `/api/monitor-configs/${form.dataset.configId}`;
        const method = action === 'add' ? 'POST' : 'PUT';
        
        const response = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(config)
        });
        
        const result = await response.json();
        
        if (result.success) {
            showMessage(`监控配置${action === 'add' ? '添加' : '更新'}成功`, 'success');
            
            // 正确关闭模态框
            if (action === 'add') {
                const addModal = bootstrap.Modal.getInstance(document.getElementById('addConfigModal'));
                if (addModal) {
                    addModal.hide();
                }
            } else {
                // 编辑模态框使用全局实例
                if (editModalInstance) {
                    editModalInstance.hide();
                } else {
                    const editModal = bootstrap.Modal.getInstance(document.getElementById('editConfigModal'));
                    if (editModal) {
                        editModal.hide();
                    }
                }
            }
            
            // 延迟刷新页面，让用户看到成功消息
            setTimeout(() => location.reload(), 1500);
        } else {
            showMessage(`${action === 'add' ? '添加' : '更新'}失败: ` + (result.error || '未知错误'), 'error');
        }
    } catch (error) {
        handleAjaxError(error);
    }
}

// 切换监控配置状态
async function toggleMonitorConfig(configId, enabled) {
    try {
        const response = await fetch(`/api/monitor-configs/${configId}/toggle`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: `enabled=${enabled}`
        });
        
        const result = await response.json();
        
        if (result.success) {
            showMessage(`监控配置已${enabled ? '启用' : '禁用'}`, 'success');
        } else {
            showMessage('操作失败', 'error');
            // 恢复开关状态
            const switchEl = document.querySelector(`.toggle-switch[data-config-id="${configId}"]`);
            if (switchEl) {
                switchEl.checked = !enabled;
            }
        }
    } catch (error) {
        handleAjaxError(error);
        // 恢复开关状态
        const switchEl = document.querySelector(`.toggle-switch[data-config-id="${configId}"]`);
        if (switchEl) {
            switchEl.checked = !enabled;
        }
    }
}

// 删除监控配置
async function deleteMonitorConfig(configId, configName) {
    if (!confirm(`确定要删除监控配置 "${configName}" 吗？此操作不可恢复。`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/monitor-configs/${configId}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (result.success) {
            showMessage('监控配置删除成功', 'success');
            setTimeout(() => location.reload(), 1000);
        } else {
            showMessage('删除失败', 'error');
        }
    } catch (error) {
        handleAjaxError(error);
    }
}

// 加载配置用于编辑
async function loadConfigForEdit(configId) {
    try {
        const response = await fetch(`/api/monitor-configs/${configId}`);
        const result = await response.json();
        
        if (result.success && result.data) {
            const config = result.data;
            
            // 如果是磁盘监控且没有分区信息，先获取分区信息
            if (config.type === 'disk' && (!window.diskPartitions || window.diskPartitions.length === 0)) {
                await refreshDiskPartitions();
            }
            
            // 如果是网络监控且没有接口信息，先获取接口信息
            if (config.type === 'network' && (!window.networkInterfaces || window.networkInterfaces.length === 0)) {
                await refreshNetworkInterfaces();
            }
                        
            // 设置表单数据
            const form = document.getElementById('edit-config-form');
            form.dataset.configId = configId;
            
            // 生成表单
            const template = configTemplates[config.type];
            if (template) {
                const formContent = document.getElementById('edit-config-form-content');
                formContent.innerHTML = generateConfigForm(config.type, template, 'edit', config);
                
                // 使用全局模态框实例显示
                if (editModalInstance) {
                    editModalInstance.show();
                } else {
                    // 备用方案：创建新实例
                    const modal = new bootstrap.Modal(document.getElementById('editConfigModal'));
                    modal.show();
                }
            } else {
                showMessage(`不支持的监控类型: ${config.type}`, 'error');
            }
        } else {
            showMessage('加载配置失败: ' + (result.error || '未知错误'), 'error');
        }
    } catch (error) {
        console.error('加载配置错误:', error);
        handleAjaxError(error);
    }
}

// 测试邮箱配置
async function testEmailConfig() {
    // 获取表单数据
    const form = document.getElementById('email-config-form');
    const formData = new FormData(form);
    
    // 构建配置对象
    const config = {
        smtp_server: formData.get('smtp_server'),
        smtp_port: parseInt(formData.get('smtp_port')),
        username: formData.get('username'),
        password: formData.get('password'),
        sender: formData.get('sender'),
        receivers: formData.get('receivers').split(';').map(r => r.trim()),
        ssl_enabled: formData.get('ssl_enabled') === 'on'
    };
    
    // 验证必填字段
    if (!config.smtp_server || !config.smtp_port || !config.username || 
        !config.password || !config.sender || !config.receivers.length) {
        showMessage('请填写所有必填字段', 'error');
        return;
    }
    
    // 验证收件人邮箱格式
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    const invalidEmails = config.receivers.filter(email => !emailRegex.test(email));
    if (invalidEmails.length > 0) {
        showMessage(`无效的邮箱地址: ${invalidEmails.join(', ')}`, 'error');
        return;
    }
    
    // 显示加载状态
    const testButton = document.querySelector('button[onclick="testEmailConfig()"]');
    const originalText = testButton.innerHTML;
    testButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span> 发送测试中...';
    testButton.disabled = true;
    
    try {
        // 先保存配置
        const saveResponse = await fetch('/api/email-config', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(config)
        });
        
        const saveResult = await saveResponse.json();
        
        if (!saveResult.success) {
            throw new Error('保存配置失败: ' + (saveResult.error || '未知错误'));
        }
        
        // 发送测试请求
        const testResponse = await fetch('/api/test-email', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        const testResult = await testResponse.json();
        
        if (testResult.success) {
            showMessage(testResult.message, 'success');
            
            // 显示详细成功信息
            showDetailedSuccess(config, testResult.message);
        } else {
            showMessage('测试失败: ' + (testResult.error || '未知错误'), 'error');
            
            // 显示详细错误信息
            showDetailedError(config, testResult.error);
        }
        
    } catch (error) {
        console.error('邮箱配置测试错误:', error);
        showMessage('测试过程中出现错误: ' + error.message, 'error');
    } finally {
        // 恢复按钮状态
        testButton.innerHTML = originalText;
        testButton.disabled = false;
    }
}

// 显示详细成功信息
function showDetailedSuccess(config, message) {
    const successHtml = `
        <div class="alert alert-success alert-dismissible fade show mt-3" role="alert">
            <h5 class="alert-heading">✅ 邮箱配置测试成功</h5>
            <p>${message}</p>
            <hr>
            <h6>配置详情:</h6>
            <ul class="mb-0">
                <li><strong>SMTP服务器:</strong> ${config.smtp_server}:${config.smtp_port}</li>
                <li><strong>用户名:</strong> ${config.username}</li>
                <li><strong>发件人:</strong> ${config.sender}</li>
                <li><strong>收件人:</strong> ${config.receivers.join('; ')}</li>
                <li><strong>SSL/TLS:</strong> ${config.ssl_enabled ? '已启用' : '未启用'}</li>
            </ul>
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    // 在邮箱配置卡片中显示成功信息
    const emailCard = document.querySelector('.card.config-card');
    if (emailCard) {
        emailCard.insertAdjacentHTML('beforeend', successHtml);
    }
}

// 显示详细错误信息
function showDetailedError(config, error) {
    let troubleshooting = '';
    
    // 根据错误类型提供排查建议
    if (error.includes('认证失败') || error.includes('Authentication')) {
        troubleshooting = `
            <h6 class="mt-3">排查建议:</h6>
            <ul>
                <li>检查用户名和密码是否正确</li>
                <li>某些邮箱服务商需要使用授权码而不是登录密码</li>
                <li>确认邮箱服务是否开启了SMTP服务</li>
            </ul>
        `;
    } else if (error.includes('连接') || error.includes('Connection') || error.includes('网络')) {
        troubleshooting = `
            <h6 class="mt-3">排查建议:</h6>
            <ul>
                <li>检查SMTP服务器地址和端口是否正确</li>
                <li>确认网络连接正常</li>
                <li>检查防火墙设置</li>
                <li>尝试更换端口（如587、465、25）</li>
            </ul>
        `;
    } else if (error.includes('SSL') || error.includes('TLS')) {
        troubleshooting = `
            <h6 class="mt-3">排查建议:</h6>
            <ul>
                <li>尝试启用/禁用SSL选项</li>
                <li>检查端口是否正确（SSL通常使用465端口）</li>
                <li>确认服务器支持选择的加密方式</li>
            </ul>
        `;
    }
    
    const errorHtml = `
        <div class="alert alert-danger alert-dismissible fade show mt-3" role="alert">
            <h5 class="alert-heading">❌ 邮箱配置测试失败</h5>
            <p><strong>错误信息:</strong> ${error}</p>
            <hr>
            <h6>当前配置:</h6>
            <ul>
                <li><strong>SMTP服务器:</strong> ${config.smtp_server}:${config.smtp_port}</li>
                <li><strong>用户名:</strong> ${config.username}</li>
                <li><strong>SSL/TLS:</strong> ${config.ssl_enabled ? '已启用' : '未启用'}</li>
            </ul>
            ${troubleshooting}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    // 在邮箱配置卡片中显示错误信息
    const emailCard = document.querySelector('.card.config-card');
    if (emailCard) {
        emailCard.insertAdjacentHTML('beforeend', errorHtml);
    }
}

// 处理AJAX错误
function handleAjaxError(error) {
    console.error('AJAX Error:', error);
    showMessage('操作失败: ' + (error.message || '网络错误'), 'error');
}

// 显示消息提示
function showMessage(message, type = 'success') {
    const alertClass = type === 'success' ? 'alert-success' : 
                       type === 'error' ? 'alert-danger' : 
                       type === 'warning' ? 'alert-warning' : 'alert-info';
    
    const alertHtml = `
        <div class="alert ${alertClass} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    // 在页面顶部显示消息
    const container = document.querySelector('.container');
    if (container) {
        container.insertAdjacentHTML('afterbegin', alertHtml);
        
        // 5秒后自动消失
        setTimeout(() => {
            const alert = document.querySelector('.alert');
            if (alert) {
                alert.remove();
            }
        }, 5000);
    }
}

// 邮箱配置表单验证
function validateEmailConfig() {
    const form = document.getElementById('email-config-form');
    const inputs = form.querySelectorAll('input[required]');
    
    let isValid = true;
    inputs.forEach(input => {
        if (!input.value.trim()) {
            isValid = false;
            input.classList.add('is-invalid');
        } else {
            input.classList.remove('is-invalid');
        }
    });
    
    // 验证邮箱格式
    const emailInputs = ['sender', 'receivers'];
    emailInputs.forEach(fieldName => {
        const input = form.querySelector(`[name="${fieldName}"]`);
        if (input && input.value) {
            if (fieldName === 'receivers') {
                const emails = input.value.split(';').map(e => e.trim());
                const invalidEmails = emails.filter(email => !isValidEmail(email));
                if (invalidEmails.length > 0) {
                    isValid = false;
                    input.classList.add('is-invalid');
                    // 显示具体的无效邮箱
                    const errorDiv = input.nextElementSibling || document.createElement('div');
                    errorDiv.className = 'invalid-feedback';
                    errorDiv.textContent = `无效的邮箱地址: ${invalidEmails.join(', ')}`;
                    if (!input.nextElementSibling) {
                        input.parentNode.appendChild(errorDiv);
                    }
                } else {
                    input.classList.remove('is-invalid');
                }
            } else {
                if (!isValidEmail(input.value)) {
                    isValid = false;
                    input.classList.add('is-invalid');
                    const errorDiv = input.nextElementSibling || document.createElement('div');
                    errorDiv.className = 'invalid-feedback';
                    errorDiv.textContent = '请输入有效的邮箱地址';
                    if (!input.nextElementSibling) {
                        input.parentNode.appendChild(errorDiv);
                    }
                } else {
                    input.classList.remove('is-invalid');
                }
            }
        }
    });
    
    return isValid;
}

// 邮箱格式验证函数
function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

// 强制关闭所有模态框的函数
function forceCloseAllModals() {
    // 关闭所有 Bootstrap 模态框
    const modals = document.querySelectorAll('.modal');
    modals.forEach(modal => {
        const bsModal = bootstrap.Modal.getInstance(modal);
        if (bsModal) {
            bsModal.hide();
        }
    });
    
    // 手动移除背景遮罩
    const backdrops = document.querySelectorAll('.modal-backdrop');
    backdrops.forEach(backdrop => {
        backdrop.remove();
    });
    
    // 移除 modal-open 类
    document.body.classList.remove('modal-open');
    document.body.style.paddingRight = '';
    document.body.style.overflow = '';
}

// 页面加载完成后初始化
//document.addEventListener('DOMContentLoaded', initConfigForms);
document.addEventListener('DOMContentLoaded', function() {
    initConfigForms();
    
    // 全局事件委托，处理动态生成的表单元素
    document.addEventListener('change', function(e) {
        // 处理监控类型切换
        if (e.target && e.target.name === 'type') {
            const form = e.target.closest('form');
            if (form && (form.id === 'add-config-form' || form.id === 'edit-config-form')) {
                updateConfigForm(e.target);
            }
        }
    });

    // 监听 ESC 键关闭模态框
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            forceCloseAllModals();
        }
    });
    
    // 点击背景关闭模态框
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('modal-backdrop')) {
            forceCloseAllModals();
        }
    });    
});
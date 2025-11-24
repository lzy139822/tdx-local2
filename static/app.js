// API基础URL
const API_BASE = '';

// 全局变量
let currentStrategy = null;
let currentResults = [];

// DOM元素
const elements = {
    strategyName: document.getElementById('strategyName'),
    strategyInput: document.getElementById('strategyInput'),
    generateBtn: document.getElementById('generateBtn'),
    executeBtn: document.getElementById('executeBtn'),
    exportBtn: document.getElementById('exportBtn'),
    codeSection: document.getElementById('codeSection'),
    generatedCode: document.getElementById('generatedCode'),
    strategyList: document.getElementById('strategyList'),
    loadingState: document.getElementById('loadingState'),
    resultStats: document.getElementById('resultStats'),
    resultActions: document.getElementById('resultActions'),
    resultsTable: document.getElementById('resultsTable'),
    totalCount: document.getElementById('totalCount'),
    executionTime: document.getElementById('executionTime'),
    toast: document.getElementById('toast')
};

// Toast通知
function showToast(message, type = 'success') {
    elements.toast.textContent = message;
    elements.toast.className = `toast show ${type}`;

    setTimeout(() => {
        elements.toast.classList.remove('show');
    }, 3000);
}

// 生成策略
async function generateStrategy() {
    const name = elements.strategyName.value.trim();
    const userInput = elements.strategyInput.value.trim();

    if (!name || !userInput) {
        showToast('请填写策略名称和选股条件', 'error');
        return;
    }

    elements.generateBtn.disabled = true;
    elements.generateBtn.innerHTML = '<span class="btn-icon">⏳</span>生成中...';

    try {
        const response = await fetch(`${API_BASE}/api/strategies`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                name: name,
                description: `基于用户输入生成的策略`,
                user_input: userInput
            })
        });

        if (!response.ok) {
            throw new Error('生成策略失败');
        }

        const strategy = await response.json();
        currentStrategy = strategy;

        // 显示生成的代码
        elements.generatedCode.textContent = strategy.generated_code;
        elements.codeSection.style.display = 'block';

        // 启用执行按钮
        elements.executeBtn.disabled = false;

        showToast('策略生成成功!', 'success');

        // 刷新历史策略
        loadStrategies();

    } catch (error) {
        console.error('Error:', error);
        showToast('生成策略失败: ' + error.message, 'error');
    } finally {
        elements.generateBtn.disabled = false;
        elements.generateBtn.innerHTML = '<span class="btn-icon">✨</span>生成策略';
    }
}

// 执行选股
async function executeStrategy() {
    if (!currentStrategy || !currentStrategy.id) {
        showToast('请先生成策略', 'error');
        return;
    }

    elements.executeBtn.disabled = true;
    elements.executeBtn.innerHTML = '<span class="btn-icon">⏳</span>执行中...';
    elements.loadingState.style.display = 'block';
    elements.resultStats.style.display = 'none';
    elements.resultActions.style.display = 'none';
    elements.resultsTable.innerHTML = '<p class="empty-state">正在执行选股...</p>';

    try {
        const response = await fetch(`${API_BASE}/api/strategies/${currentStrategy.id}/execute?max_stocks=100`, {
            method: 'POST'
        });

        if (!response.ok) {
            throw new Error('执行策略失败');
        }

        const result = await response.json();
        currentResults = result.results;

        // 更新统计信息
        elements.totalCount.textContent = result.total_count;
        elements.executionTime.textContent = result.execution_time.toFixed(2) + 's';

        // 显示结果
        displayResults(result.results);

        elements.loadingState.style.display = 'none';
        elements.resultStats.style.display = 'grid';
        elements.resultActions.style.display = 'flex';

        showToast(`选股完成,共选中 ${result.total_count} 只股票`, 'success');

    } catch (error) {
        console.error('Error:', error);
        showToast('执行策略失败: ' + error.message, 'error');
        elements.loadingState.style.display = 'none';
        elements.resultsTable.innerHTML = '<p class="empty-state">执行失败</p>';
    } finally {
        elements.executeBtn.disabled = false;
        elements.executeBtn.innerHTML = '<span class="btn-icon">🚀</span>执行选股';
    }
}

// 显示选股结果
function displayResults(results) {
    if (!results || results.length === 0) {
        elements.resultsTable.innerHTML = '<p class="empty-state">未找到符合条件的股票</p>';
        return;
    }

    // 获取所有指标字段
    const metricsFields = new Set();
    results.forEach(r => {
        if (r.metrics) {
            Object.keys(r.metrics).forEach(key => metricsFields.add(key));
        }
    });

    const metricsArray = Array.from(metricsFields);

    // 创建表格
    let html = '<table><thead><tr>';
    html += '<th>序号</th>';
    html += '<th>股票代码</th>';
    html += '<th>股票名称</th>';

    metricsArray.forEach(field => {
        html += `<th>${field}</th>`;
    });

    html += '<th>选中时间</th>';
    html += '</tr></thead><tbody>';

    results.forEach((result, index) => {
        html += '<tr>';
        html += `<td>${index + 1}</td>`;
        html += `<td class="stock-code">${result.code}</td>`;
        html += `<td>${result.name || '-'}</td>`;

        metricsArray.forEach(field => {
            const value = result.metrics ? result.metrics[field] : null;
            if (value !== null && value !== undefined) {
                const displayValue = typeof value === 'number' ? value.toFixed(2) : value;
                html += `<td>${displayValue}</td>`;
            } else {
                html += '<td>-</td>';
            }
        });

        const date = new Date(result.selected_at);
        html += `<td>${date.toLocaleString('zh-CN')}</td>`;
        html += '</tr>';
    });

    html += '</tbody></table>';
    elements.resultsTable.innerHTML = html;
}

// 加载历史策略
async function loadStrategies() {
    try {
        const response = await fetch(`${API_BASE}/api/strategies?limit=10`);

        if (!response.ok) {
            throw new Error('加载策略失败');
        }

        const strategies = await response.json();

        if (!strategies || strategies.length === 0) {
            elements.strategyList.innerHTML = '<p class="empty-state">暂无历史策略</p>';
            return;
        }

        let html = '';
        strategies.forEach(strategy => {
            const date = new Date(strategy.created_at);
            html += `
                <div class="strategy-item" data-id="${strategy.id}">
                    <div class="strategy-item-content">
                        <div class="strategy-item-title">${strategy.name}</div>
                        <div class="strategy-item-desc">${strategy.user_input}</div>
                        <div class="strategy-item-date">${date.toLocaleString('zh-CN')}</div>
                    </div>
                    <button class="btn-delete" onclick="deleteStrategy(${strategy.id}, event)" title="删除策略">
                        <span>🗑️</span>
                    </button>
                </div>
            `;
        });

        elements.strategyList.innerHTML = html;

        // 添加点击事件(排除删除按钮)
        document.querySelectorAll('.strategy-item').forEach(item => {
            item.addEventListener('click', (e) => {
                // 如果点击的是删除按钮,不触发加载
                if (e.target.closest('.btn-delete')) {
                    return;
                }
                loadStrategy(item.dataset.id);
            });
        });

    } catch (error) {
        console.error('Error:', error);
    }
}

// 加载单个策略
async function loadStrategy(strategyId) {
    try {
        const response = await fetch(`${API_BASE}/api/strategies/${strategyId}`);

        if (!response.ok) {
            throw new Error('加载策略失败');
        }

        const strategy = await response.json();
        currentStrategy = strategy;

        // 填充表单
        elements.strategyName.value = strategy.name;
        elements.strategyInput.value = strategy.user_input;
        elements.generatedCode.textContent = strategy.generated_code;
        elements.codeSection.style.display = 'block';
        elements.executeBtn.disabled = false;

        showToast('策略已加载', 'success');

    } catch (error) {
        console.error('Error:', error);
        showToast('加载策略失败', 'error');
    }
}

// 删除策略
async function deleteStrategy(strategyId, event) {
    event.stopPropagation(); // 阻止事件冒泡

    if (!confirm('确定要删除这个策略吗?此操作不可恢复!')) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/strategies/${strategyId}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            throw new Error('删除策略失败');
        }

        showToast('策略已删除', 'success');

        // 如果删除的是当前策略,清空表单
        if (currentStrategy && currentStrategy.id === strategyId) {
            currentStrategy = null;
            elements.strategyName.value = '';
            elements.strategyInput.value = '';
            elements.generatedCode.textContent = '';
            elements.codeSection.style.display = 'none';
            elements.executeBtn.disabled = true;
            elements.resultStats.style.display = 'none';
            elements.resultActions.style.display = 'none';
            elements.resultsTable.innerHTML = '<p class="empty-state">请先生成或加载策略</p>';
        }

        // 刷新历史策略列表
        loadStrategies();

    } catch (error) {
        console.error('Error:', error);
        showToast('删除策略失败: ' + error.message, 'error');
    }
}

// 导出选股结果
async function exportResults() {
    if (!currentStrategy || !currentStrategy.id) {
        showToast('请先执行选股', 'error');
        return;
    }

    elements.exportBtn.disabled = true;
    elements.exportBtn.innerHTML = '<span class="btn-icon">⏳</span>导出中...';

    try {
        const response = await fetch(`${API_BASE}/api/strategies/${currentStrategy.id}/export?format=all`, {
            method: 'POST'
        });

        if (!response.ok) {
            throw new Error('导出失败');
        }

        const result = await response.json();

        showToast(`导出成功! 生成了 ${result.data.files.length} 个文件`, 'success');

        // 显示导入说明
        setTimeout(() => {
            alert(result.data.instructions);
        }, 500);

    } catch (error) {
        console.error('Error:', error);
        showToast('导出失败: ' + error.message, 'error');
    } finally {
        elements.exportBtn.disabled = false;
        elements.exportBtn.innerHTML = '<span class="btn-icon">📥</span>导出自选股';
    }
}

// 事件监听
elements.generateBtn.addEventListener('click', generateStrategy);
elements.executeBtn.addEventListener('click', executeStrategy);
elements.exportBtn.addEventListener('click', exportResults);

// 页面加载时加载历史策略
document.addEventListener('DOMContentLoaded', () => {
    loadStrategies();

    // 检查服务状态
    fetch(`${API_BASE}/api/health`)
        .then(response => response.json())
        .then(data => {
            console.log('服务状态:', data);
        })
        .catch(error => {
            console.error('服务连接失败:', error);
            showToast('无法连接到服务,请检查服务是否启动', 'error');
        });
});

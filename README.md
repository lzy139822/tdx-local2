# 通达信AI选股系统

智能选股,数据驱动,精准决策

## 项目简介

本项目将通达信本地数据转化为RESTful API服务,并集成AI大模型实现智能选股功能。无需将数据转储到MySQL,直接读取通达信.day文件,提供高性能的数据查询和选股服务。

## 核心功能

### 1. 数据中转服务
- 🔍 **股票数据查询**: 直接读取通达信本地.day文件
- 🚀 **RESTful API**: 标准HTTP接口,支持第三方程序调用
- ⚡ **高性能缓存**: LRU缓存机制,提升查询速度
- 📊 **批量查询**: 支持批量股票数据查询

### 2. AI选股机器人
- 🤖 **自然语言输入**: 用中文描述选股条件
- ✨ **AI策略生成**: 调用DeepSeek等大模型生成Python选股代码
- 🎯 **智能执行**: 安全沙箱环境执行选股策略
- 💾 **策略管理**: SQLite数据库保存历史策略和结果
- 📥 **导出自选股**: 生成通达信可导入的自选股文件

### 3. 现代化Web界面
- 🎨 **精美设计**: 深色主题,渐变色,流畅动画
- 📱 **响应式布局**: 支持PC、平板、手机访问
- ⚡ **实时交互**: 即时反馈,流畅体验

## 快速开始

### 1. 环境要求
- Python 3.8+
- 通达信软件(已安装)
- DeepSeek API密钥(用于AI选股)

### 2. 安装依赖

**创建虚拟环境(推荐):**

```bash
cd f:\webtest\tdx-local2

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
.\venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

**或直接安装(不推荐):**

```bash
pip install -r requirements.txt
```

### 3. 配置

编辑 `config.ini` 文件:

```ini
[TDX]
INSTALL_PATH = D:/new_tdx  # 修改为你的通达信安装路径

[AI]
API_KEY = your-deepseek-api-key  # 填入你的API密钥
```

### 4. 启动服务

```bash
python main.py
```

### 5. 访问系统

- **Web界面**: http://localhost:8000
- **API文档**: http://localhost:8000/docs

## API使用示例

### 查询股票列表
```bash
curl http://localhost:8000/api/stocks
```

### 查询单个股票日线数据
```bash
curl http://localhost:8000/api/stocks/sh600000/day
```

### 查询指定时间范围
```bash
curl "http://localhost:8000/api/stocks/sh600000/day?start=2024-01-01&end=2024-02-01"
```

### 创建选股策略
```bash
curl -X POST http://localhost:8000/api/strategies \
  -H "Content-Type: application/json" \
  -d '{
    "name": "低估值策略",
    "user_input": "选出市盈率小于20且成交量大于1000万的股票"
  }'
```

### 执行策略
```bash
curl -X POST http://localhost:8000/api/strategies/1/execute
```

## 使用流程

### 方式一:Web界面(推荐)

1. 打开浏览器访问 http://localhost:8000
2. 在"创建选股策略"区域:
   - 输入策略名称(如:"低估值高成交量")
   - 描述选股条件(如:"选出市盈率小于20且最近5天平均成交量大于1000万手的股票")
3. 点击"生成策略"按钮,AI将生成Python选股代码
4. 查看生成的代码,确认无误后点击"执行选股"
5. 等待执行完成,查看选股结果
6. 点击"导出自选股"生成通达信导入文件

### 方式二:直接调用API

1. 使用 `/api/strategies/create-and-execute` 接口一站式完成
2. 或分步调用:创建策略 → 执行策略 → 导出结果

## 导入通达信自选股

### 方法一:文本文件导入(推荐)
1. 执行完选股后,点击"导出自选股"
2. 在项目目录找到 `selected_stocks.txt`
3. 打开通达信软件
4. 进入自选股界面(快捷键: Ctrl+D)
5. 右键 → 批量导入 → 选择文件

### 方法二:手动添加
导出的CSV文件包含股票代码,可手动在通达信中逐个添加

## 项目结构

```
tdx-local2/
├── main.py              # 主启动文件
├── api_service.py       # FastAPI服务
├── tdx_reader.py        # 通达信数据读取器
├── ai_selector.py       # AI选股引擎
├── database.py          # SQLite数据库管理
├── tdx_exporter.py      # 自选股导出工具
├── models.py            # 数据模型定义
├── config.ini           # 配置文件
├── requirements.txt     # 依赖列表
├── static/              # 静态文件(Web界面)
│   ├── index.html
│   ├── style.css
│   └── app.js
└── README.md            # 本文件
```

## 配置说明

### config.ini

```ini
[TDX]
INSTALL_PATH = D:/new_tdx           # 通达信安装路径
SH_LDAY_PATH = ...                  # (自动计算)上海日线数据路径
SZ_LDAY_PATH = ...                  # (自动计算)深圳日线数据路径

[API]
HOST = 0.0.0.0                      # API服务监听地址
PORT = 8000                         # API服务端口

[AI]
MODEL = deepseek-chat               # 使用的模型
API_BASE = https://api.deepseek.com/v1  # API基础URL
API_KEY = your-api-key-here         # API密钥(必填)

[DATABASE]
SQLITE_PATH = ./stock_selector.db   # SQLite数据库路径
```

## 常见问题

### Q: 提示"未找到股票数据"?
A: 检查通达信安装路径是否正确,确保 `vipdoc/sh/lday` 和 `vipdoc/sz/lday` 目录存在且有.day文件

### Q: AI选股功能不可用?
A: 检查config.ini中是否配置了正确的API_KEY,确保网络可以访问DeepSeek API

### Q: 生成的策略代码不符合预期?
A: 可以修改描述重新生成,或者手动编辑生成的代码后保存为新策略

### Q: 如何获取DeepSeek API密钥?
A: 访问 https://platform.deepseek.com 注册并获取API密钥

### Q: 可以使用其他大模型吗?
A: 可以,只要支持OpenAI兼容接口,修改config.ini中的API_BASE和MODEL即可

## 技术栈

- **后端**: FastAPI, Python 3.8+
- **数据库**: SQLite
- **AI**: DeepSeek/OpenAI兼容API
- **前端**: 原生HTML/CSS/JavaScript
- **数据处理**: Pandas, NumPy

## 安全说明

- AI生成的代码会经过安全检查,禁止文件操作、网络请求等危险操作
- 所有代码在隔离的命名空间中执行
- 建议仅在本地网络使用,或添加身份验证

## 性能优化

- LRU缓存机制,重复查询直接使用缓存
- 批量查询API减少网络往返
- 支持限制选股结果数量,避免处理过多数据

## 更新日志

### v1.0.0 (2024-02-02)
- ✨ 初始版本发布
- ✅ 支持通达信日线数据读取
- ✅ RESTful API服务
- ✅ AI选股功能
- ✅ Web界面
- ✅ 自选股导出

## 许可证

MIT License

## 联系方式

如有问题或建议,欢迎提Issue!

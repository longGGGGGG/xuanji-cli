# xuanji-cli

舆情分析工作流 CLI 工具 - 从数据获取到 AI 分析再到报告生成的一站式解决方案。

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 功能特性

- **专项管理** - 创建、查看、删除舆情监控专项
- **数据获取** - 从 project-mcp 获取舆情数据，支持多种输出格式
- **AI 分析** - 内置 8 种分析功能（摘要、情感、观点、主题、实体、KOL、地域、互动）
- **MapReduce 架构** - 支持 500+ 条数据的大规模分析，自动分块并行处理
- **报告生成** - 基于 Jinja2 模板生成专业 Markdown 报告
- **工作流编排** - 一键执行完整分析流程
- **配置管理** - 支持主模型和轻量模型双配置

---

## 安装

### 方式一：pipx 安装（推荐，全局可用）

```bash
# 安装 pipx（如果没有）
brew install pipx
pipx ensurepath

# 克隆并安装
git clone https://github.com/yourusername/xuanji-cli.git
cd xuanji-cli
pipx install -e .
```

安装后 `xuanji` 命令全局可用，无需激活虚拟环境。

### 方式二：虚拟环境安装（开发用）

```bash
git clone https://github.com/yourusername/xuanji-cli.git
cd xuanji-cli

python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

> 注意：虚拟环境安装后，每次使用前需要 `source .venv/bin/activate`

### 验证安装

```bash
xuanji --version
```

---

## 配置

xuanji-cli 需要配置 LLM 才能进行 AI 分析。配置文件位于 `~/.xuanji/config.json`。

```json
{
  "default_limit": 500,
  "default_analysis": "summary,opinion",
  "llm": {
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "api_key": "sk-xxxxx",
    "model_name": "MiniMax-M2.5"
  },
  "llm_light": {
    "model_name": "qwen3.5-flash"
  },
  "default_project": "xxxx",
  "cookie": "remember_user_token=xxxxx"
}
```

### 交互式配置（推荐）

```bash
xuanji config init
```

按提示输入 LLM API 信息即可完成配置。

### 手动配置

```bash
# 舆情平台 Cookie（必须，用于访问舆情数据）
xuanji config set cookie "remember_user_token=your-cookie-value"

# 主模型配置（必须）
xuanji config set llm.base_url "https://api.openai.com/v1/"
xuanji config set llm.api_key "sk-your-api-key"
xuanji config set llm.model_name "gpt-4"

# 轻量模型配置（可选，用于 MapReduce 子任务，更快更便宜）
xuanji config set llm_light.model_name "qwen3.5-flash"
```

### 支持的 LLM 提供商

| 提供商     | Base URL                                              |
| ---------- | ----------------------------------------------------- |
| OpenAI     | `https://api.openai.com/v1/`                        |
| Kimi       | `https://api.kimi.com/coding/`                      |
| 阿里云通义 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| 本地模型   | `http://localhost:8000/v1/`                         |

### 查看当前配置

```bash
xuanji config show
```

### 配置项说明

| 配置项                   | 说明                                    | 示例                           |
| ------------------------ | --------------------------------------- | ------------------------------ |
| `cookie`               | 舆情平台认证 Cookie                     | `remember_user_token=xxx`    |
| `llm.base_url`         | 主模型 API 地址                         | `https://api.openai.com/v1/` |
| `llm.api_key`          | 主模型 API 密钥                         | `sk-xxx`                     |
| `llm.model_name`       | 主模型名称                              | `gpt-4`                      |
| `llm_light.model_name` | 轻量模型名称                            | `qwen3.5-flash`              |
| `llm_light.base_url`   | 轻量模型 API 地址（可选，默认同主模型） | -                              |
| `llm_light.api_key`    | 轻量模型 API 密钥（可选，默认同主模型） | -                              |
| `default_project`      | 默认专项名称                            | `北京全量`                   |
| `default_limit`        | 默认数据条数                            | `100`                        |
| `default_analysis`     | 默认分析功能                            | `summary,opinion`            |

---

## 快速开始

### 1. 一键工作流（最简单）

```bash
xuanji workflow quick "项目名称" "output.md"
```

### 2. 完整工作流

```bash
xuanji workflow run \
    --project "北京全量" \
    --keyword "北京&舆情" \
    --limit 500 \
    --analysis summary,opinion \
    --output "report.md"
```

### 3. 管道组合（灵活）

```bash
xuanji data get --project "北京全量" --limit 500 | \
    xuanji analyze --functions summary,sentiment,opinion | \
    xuanji report --output "report.md"
```

---

## 命令参考

### 总览

```
xuanji
├── config      # 配置管理
├── project     # 专项管理
├── data        # 数据获取
├── analyze     # AI 分析
├── report      # 报告生成
├── workflow    # 工作流编排
├── functions   # 列出分析功能
└── templates   # 列出报告模板
```

### config - 配置管理

```bash
xuanji config init              # 交互式初始化配置
xuanji config show              # 查看当前配置
xuanji config set <key> <value> # 设置配置项
xuanji config get <key>         # 获取配置项
xuanji config unset <key>       # 删除配置项
```

**示例：**

```bash
xuanji config set llm.base_url "https://api.openai.com/v1/"
xuanji config set llm.api_key "sk-xxx"
xuanji config set llm.model_name "gpt-4"
xuanji config set llm_light.model_name "qwen3.5-flash"
xuanji config set default_limit 500
```

### project - 专项管理

```bash
xuanji project list                         # 列出所有专项
xuanji project create "关键词" --name "名称" # 创建专项
xuanji project get --name "名称"            # 查看专项详情
xuanji project delete <id>                  # 删除专项
```

**示例：**

```bash
# 创建一个监控"北京舆情"的专项
xuanji project create "北京&舆情" --name "北京全量"

# 查看专项详情
xuanji project get --name "北京全量"
```

### data - 数据获取

```bash
xuanji data get --project "名称" [选项]    # 获取数据
xuanji data stats --project "名称"         # 数据统计
```

**选项：**

| 选项          | 说明                                   | 默认值 |
| ------------- | -------------------------------------- | ------ |
| `--project` | 专项名称                               | 必填   |
| `--limit`   | 获取条数                               | 100    |
| `--format`  | 输出格式：`jsonl`/`json`/`table` | jsonl  |

**示例：**

```bash
# 获取 500 条数据，JSON 格式保存
xuanji data get --project "北京全量" --limit 500 --format json > data.json

# 查看数据统计
xuanji data stats --project "北京全量"

# 表格形式预览
xuanji data get --project "北京全量" --limit 10 --format table
```

### analyze - AI 分析

```bash
xuanji analyze --functions <功能列表> [选项]
xuanji functions                            # 列出所有分析功能
```

**可用分析功能：**

| 功能           | 说明                                 |
| -------------- | ------------------------------------ |
| `summary`    | 生成整体摘要，概括舆情主要内容和趋势 |
| `sentiment`  | 情感分析，统计正面/负面/中性情绪分布 |
| `opinion`    | 观点提取，识别主要立场和意见分歧     |
| `topics`     | 主题聚类，识别讨论热点和话题分布     |
| `entities`   | 实体识别，提取人名、地名、机构名等   |
| `kol`        | KOL 分析，识别关键意见领袖及其影响力 |
| `geography`  | 地域分析，识别舆情传播的地域分布     |
| `engagement` | 互动分析，分析点赞、转发、评论数据   |

**示例：**

```bash
# 从管道读取数据进行分析
xuanji data get --project "北京全量" | xuanji analyze --functions summary,opinion

# 多功能分析
xuanji data get --project "北京全量" | xuanji analyze --functions summary,sentiment,opinion,topics
```

### report - 报告生成

```bash
xuanji report --output <文件名> [选项]
xuanji templates                            # 列出所有报告模板
```

**可用模板：**

| 模板                    | 说明                 |
| ----------------------- | -------------------- |
| `opinion-analysis`    | 观点分析报告（默认） |
| `sentiment-dashboard` | 情感分析仪表盘       |
| `briefing`            | 执行简报             |

**示例：**

```bash
# 使用默认模板生成报告
xuanji data get --project "北京全量" | \
    xuanji analyze --functions summary,opinion | \
    xuanji report --output report.md

# 使用情感仪表盘模板
xuanji data get --project "北京全量" | \
    xuanji analyze --functions sentiment | \
    xuanji report --template sentiment-dashboard --output sentiment.md
```

### workflow - 工作流编排

```bash
xuanji workflow run [选项]                  # 完整工作流
xuanji workflow quick <项目名> <输出文件>    # 快速工作流
```

**选项：**

| 选项           | 说明         | 默认值           |
| -------------- | ------------ | ---------------- |
| `--project`  | 专项名称     | 必填             |
| `--keyword`  | 搜索关键词   | -                |
| `--limit`    | 数据条数     | 100              |
| `--analysis` | 分析功能列表 | summary,opinion  |
| `--template` | 报告模板     | opinion-analysis |
| `--output`   | 输出文件     | 必填             |

**示例：**

```bash
# 快速工作流（使用配置默认值）
xuanji workflow quick "北京全量" "daily-report.md"

# 完整工作流（自定义参数）
xuanji workflow run \
    --project "北京全量" \
    --keyword "北京&舆情" \
    --limit 500 \
    --analysis summary,sentiment,opinion \
    --template opinion-analysis \
    --output "comprehensive-report.md"
```

---

## 高级用法

### 大规模数据分析（MapReduce）

当数据量超过 100 条时，xuanji-cli 自动启用 MapReduce 模式：

1. **Map 阶段**：数据分块（每块 50 条），使用轻量模型并行分析
2. **Reduce 阶段**：合并子结果，使用主模型生成最终报告

```bash
# 分析 500 条数据（自动启用 MapReduce）
xuanji data get --project "北京全量" --limit 500 | \
    xuanji analyze --functions summary,opinion
```

**配置轻量模型以降低成本：**

```bash
xuanji config set llm_light.model_name "qwen3.5-flash"
```

### 数据导出

```bash
# 导出为 JSON
xuanji data get --project "北京全量" --limit 500 --format json > data.json

# 导出为 JSON Lines（便于流式处理）
xuanji data get --project "北京全量" --limit 500 --format jsonl > data.jsonl
```

### 自定义分析管道

```bash
# 获取数据 → 多维度分析 → 生成情感仪表盘
xuanji data get --project "北京全量" --limit 500 | \
    xuanji analyze --functions summary,sentiment,opinion,topics,entities | \
    xuanji report --template sentiment-dashboard --output "dashboard.md"
```

---

## 项目结构

```
xuanji-cli/
├── xuanji/
│   ├── __init__.py
│   ├── cli.py                  # CLI 入口
│   ├── commands/               # 子命令
│   │   ├── config.py           # 配置管理
│   │   ├── project.py          # 专项管理
│   │   ├── data.py             # 数据获取
│   │   ├── analyze.py          # AI 分析
│   │   ├── report.py           # 报告生成
│   │   └── workflow.py         # 工作流编排
│   ├── core/                   # 核心模块
│   │   ├── models.py           # 数据模型
│   │   ├── analyzer.py         # AI 分析引擎（含 MapReduce）
│   │   └── llm.py              # LLM 客户端
│   ├── templates/              # 报告模板
│   │   ├── opinion-analysis.md.j2
│   │   ├── sentiment-dashboard.md.j2
│   │   └── briefing.md.j2
│   └── vendor/                 # 第三方封装
│       └── project_mcp.py      # project-mcp 包装器
├── tests/                      # 测试
├── pyproject.toml              # 项目配置
└── README.md
```

---

## 依赖

- **Python** >= 3.9
- **click** - CLI 框架
- **jinja2** - 模板引擎
- **pydantic** - 数据验证
- **tabulate** - 表格输出
- **httpx** - HTTP 客户端
- **project-mcp** - 底层数据获取（需单独安装）

---

## 常见问题

### Q: 提示 "LLM 未配置"

运行 `xuanji config init` 配置 LLM 参数，或手动设置：

```bash
xuanji config set llm.base_url "https://api.openai.com/v1/"
xuanji config set llm.api_key "sk-xxx"
xuanji config set llm.model_name "gpt-4"
```

### Q: 如何降低 API 调用成本？

配置轻量模型用于 MapReduce 子任务：

```bash
xuanji config set llm_light.model_name "qwen3.5-flash"
```

### Q: 数据量很大，分析很慢？

xuanji-cli 会自动启用 MapReduce 并行处理。你也可以减少数据量：

```bash
xuanji workflow run --project "项目" --limit 200 --output "report.md"
```

---

## License

MIT

---
name: xuanji-cli
description: |
  舆情分析工作流 CLI 工具，用于从数据获取到 AI 分析再到报告生成的一站式解决方案。

  触发场景：
  - 用户提到"舆情分析"、"舆情监控"、"舆情报告"
  - 用户需要创建、管理舆情监控专项
  - 用户需要获取舆情数据并进行 AI 分析（摘要、情感、观点、主题、实体）
  - 用户需要生成舆情分析报告
  - 用户提到 "xuanji"、"玄机" 相关命令
  - 用户需要执行完整的舆情分析工作流
  - 用户需要自定义分析维度（如原因分析、意义解读、行业启示等非模板维度）
---
# xuanji-cli 舆情分析工作流

## 前置条件

确保 xuanji CLI 已安装并可用：

```bash
xuanji --version
```

如未安装，执行：

```bash
# 安装 pipx（如果没有）
brew install pipx
pipx ensurepath

# 克隆并安装
git clone https://github.com/longGGGGGG/xuanji-cli.git
cd xuanji-cli
pipx install -e .

```

## 核心工作流

### 1. 快速分析（推荐）

一键执行完整工作流：

```bash
xuanji workflow quick "项目名称" "output.md"
```

### 2. 完整工作流

```bash
xuanji workflow run \
    --project "项目名称" \
    --keyword "关键词" \
    --limit 500 \
    --analysis summary,opinion \
    --template opinion-analysis \
    --output "report.md"
```

### 3. 管道组合

```bash
xuanji data get --project "项目名称" --limit 500 | \
    xuanji analyze --functions summary,sentiment,opinion | \
    xuanji report --template opinion-analysis --output "report.md"
```

## 命令参考

### 配置管理

```bash
xuanji config init                              # 交互式初始化
xuanji config show                              # 查看配置
xuanji config set llm.base_url "https://..."    # 设置 LLM URL
xuanji config set llm.api_key "sk-xxx"          # 设置 API Key
xuanji config set llm.model_name "gpt-4"        # 设置模型
```

### 专项管理

```bash
xuanji project list                             # 列出专项
xuanji project create "关键词" --name "名称"    # 创建专项
xuanji project delete <id>                      # 删除专项
xuanji project get --name "名称"                # 查看详情
```

### 数据获取

```bash
xuanji data get --project "名称" --limit 500    # 获取数据
xuanji data stats --project "名称"              # 数据统计
```

### AI 分析

```bash
xuanji functions                                # 列出分析功能
xuanji analyze --functions summary,opinion      # 执行分析
```

可用分析功能：`summary`（摘要）、`sentiment`（情感）、`opinion`（观点）、`topics`（主题）、`entities`（实体）

### 报告生成

```bash
xuanji templates                                # 列出模板
xuanji report --output report.md                # 生成报告
xuanji report --template briefing --output r.md # 指定模板
```

可用模板：`opinion-analysis`（观点分析）、`sentiment-dashboard`（情感仪表盘）、`briefing`（执行简报）

## 大规模数据分析（MapReduce）

对于大数据量分析，可以**手动启用** MapReduce 模式（通过 `--mapreduce` 参数）：

1. **Map 阶段**：数据分块（每块 50 条），使用轻量模型并行分析
2. **Reduce 阶段**：合并子结果，使用主模型生成最终报告

**默认行为**：不启用 MapReduce，使用分层采样策略（智能采样 + 主模型分析）。

```bash
# 启用 MapReduce 分析 500 条数据
xuanji workflow run --project "北京全量" --limit 500 --mapreduce --output report.md
```

## 典型使用场景

1. **日常舆情监控**：`xuanji workflow quick "北京全量" "daily-report.md"`
2. **深度观点分析**：`xuanji workflow run --project "项目" --analysis summary,opinion,sentiment --output "analysis.md"`
3. **数据导出**：`xuanji data get --project "项目" --format json > data.json`

## 自定义分析维度

当用户请求的分析维度不在内置功能（summary/sentiment/opinion/topics/entities）中时，采用以下流程：

### 判断标准

内置维度直接使用 xuanji CLI：

- 摘要、总结 → `summary`
- 情感、情绪 → `sentiment`
- 观点、看法 → `opinion`
- 主题、话题 → `topics`
- 实体、人物、机构 → `entities`

自定义维度由 LLM 直接分析：

- 原因分析（如"分析 xxx 的原因"）
- 意义解读（如"这件事的意义是什么"）
- 行业启示（如"对传统 SaaS 厂商的启示"）
- 趋势预测、风险评估、对比分析等

### 自定义分析流程

1. **获取数据**：使用 xuanji CLI 获取舆情数据

   ```bash
   xuanji data get --project "项目名" --limit 500 --format json > data.json
   ```
2. **读取数据**：将数据加载到上下文，根据数据量进行适当截断

   - 数据量 < 50 条：全量加载
   - 数据量 50-200 条：保留标题、摘要、关键字段，省略正文详情
   - 数据量 > 200 条：采样代表性数据（按时间/来源分层采样），或先用 xuanji 内置 `summary` 生成摘要后再分析
3. **LLM 直接分析**：根据用户指定的维度，由 LLM 直接对截断后的数据进行分析并输出结果

### 示例

用户请求："分析这些舆情数据对传统 SaaS 厂商的启示"

执行步骤：

1. 运行 `xuanji data get --project "项目" --format json` 获取数据
2. 读取数据内容
3. LLM 根据数据内容，从"对传统 SaaS 厂商的启示"角度进行深度分析
4. 输出分析报告（可保存为 markdown 文件）

### 混合模式

可同时使用内置维度和自定义维度：

1. 先用 xuanji CLI 执行内置分析（如 summary, sentiment）
2. 再由 LLM 补充自定义维度分析
3. 整合输出完整报告

"""Orchestrated workflow commands"""
import json
import os
from datetime import datetime
from pathlib import Path

import click

from xuanji.vendor.project_mcp import ProjectMCPClientSync as ProjectMCPClient, ProjectMCPError
from xuanji.core.analyzer import AIAnalyzer, MapReduceAnalyzer, LLMError
from xuanji.core.models import AnalysisResult
from xuanji.commands.report import generate_report
from xuanji.commands.config import get_config


@click.group(name='workflow')
def workflow_cmd():
    """工作流 - 一键执行完整分析流程"""
    pass


@workflow_cmd.command(name='run')
@click.option('--project', '-p', help='专项名称（默认使用配置中的 default_project）')
@click.option('--keyword', '-k', help='关键词（专项不存在时自动创建）')
@click.option('--limit', '-l', type=int, help='数据数量限制（默认使用配置中的 default_limit）')
@click.option('--analysis', '-a', help='分析功能，逗号分隔（默认使用配置中的 default_analysis）')
@click.option('--output', '-o', required=True, help='输出文件路径')
@click.option('--template', '-t', default='opinion-analysis', help='报告模板')
@click.option('--mapreduce', is_flag=True, help='使用 MapReduce 架构（大数据量推荐，子任务用 qwen3.5-flash）')
@click.option('--chunk-size', type=int, default=50, help='MapReduce 每块数据量（默认50条）')
def run_workflow(project, keyword, limit, analysis, output, template, mapreduce, chunk_size):
    """一键运行完整工作流
    
    需要先配置 LLM 参数：
        xuanji config set llm.base_url "https://api.example.com/v1/"
        xuanji config set llm.api_key "your-api-key"
        xuanji config set llm.model_name "gpt-4"
    
    示例:
        xuanji workflow run \\
            --project "北京全量" \\
            --keyword "北京&舆情" \\
            --limit 500 \\
            --analysis summary,opinion \\
            --output "北京全量舆情观点分析.md"
    """
    # Load config defaults
    config = get_config()
    
    project = project or config.get('default_project')
    if not project:
        click.echo("错误: 请指定 --project 或在配置中设置 default_project", err=True)
        raise click.Abort()
    
    limit = limit if limit is not None else config.get('default_limit', 100)
    analysis = analysis or config.get('default_analysis', 'summary,opinion')
    
    client = ProjectMCPClient()
    
    click.echo(f"[1/4] 检查专项 '{project}'...")
    try:
        project_info = client.get_project_by_name(project)
        if project_info:
            click.echo(f"      找到专项 (ID: {project_info.id})")
        elif keyword:
            click.echo(f"      创建新专项...")
            project_info = client.create_project(keyword, project)
            click.echo(f"      已创建 (ID: {project_info.id})")
        else:
            click.echo(f"错误: 专项不存在且未提供关键词", err=True)
            raise click.Abort()
    except ProjectMCPError as e:
        click.echo(f"错误: {e}", err=True)
        raise click.Abort()
    
    click.echo(f"[2/4] 获取数据 (limit={limit})...")
    try:
        posts = client.get_data(project_info.id, project, limit=limit)
        click.echo(f"      获取到 {len(posts)} 条数据")
    except ProjectMCPError as e:
        click.echo(f"错误: {e}", err=True)
        raise click.Abort()
    
    click.echo(f"[3/4] AI 分析 ({analysis})...")
    
    function_list = [f.strip() for f in analysis.split(',')]
    analyses = []
    
    if mapreduce:
        # MapReduce 模式：大数据量全量分析
        click.echo(f"      使用 MapReduce 架构（子任务模型: qwen3.5-flash）")
        
        llm_config = config.get('llm', {})
        base_url = llm_config.get('base_url')
        api_key = llm_config.get('api_key')
        main_model = llm_config.get('model_name', 'qwen3.5-plus')
        
        if not base_url or not api_key:
            click.echo("错误: 使用 MapReduce 需要配置 LLM 参数", err=True)
            raise click.Abort()
        
        mr_analyzer = MapReduceAnalyzer(
            main_base_url=base_url,
            main_api_key=api_key,
            main_model=main_model,
            sub_model="qwen3.5-flash",  # 轻量模型
            chunk_size=chunk_size,
            max_workers=3
        )
        
        for func_name in function_list:
            if func_name not in mr_analyzer.get_available_functions():
                click.echo(f"      跳过未知功能: {func_name}")
                continue
            
            click.echo(f"      分析: {func_name}...")
            try:
                result = mr_analyzer.analyze(posts, func_name)
                analyses.append(result)
                click.echo(f"        ✓ 完成（使用 {result.metadata.get('chunks', 1)} 个子任务）")
            except Exception as e:
                click.echo(f"        ✗ 失败: {e}")
                analyses.append(AnalysisResult(
                    function=func_name,
                    content=f"[分析失败: {e}]",
                    metadata={'error': str(e)}
                ))
    else:
        # 标准模式：采样分析
        try:
            analyzer = AIAnalyzer()
        except LLMError as e:
            click.echo(f"错误: {e}", err=True)
            raise click.Abort()
        
        available = analyzer.get_available_functions()
        valid_functions = [f for f in function_list if f in available]
        analyses = analyzer.analyze_multi(posts, valid_functions)
    
    click.echo(f"      完成 {len(analyses)} 项分析")
    
    click.echo(f"[4/4] 生成报告...")
    report_content = generate_report(
        posts=posts,
        analyses=analyses,
        template_name=template,
        title=f"{project} - 舆情分析报告",
        project_name=project
    )
    
    output_path = Path(output)
    output_path.write_text(report_content, encoding='utf-8')
    click.echo(f"      ✓ 报告已保存: {output}")


@workflow_cmd.command(name='quick')
@click.argument('project')
@click.argument('output')
def quick_workflow(project, output):
    """快速运行默认工作流
    
    PROJECT: 专项名称
    OUTPUT: 输出文件路径
    
    示例:
        xuanji workflow quick "北京全量" "report.md"
    """
    ctx = click.Context(run_workflow)
    ctx.invoke(
        run_workflow,
        project=project,
        keyword=None,
        limit=None,
        analysis=None,
        output=output,
        template='opinion-analysis'
    )

"""AI analysis commands"""
import json
import sys

import click

from xuanji.core.analyzer import AIAnalyzer, LLMError
from xuanji.commands.config import get_config
from xuanji.core.models import Post


@click.command(name='analyze')
@click.option('--functions', '-f', default=None,
              help='分析功能，逗号分隔: summary,sentiment,opinion,topics,entities（默认使用配置文件中的 default_analysis）')
@click.option('--output', '-o', type=click.Choice(['json', 'pretty']), default='json')
def analyze_cmd(functions, output):
    """AI 分析舆情数据
    
    从 stdin 读取 JSON Lines 格式的帖子数据，输出分析结果。
    
    需要先配置 LLM 参数：
        xuanji config set llm.base_url "https://api.example.com/v1/"
        xuanji config set llm.api_key "your-api-key"
        xuanji config set llm.model_name "gpt-4"
    
    示例:
        xuanji data get --project "北京全量" | xuanji analyze --functions summary,opinion
    """
    # 如果未指定 functions，从配置文件读取默认值
    if functions is None:
        config = get_config()
        functions = config.get('default_analysis', 'summary')
        # 处理配置文件中可能带引号的情况
        functions = functions.strip('"\'')
    
    function_list = [f.strip() for f in functions.split(',')]
    
    posts = []
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            posts.append(Post(**data))
        except (json.JSONDecodeError, TypeError) as e:
            click.echo(f"警告: 跳过无效数据行: {e}", err=True)
            continue
    
    if not posts:
        click.echo("错误: 没有有效的输入数据", err=True)
        raise click.Abort()
    
    click.echo(f"正在分析 {len(posts)} 条数据...", err=True)
    
    try:
        analyzer = AIAnalyzer()
    except LLMError as e:
        click.echo(f"错误: {e}", err=True)
        raise click.Abort()
    
    available = analyzer.get_available_functions()
    invalid = [f for f in function_list if f not in available]
    if invalid:
        click.echo(f"错误: 未知的分析功能: {', '.join(invalid)}", err=True)
        click.echo(f"可用功能: {', '.join(available.keys())}", err=True)
        raise click.Abort()
    
    results = analyzer.analyze_multi(posts, function_list)
    
    if output == 'json':
        for result in results:
            click.echo(json.dumps(result.model_dump(), ensure_ascii=False))
    else:
        for result in results:
            source = result.metadata.get('source', 'unknown')
            model = result.metadata.get('model', 'unknown')
            click.echo(f"\n{'='*50}", err=True)
            click.echo(f"分析类型: {result.function} (来源: {source}, 模型: {model})", err=True)
            click.echo(f"{'='*50}", err=True)
            click.echo(result.content)


@click.command(name='functions')
def list_functions():
    """列出可用的分析功能"""
    try:
        analyzer = AIAnalyzer()
    except LLMError:
        click.echo("错误: 请先配置 LLM 参数")
        click.echo('  xuanji config set llm.base_url "https://api.example.com/v1/"')
        click.echo('  xuanji config set llm.api_key "your-api-key"')
        click.echo('  xuanji config set llm.model_name "gpt-4"')
        return
    
    functions = analyzer.get_available_functions()
    
    click.echo("可用的分析功能:\n")
    for name, func in functions.items():
        click.echo(f"  {name:12} - {func.description}")
    
    click.echo("\n使用示例:")
    click.echo('  xuanji data get --project "北京全量" | xuanji analyze --functions summary,opinion')

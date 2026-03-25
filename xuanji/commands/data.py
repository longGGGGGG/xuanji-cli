"""Data fetching commands"""
import json
import sys

import click

from xuanji.vendor.project_mcp import ProjectMCPClientSync as ProjectMCPClient, ProjectMCPError


@click.group(name='data')
def data_cmd():
    """数据获取 - 从专项获取舆情数据"""
    pass


@data_cmd.command(name='get')
@click.option('--project', '-p', required=True, help='专项名称')
@click.option('--limit', '-l', type=int, default=100, help='限制返回数量')
@click.option('--format', 'output_format', type=click.Choice(['jsonl', 'json', 'table']), default='jsonl')
def get_data(project, limit, output_format):
    """获取专项数据
    
    默认输出 JSON Lines 格式，便于管道处理
    """
    client = ProjectMCPClient()
    
    try:
        project_info = client.get_project_by_name(project)
        if not project_info:
            click.echo(f"错误: 未找到专项 '{project}'", err=True)
            raise click.Abort()
        
        click.echo(f"正在获取专项 '{project}' 的数据...", err=True)
        
        posts = client.get_data(project_info.id, project, limit=limit)
        
        click.echo(f"获取到 {len(posts)} 条数据", err=True)
        
        if output_format == 'jsonl':
            for post in posts:
                click.echo(json.dumps(post.model_dump(), ensure_ascii=False))
        
        elif output_format == 'json':
            click.echo(json.dumps(
                [p.model_dump() for p in posts],
                indent=2,
                ensure_ascii=False
            ))
        
        else:
            click.echo(f"{'ID':<20} {'来源':<10} {'时间':<20} {'内容':<50}")
            click.echo("-" * 100)
            for p in posts:
                content = p.content[:47] + '...' if len(p.content) > 50 else p.content
                click.echo(f"{p.id[:20]:<20} {p.source:<10} {p.time:<20} {content:<50}")
    
    except ProjectMCPError as e:
        click.echo(f"错误: {e}", err=True)
        raise click.Abort()


@data_cmd.command(name='stats')
@click.option('--project', '-p', required=True, help='专项名称')
def data_stats(project):
    """获取数据统计信息"""
    client = ProjectMCPClient()
    
    try:
        project_info = client.get_project_by_name(project)
        if not project_info:
            click.echo(f"错误: 未找到专项 '{project}'", err=True)
            raise click.Abort()
        
        posts = client.get_data(project_info.id, project)
        
        sources = {}
        for p in posts:
            sources[p.source] = sources.get(p.source, 0) + 1
        
        click.echo(f"专项: {project}")
        click.echo(f"总数据量: {len(posts)}")
        click.echo("")
        click.echo("来源分布:")
        for source, count in sorted(sources.items(), key=lambda x: -x[1]):
            click.echo(f"  {source}: {count}")
    
    except ProjectMCPError as e:
        click.echo(f"错误: {e}", err=True)
        raise click.Abort()

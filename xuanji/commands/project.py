"""Project management commands"""
import json
import click

from xuanji.vendor.project_mcp import ProjectMCPClientSync as ProjectMCPClient
from xuanji.core.errors import XuanjiError


@click.group(name='project')
def project_cmd():
    """专项管理 - 创建、查看、删除舆情监控专项"""
    pass


def _handle_error(e: XuanjiError):
    """统一错误处理：输出结构化错误信息，便于 client 获取和 LLM 自我修复
    
    输出格式：
    - 人类可读的错误信息
    - 修复建议
    - [ERROR_JSON]{...}[/ERROR_JSON] 供程序解析
    """
    click.echo(f"错误: {e.message}", err=True)
    if e.suggestion:
        click.echo(f"建议: {e.suggestion}", err=True)
    # 输出 JSON 格式的详细错误信息（供程序解析）
    click.echo(f"[ERROR_JSON]{e.to_json()}[/ERROR_JSON]", err=True)
    raise click.Abort()


@project_cmd.command(name='list')
@click.option('--format', 'output_format', type=click.Choice(['table', 'json']), default='table')
def list_projects(output_format):
    """列出所有专项"""
    client = ProjectMCPClient()
    
    try:
        projects = client.list_projects()
        
        if not projects:
            click.echo("暂无专项")
            return
        
        if output_format == 'json':
            import json
            click.echo(json.dumps(projects, indent=2, ensure_ascii=False))
        else:
            click.echo(f"{'ID':<10} {'名称':<30} {'关键词':<20}")
            click.echo("-" * 60)
            for p in projects:
                click.echo(f"{p.get('id', 'N/A'):<10} {p.get('name', 'N/A'):<30} {p.get('keyword', 'N/A'):<20}")
    
    except XuanjiError as e:
        _handle_error(e)


@project_cmd.command(name='create')
@click.argument('keyword')
@click.option('--name', '-n', required=True, help='专项名称')
@click.option('--format', 'output_format', type=click.Choice(['table', 'json']), default='table')
def create_project(keyword, name, output_format):
    """创建新专项
    
    KEYWORD: 关键词表达式，支持 & (与) | (或) 逻辑运算符
    例如: "北京&火锅" 或 "北京|上海"
    """
    client = ProjectMCPClient()
    
    try:
        existing = client.get_project_by_name(name)
        if existing:
            click.echo(f"专项 '{name}' 已存在 (ID: {existing.id})")
            return
        
        project = client.create_project(keyword, name)
        
        if output_format == 'json':
            import json
            click.echo(json.dumps(project.model_dump(), indent=2, ensure_ascii=False))
        else:
            click.echo(f"✓ 专项创建成功")
            click.echo(f"  ID: {project.id}")
            click.echo(f"  名称: {project.name}")
            click.echo(f"  关键词: {project.keyword}")
    
    except XuanjiError as e:
        _handle_error(e)


@project_cmd.command(name='delete')
@click.argument('project_id')
@click.confirmation_option(prompt='确定要删除这个专项吗?')
def delete_project(project_id):
    """删除专项"""
    client = ProjectMCPClient()
    
    try:
        if client.delete_project(project_id):
            click.echo(f"✓ 专项 {project_id} 已删除")
        else:
            click.echo(f"✗ 删除失败", err=True)
            raise click.Abort()
    
    except XuanjiError as e:
        _handle_error(e)


@project_cmd.command(name='get')
@click.option('--name', '-n', help='按名称查找')
@click.option('--id', '-i', help='按ID查找')
def get_project(name, id):
    """获取专项详情"""
    if not name and not id:
        click.echo("错误: 请提供 --name 或 --id", err=True)
        raise click.Abort()
    
    client = ProjectMCPClient()
    
    try:
        if id:
            projects = client.list_projects()
            project = next((p for p in projects if p.get('id') == id), None)
        else:
            p = client.get_project_by_name(name)
            project = p.model_dump() if p else None
        
        if not project:
            click.echo("未找到专项")
            return
        
        click.echo(f"ID: {project.get('id')}")
        click.echo(f"名称: {project.get('name')}")
        click.echo(f"关键词: {project.get('keyword', 'N/A')}")
    
    except XuanjiError as e:
        _handle_error(e)

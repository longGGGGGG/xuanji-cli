"""Configuration management commands"""
import json
import os
from pathlib import Path

import click

CONFIG_DIR = Path.home() / '.xuanji'
CONFIG_FILE = CONFIG_DIR / 'config.json'


def get_config() -> dict:
    """读取配置"""
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
    return {}


def save_config(config: dict):
    """保存配置"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding='utf-8')


@click.group(name='config')
def config_cmd():
    """配置管理 - 查看和设置默认参数"""
    pass


@config_cmd.command(name='show')
def show_config():
    """显示当前配置"""
    config = get_config()
    
    if not config:
        click.echo("暂无配置")
        click.echo(f"\n配置文件位置: {CONFIG_FILE}")
        click.echo("\n建议运行: xuanji config init")
        return
    
    click.echo("当前配置:\n")
    for key, value in config.items():
        if isinstance(value, dict):
            click.echo(f"  {key}:")
            for sub_key, sub_value in value.items():
                if 'key' in sub_key.lower() and sub_value:
                    click.echo(f"    {sub_key}: ****{str(sub_value)[-4:]}")
                else:
                    click.echo(f"    {sub_key}: {sub_value}")
        else:
            click.echo(f"  {key}: {value}")
    
    click.echo(f"\n配置文件位置: {CONFIG_FILE}")


@config_cmd.command(name='set')
@click.argument('key')
@click.argument('value')
def set_config(key, value):
    """设置配置项
    
    KEY: 配置项名称，支持嵌套（如 llm.api_key）
    VALUE: 配置项值
    
    常用配置:
        llm.base_url          - LLM API 基础 URL
        llm.api_key           - LLM API 密钥
        llm.model_name        - 模型名称
        llm_light.base_url    - 轻量模型 API URL（可选，默认同 llm）
        llm_light.api_key     - 轻量模型 API Key（可选，默认同 llm）
        llm_light.model_name  - 轻量模型名称（如 qwen3.5-flash）
        default_project       - 默认专项名称
        default_limit         - 默认数据条数
        default_analysis      - 默认分析功能
    
    示例:
        xuanji config set llm.base_url "https://api.openai.com/v1/"
        xuanji config set llm.api_key "sk-xxx"
        xuanji config set llm.model_name "gpt-4"
        xuanji config set llm_light.model_name "qwen3.5-flash"
    """
    config = get_config()
    
    # 处理嵌套键（如 llm.api_key）
    keys = key.split('.')
    current = config
    for k in keys[:-1]:
        if k not in current:
            current[k] = {}
        current = current[k]
    
    final_key = keys[-1]
    
    # 尝试解析为 number 或 boolean
    if value.lower() in ('true', 'false'):
        value = value.lower() == 'true'
    else:
        try:
            if '.' in value:
                value = float(value)
            else:
                value = int(value)
        except ValueError:
            pass  # 保持为字符串
    
    current[final_key] = value
    save_config(config)
    
    click.echo(f"✓ 已设置: {key} = {value if not isinstance(value, str) or 'key' not in key.lower() else '****'}")


@config_cmd.command(name='get')
@click.argument('key')
def get_config_value(key):
    """获取配置项值"""
    config = get_config()
    
    # 处理嵌套键
    keys = key.split('.')
    current = config
    for k in keys:
        if isinstance(current, dict) and k in current:
            current = current[k]
        else:
            click.echo(f"未设置: {key}", err=True)
            raise click.Abort()
    
    click.echo(current)


@config_cmd.command(name='unset')
@click.argument('key')
def unset_config(key):
    """删除配置项"""
    config = get_config()
    
    # 处理嵌套键
    keys = key.split('.')
    current = config
    for k in keys[:-1]:
        if isinstance(current, dict) and k in current:
            current = current[k]
        else:
            click.echo(f"未设置: {key}")
            return
    
    final_key = keys[-1]
    if final_key in current:
        del current[final_key]
        save_config(config)
        click.echo(f"✓ 已删除: {key}")
    else:
        click.echo(f"未设置: {key}")


@config_cmd.command(name='init')
def init_config():
    """交互式初始化配置"""
    click.echo("xuanji-cli 配置向导\n")
    
    config = get_config()
    
    if 'llm' not in config:
        config['llm'] = {}
    
    click.echo("=" * 50)
    click.echo("主模型配置（用于 AI 分析）")
    click.echo("=" * 50)
    click.echo("支持的提供商：OpenAI, Kimi, Claude, 本地模型等\n")
    
    # Base URL
    default_base_url = config['llm'].get('base_url', 'https://api.openai.com/v1/')
    base_url = click.prompt(
        "LLM Base URL",
        default=default_base_url
    )
    config['llm']['base_url'] = base_url
    
    # API Key
    default_api_key = config['llm'].get('api_key', '')
    api_key = click.prompt(
        "LLM API Key",
        default=default_api_key,
        hide_input=True,
        show_default=False
    )
    if api_key:
        config['llm']['api_key'] = api_key
    
    # Model Name
    default_model = config['llm'].get('model_name', 'gpt-4')
    model_name = click.prompt(
        "Model Name",
        default=default_model
    )
    config['llm']['model_name'] = model_name
    
    click.echo("\n" + "=" * 50)
    click.echo("轻量模型配置（用于 MapReduce 子任务，可选）")
    click.echo("=" * 50)
    click.echo("轻量模型用于大规模数据分块处理，速度更快、成本更低\n")
    
    if 'llm_light' not in config:
        config['llm_light'] = {}
    
    # 轻量模型名称
    default_light_model = config['llm_light'].get('model_name', 'qwen3.5-flash')
    light_model = click.prompt(
        "轻量模型名称 (按Enter使用默认值)",
        default=default_light_model
    )
    if light_model:
        config['llm_light']['model_name'] = light_model
    
    # 轻量模型 URL（可选，默认同主模型）
    use_same_url = click.confirm(
        "轻量模型使用与主模型相同的 API URL?",
        default=True
    )
    if not use_same_url:
        light_base_url = click.prompt(
            "轻量模型 Base URL",
            default=config['llm_light'].get('base_url', '')
        )
        if light_base_url:
            config['llm_light']['base_url'] = light_base_url
        
        light_api_key = click.prompt(
            "轻量模型 API Key",
            default='',
            hide_input=True,
            show_default=False
        )
        if light_api_key:
            config['llm_light']['api_key'] = light_api_key
    
    click.echo("\n" + "=" * 50)
    click.echo("默认参数配置")
    click.echo("=" * 50 + "\n")
    
    # Default project
    default_project = click.prompt(
        "默认专项名称 (可选，按Enter跳过)",
        default=config.get('default_project', '')
    )
    if default_project:
        config['default_project'] = default_project
    
    # Default limit
    default_limit = click.prompt(
        "默认数据条数",
        default=config.get('default_limit', 100),
        type=int
    )
    config['default_limit'] = default_limit
    
    # Default analysis functions
    default_analysis = click.prompt(
        "默认分析功能",
        default=config.get('default_analysis', 'summary,opinion')
    )
    config['default_analysis'] = default_analysis
    
    save_config(config)
    
    click.echo(f"\n✓ 配置已保存到: {CONFIG_FILE}")
    click.echo("\n当前配置:")
    
    if 'llm' in config:
        click.echo("  llm:")
        for key, value in config['llm'].items():
            if 'key' in key.lower() and value:
                click.echo(f"    {key}: ****{str(value)[-4:]}")
            else:
                click.echo(f"    {key}: {value}")
    
    if 'llm_light' in config:
        click.echo("  llm_light:")
        for key, value in config['llm_light'].items():
            if 'key' in key.lower() and value:
                click.echo(f"    {key}: ****{str(value)[-4:]}")
            else:
                click.echo(f"    {key}: {value}")
    
    for key, value in config.items():
        if key not in ('llm', 'llm_light'):
            click.echo(f"  {key}: {value}")
    

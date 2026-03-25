"""Report generation commands"""
import json
import sys
from datetime import datetime
from pathlib import Path

import click
from jinja2 import Template

from xuanji.core.models import Post, AnalysisResult
from xuanji.templates import get_template_path, list_templates


@click.command(name='report')
@click.option('--template', '-t', default='opinion-analysis',
              help='报告模板名称')
@click.option('--output', '-o', type=click.File('w'), default='-',
              help='输出文件路径 (默认: stdout)')
@click.option('--title', help='报告标题')
@click.option('--project', '-p', help='项目名称')
def report_cmd(template, output, title, project):
    """生成分析报告
    
    从 stdin 读取帖子数据和AI分析结果，生成 Markdown 报告。
    
    示例:
        xuanji data get --project "北京全量" | \\
            xuanji analyze --functions summary,opinion | \\
            xuanji report --output report.md
    """
    posts = []
    analyses = []
    
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            if 'function' in data and 'content' in data:
                analyses.append(AnalysisResult(**data))
            elif 'id' in data and 'content' in data:
                posts.append(Post(**data))
        except (json.JSONDecodeError, TypeError) as e:
            click.echo(f"警告: 跳过无效数据: {e}", err=True)
    
    if not posts and not analyses:
        click.echo("错误: 没有有效的输入数据", err=True)
        raise click.Abort()
    
    report = generate_report(
        posts=posts,
        analyses=analyses,
        template_name=template,
        title=title or f"舆情分析报告 - {project or '未命名'}",
        project_name=project or '未命名项目'
    )
    
    output.write(report)
    
    if output.name != '<stdout>':
        click.echo(f"✓ 报告已保存至: {output.name}", err=True)


def generate_report(
    posts: list[Post],
    analyses: list[AnalysisResult],
    template_name: str,
    title: str,
    project_name: str
) -> str:
    """Generate report from template"""
    
    context = {
        'title': title,
        'project_name': project_name,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'metadata': {
            'post_count': len(posts),
            'source_count': len(set(p.source for p in posts)) if posts else 0,
            'analysis_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        },
        'sample_posts': posts[:5],
        'summary': '',
        'opinion_analysis': '',
        'sentiment_analysis': '',
        'kol_analysis': '',
        'geography_analysis': '',
        'engagement_analysis': '',
        'topics_analysis': '',
        'entities_analysis': '',
    }
    
    for analysis in analyses:
        if analysis.function == 'summary':
            context['summary'] = analysis.content
        elif analysis.function == 'opinion':
            context['opinion_analysis'] = analysis.content
        elif analysis.function == 'sentiment':
            context['sentiment_analysis'] = analysis.content
        elif analysis.function == 'kol':
            context['kol_analysis'] = analysis.content
        elif analysis.function == 'geography':
            context['geography_analysis'] = analysis.content
        elif analysis.function == 'engagement':
            context['engagement_analysis'] = analysis.content
        elif analysis.function == 'topics':
            context['topics_analysis'] = analysis.content
        elif analysis.function == 'entities':
            context['entities_analysis'] = analysis.content
        else:
            context[f"{analysis.function}_analysis"] = analysis.content
    
    template_path = get_template_path(template_name)
    if not template_path.exists():
        template_content = _get_default_template()
    else:
        template_content = template_path.read_text(encoding='utf-8')
    
    template = Template(template_content)
    return template.render(**context)


def _get_default_template() -> str:
    """Get default inline template"""
    return """# {{ title }}

**项目名称:** {{ project_name }}
**生成时间:** {{ generated_at }}
**数据量:** {{ metadata.post_count }} 条

---

{% if summary %}
## 摘要

{{ summary }}

{% endif %}

{% if opinion_analysis %}
## 观点分析

{{ opinion_analysis }}

{% endif %}

{% if sentiment_analysis %}
## 情感分析

{{ sentiment_analysis }}

{% endif %}

{% if kol_analysis %}
## KOL分析

{{ kol_analysis }}

{% endif %}

{% if geography_analysis %}
## 地域分布

{{ geography_analysis }}

{% endif %}

{% if engagement_analysis %}
## 互动分析

{{ engagement_analysis }}

{% endif %}

{% if topics_analysis %}
## 话题聚类

{{ topics_analysis }}

{% endif %}

{% if entities_analysis %}
## 实体识别

{{ entities_analysis }}

{% endif %}

---

*报告由 xuanji-cli 自动生成*
"""


@click.command(name='templates')
def list_templates_cmd():
    """列出可用的报告模板"""
    templates = list_templates()
    
    click.echo("可用的报告模板:\n")
    for name in templates:
        click.echo(f"  - {name}")

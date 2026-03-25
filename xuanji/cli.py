"""Main CLI entry point for xuanji"""
import click

from xuanji import __version__
from xuanji.commands.project import project_cmd
from xuanji.commands.data import data_cmd
from xuanji.commands.analyze import analyze_cmd, list_functions
from xuanji.commands.report import report_cmd, list_templates_cmd
from xuanji.commands.workflow import workflow_cmd
from xuanji.commands.config import config_cmd


@click.group()
@click.version_option(version=__version__, prog_name="xuanji")
@click.option('--verbose', '-v', is_flag=True, help='启用详细日志')
@click.pass_context
def cli(ctx, verbose):
    """xuanji - 舆情分析工作流 CLI 工具
    
    示例:
        xuanji project create "北京&舆情" --name "北京全量"
        xuanji data get --project "北京全量" --limit 500
        xuanji workflow run --project "北京全量" --analysis summary,opinion
    """
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose


cli.add_command(project_cmd)
cli.add_command(data_cmd)
cli.add_command(analyze_cmd)
cli.add_command(list_functions, name='functions')
cli.add_command(report_cmd)
cli.add_command(list_templates_cmd, name='templates')
cli.add_command(workflow_cmd)
cli.add_command(config_cmd)


def main():
    """Entry point"""
    cli()


if __name__ == '__main__':
    main()

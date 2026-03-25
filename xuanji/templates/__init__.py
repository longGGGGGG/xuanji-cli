"""Report templates"""
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent


def get_template_path(name: str) -> Path:
    """Get template file path"""
    return TEMPLATES_DIR / f"{name}.md.j2"


def list_templates() -> list[str]:
    """List available templates"""
    templates = []
    for f in TEMPLATES_DIR.glob("*.md.j2"):
        templates.append(f.stem.replace('.md', ''))
    return templates

"""Vendored project-mcp client from /Users/zhoulong/Desktop/SAAS-AutoSearch/project_mcp_cli

Original: https://github.com/golaxy/project_mcp_cli
License: MIT
"""

# Re-export the client
from .project_mcp import (
    ProjectMCPClient,
    ProjectMCPClientSync,
    ProjectMCPError,
    DEFAULT_BASE_URL,
)

__all__ = ['ProjectMCPClient', 'ProjectMCPClientSync', 'ProjectMCPError', 'DEFAULT_BASE_URL']

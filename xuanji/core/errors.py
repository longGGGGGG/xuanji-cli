"""Error handling with structured error info for LLM self-repair"""
import json
import traceback
from typing import Optional, Any
from datetime import datetime


class XuanjiError(Exception):
    """Base error with structured info for LLM self-repair
    
    设计目标：让大模型能够基于错误信息自动诊断和修复问题
    """
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        context: Optional[dict] = None,
        suggestion: Optional[str] = None,
        retryable: bool = False,
        original_error: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "UNKNOWN"
        self.context = context or {}
        self.suggestion = suggestion
        self.retryable = retryable
        self.original_error = original_error
        self.timestamp = datetime.now().isoformat()
        self.traceback = traceback.format_exc() if original_error else None
    
    def to_dict(self) -> dict:
        """转换为字典，便于 client 获取和 LLM 处理"""
        return {
            "error_type": self.__class__.__name__,
            "error_code": self.error_code,
            "message": self.message,
            "context": self.context,
            "suggestion": self.suggestion,
            "retryable": self.retryable,
            "timestamp": self.timestamp,
            "traceback": self.traceback,
        }
    
    def to_json(self) -> str:
        """JSON 格式，便于传输"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    def __str__(self) -> str:
        parts = [f"[{self.error_code}] {self.message}"]
        if self.suggestion:
            parts.append(f"建议: {self.suggestion}")
        if self.context:
            parts.append(f"上下文: {json.dumps(self.context, ensure_ascii=False)}")
        return " | ".join(parts)


class ProjectCreateError(XuanjiError):
    """专项创建错误"""
    
    def __init__(self, project_name: str, details: str, **kwargs):
        super().__init__(
            message=f"创建专项 '{project_name}' 失败: {details}",
            error_code="PROJECT_CREATE_FAILED",
            context={"project_name": project_name, "details": details},
            suggestion="1. 检查网络连接 2. 确认项目名称是否已存在 3. 稍后重试",
            retryable=True,
            **kwargs
        )


class DataFetchError(XuanjiError):
    """数据获取错误"""
    
    def __init__(self, project_id: str, reason: str, **kwargs):
        super().__init__(
            message=f"获取专项数据失败 (ID: {project_id}): {reason}",
            error_code="DATA_FETCH_FAILED",
            context={"project_id": project_id, "reason": reason},
            suggestion="1. 确认专项ID正确 2. 检查专项是否有数据 3. 检查权限",
            retryable=True,
            **kwargs
        )


class AnalysisError(XuanjiError):
    """AI 分析错误"""
    
    def __init__(self, function: str, reason: str, **kwargs):
        super().__init__(
            message=f"AI 分析失败 [{function}]: {reason}",
            error_code="ANALYSIS_FAILED",
            context={"function": function, "reason": reason},
            suggestion="1. 检查 LLM 配置 2. 减少数据量重试 3. 检查 API 密钥",
            retryable=True,
            **kwargs
        )


class ConfigError(XuanjiError):
    """配置错误"""
    
    def __init__(self, key: str, reason: str, **kwargs):
        super().__init__(
            message=f"配置错误 [{key}]: {reason}",
            error_code="CONFIG_ERROR",
            context={"config_key": key, "reason": reason},
            suggestion=f"运行 'xuanji config set {key} <value>' 修复",
            retryable=False,
            **kwargs
        )


# 兼容旧代码的别名
ProjectMCPError = XuanjiError

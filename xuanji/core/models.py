"""Core data models for xuanji-cli"""
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class Post(BaseModel):
    """舆情数据帖子模型 - 扩展版"""
    id: str
    title: Optional[str] = None
    content: str
    source: str = "unknown"
    time: str = ""
    url: Optional[str] = None
    author: Optional[str] = None
    sentiment: Optional[str] = None
    
    # 扩展字段（向后兼容，默认值为 None）
    author_id: Optional[str] = None
    author_alias: Optional[str] = None
    location: Optional[list[str]] = None  # post_loc
    register_location: Optional[str] = None
    
    # 互动数据
    likes: Optional[int] = None  # nlike
    forwards: Optional[int] = None  # nfwd
    replies: Optional[int] = None  # nrply
    author_followers: Optional[int] = None  # nfol
    author_fans: Optional[int] = None  # nfans
    
    # 内容标签
    tags: Optional[list[str]] = None
    keywords: Optional[list[str]] = None  # lkey
    weighted_keywords: Optional[list[dict]] = None  # vkey
    
    # 情感详细分值
    sentiment_detail: Optional[list[int]] = None  # common_senti [正面, 负面]
    sentiment_base: Optional[int] = None  # senti_base
    
    # 传播数据
    similar_count: Optional[int] = None  # nsimilar
    media_class: Optional[str] = None
    
    # 图片
    images: Optional[list[str]] = None  # lrt_pic / lpic
    
    # 转发信息
    repost_content: Optional[str] = None  # rt_cont
    repost_author: Optional[str] = None  # rt_author_name
    repost_url: Optional[str] = None  # rt_url
    
    class Config:
        frozen = True


class Author(BaseModel):
    """作者信息模型"""
    id: str
    name: str
    alias: Optional[str] = None
    url: Optional[str] = None
    followers: Optional[int] = None
    fans: Optional[int] = None
    location: Optional[str] = None
    
    class Config:
        frozen = True


class LocationStats(BaseModel):
    """地域统计"""
    location: str
    count: int
    percentage: float


class EngagementStats(BaseModel):
    """互动数据统计"""
    total_likes: int
    total_forwards: int
    total_replies: int
    avg_likes: float
    avg_forwards: float
    avg_replies: float
    max_likes: int
    max_forwards: int
    max_replies: int


class AnalysisFunction(BaseModel):
    """分析功能配置"""
    name: str
    description: str
    prompt_template: str


class AnalysisResult(BaseModel):
    """分析结果"""
    function: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class AnalyzedPost(Post):
    """带分析结果的帖子"""
    analysis: list[AnalysisResult] = Field(default_factory=list)


class ReportSection(BaseModel):
    """报告章节"""
    title: str
    content: str
    level: int = 1


class Report(BaseModel):
    """分析报告"""
    title: str
    project_name: str
    generated_at: datetime = Field(default_factory=datetime.now)
    sections: list[ReportSection] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    def to_markdown(self) -> str:
        """转换为 Markdown 格式"""
        lines = [
            f"# {self.title}",
            "",
            f"**项目名称:** {self.project_name}",
            f"**生成时间:** {self.generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "---",
            "",
        ]
        
        for section in self.sections:
            header = "#" * section.level
            lines.extend([
                f"{header} {section.title}",
                "",
                section.content,
                "",
            ])
        
        return "\n".join(lines)


class ProjectInfo(BaseModel):
    """专项信息"""
    id: str
    name: str
    keyword: str
    created_at: Optional[str] = None

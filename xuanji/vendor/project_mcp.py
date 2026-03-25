"""舆情监控专项管理客户端

提供两个客户端类：
- ProjectMCPClient: 异步底层客户端
- ProjectMCPClientSync: 同步接口包装器，自动从配置文件读取 cookie，返回类型化数据模型
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

import httpx

from xuanji.core.models import ProjectInfo, Post
from xuanji.core.errors import ProjectCreateError, DataFetchError, XuanjiError

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 默认配置
DEFAULT_BASE_URL = "https://yuqing.golaxy.cn/api/backend"
DEFAULT_COOKIE = ""
MAX_PROJECTS = 20

# 数据源配置
DEFAULT_SOURCES = [
    {"channel": 50, "channelName": "视频", "msgTypes": [1, 2, 3]},
    {"channel": 1, "channelName": "网站", "msgTypes": [1, 2, 3]},
    {"channel": 5, "channelName": "微博", "msgTypes": [1, 2, 3]},
    {"channel": 40, "channelName": "微信", "msgTypes": [1, 2, 3]},
    {"channel": 11, "channelName": "APP", "msgTypes": [1, 2, 3]},
    {"channel": 9, "channelName": "电子报", "msgTypes": [1, 2, 3]},
    {"channel": 2, "channelName": "论坛", "msgTypes": [1, 2, 3]},
    {"channel": 41, "channelName": "问答", "msgTypes": [1, 2, 3]},
    {"channel": 901, "channelName": "今日头条", "msgTypes": [1, 2, 3]},
    {"channel": 51, "channelName": "聚合平台", "msgTypes": [1, 2, 3]},
]


class ProjectMCPClient:
    """舆情监控专项管理客户端"""
    
    def __init__(self, base_url: str = DEFAULT_BASE_URL, cookie: str = DEFAULT_COOKIE):
        self.base_url = base_url
        # 自动添加 remember_user_token= 前缀（如果不存在）
        if cookie and not cookie.startswith("remember_user_token="):
            cookie = f"remember_user_token={cookie}"
        self.cookie = cookie
        self.headers = {"Cookie": cookie}
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """发送 HTTP 请求"""
        url = f"{self.base_url}{endpoint}"
        # 合并 headers
        request_headers = self.headers.copy()
        if "headers" in kwargs:
            request_headers.update(kwargs.pop("headers"))
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method, url, headers=request_headers, timeout=30.0, **kwargs
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise httpx.HTTPStatusError(
                    "认证失败 (401): Cookie 无效或已过期，请检查 ~/.xuanji/config.json 中的 cookie 配置",
                    request=e.request,
                    response=e.response
                )
            raise
    
    async def list_all_projects(self) -> dict:
        """获取所有专项列表"""
        return await self._request(
            "GET", "/topic/findAllUserTopicGroup?userId=0"
        )
    
    async def create_project(
        self, 
        keyword_include: str,
        name: Optional[str] = None,
        keyword_exclude: Optional[str] = None
    ) -> dict:
        """创建专项"""
        # 获取现有专项列表
        resp = await self.list_all_projects()
        if resp.get("status") != 200 or not resp.get("success"):
            return {"success": False, "error": "Failed to get project list"}
        
        projects = resp.get("data", {}).get("menu", [])
        existing_names = [p.get("name", "") for p in projects]
        
        # 检查数量限制
        if len(projects) >= MAX_PROJECTS:
            return {
                "success": False,
                "error": "Project limit reached",
                "message": f"专项数量已达上限({MAX_PROJECTS}个)"
            }
        
        # 确定专项名称
        if name:
            if name in existing_names:
                return {
                    "success": False,
                    "error": "Project name already exists",
                    "message": f"专项名称「{name}」已存在"
                }
            project_name = name
        else:
            counter = 1
            project_name = f"专项_{counter}"
            while project_name in existing_names:
                counter += 1
                project_name = f"专项_{counter}"
        
        # 构建请求体
        payload = {
            "areas": [],
            "domains": [],
            "excludeMedias": [],
            "fatherId": 0,
            "includeMedias": [],
            "keywordCommon": {"keywordAll": "", "keywordAny": [], "scopes": [1, 2]},
            "keywordExclude": {
                "keyword": keyword_exclude.strip() if keyword_exclude else "",
                "scopes": [],
                "translate": False
            },
            "keywordInclude": {
                "keyword": keyword_include.strip(),
                "scopes": [],
                "translate": False
            },
            "name": project_name,
            "sourceAreas": [],
            "sources": DEFAULT_SOURCES,
            "topicId": "",
            "msgTypes": [],
            "areaCodes": [],
            "domainCodes": [],
            "districtKeyword": "",
            "subjectKeyword": "",
            "eventKeyword": "",
            "keywordNot": "",
            "simpleMode": False
        }
        
        result = await self._request(
            "POST", "/topic/add",
            json=payload,
            headers={**self.headers, "Content-Type": "application/json"}
        )
        
        if result.get("status") == 200 and result.get("success"):
            return {
                "success": True,
                "message": "专项创建成功",
                "data": {
                    "id": result.get("data", {}).get("id", ""),
                    "name": project_name,
                    "keyword_include": keyword_include.strip(),
                    "keyword_exclude": keyword_exclude.strip() if keyword_exclude else ""
                }
            }
        else:
            return {
                "success": False,
                "error": result.get("message", "Unknown error"),
                "message": f"创建专项失败: {result.get('message', 'Unknown error')}"
            }
    
    async def delete_project(self, project_id: str) -> dict:
        """删除专项"""
        # 先检查专项是否存在
        resp = await self.list_all_projects()
        if resp.get("status") != 200 or not resp.get("success"):
            return {"success": False, "error": "Failed to get project list"}
        
        projects = resp.get("data", {}).get("menu", [])
        project_ids = [str(p.get("id")) for p in projects]
        
        if project_id not in project_ids:
            return {
                "success": False,
                "error": "Project not found",
                "message": f"专项ID「{project_id}」不存在"
            }
        
        # 获取专项名称
        project_name = ""
        for p in projects:
            if str(p.get("id")) == project_id:
                project_name = p.get("name", "")
                break
        
        result = await self._request("DELETE", f"/topic/{project_id}")
        
        if result.get("status") == 200 and result.get("success"):
            return {
                "success": True,
                "message": "专项删除成功",
                "data": {"id": project_id, "name": project_name}
            }
        else:
            return {
                "success": False,
                "error": result.get("message", "Unknown error"),
                "message": f"删除专项失败: {result.get('message', 'Unknown error')}"
            }
    
    async def get_project_data(
        self,
        project_id: str,
        project_name: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        page_num: int = 1,
        page_size: int = 20
    ) -> dict:
        """获取专项数据"""
        # 处理时间参数
        current_time = int(time.time() * 1000)
        
        if end_time:
            try:
                end_time_parsed = time.strptime(end_time.strip(), "%Y-%m-%d %H:%M:%S")
                end_timestamp = int(time.mktime(end_time_parsed)) * 1000
            except ValueError:
                return {
                    "success": False,
                    "error": "Invalid end_time format",
                    "message": "结束时间格式不正确，请使用 'YYYY-MM-DD HH:MM:SS' 格式"
                }
        else:
            end_timestamp = current_time
        
        if start_time:
            try:
                start_time_parsed = time.strptime(start_time.strip(), "%Y-%m-%d %H:%M:%S")
                start_timestamp = int(time.mktime(start_time_parsed)) * 1000
            except ValueError:
                return {
                    "success": False,
                    "error": "Invalid start_time format",
                    "message": "开始时间格式不正确，请使用 'YYYY-MM-DD HH:MM:SS' 格式"
                }
        else:
            start_timestamp = current_time - 24 * 60 * 60 * 1000  # 默认24小时前
        
        # 构建请求体
        payload = {
            "collapse": 0,
            "sorts": [{"name": "pt", "direction": "desc"}],
            "areas": [],
            "areaCodes": [],
            "beginTime": start_timestamp,
            "defaultNumber": 10000,
            "domains": [],
            "endTime": end_timestamp,
            "from": None,
            "keyword": {"keyword": "", "scopes": []},
            "negs": [],
            "noises": [],
            "pageNum": page_num,
            "pageSize": page_size,
            "requestTime": current_time,
            "sources": [
                {"channel": 50, "channelName": "视频", "msgTypes": [1, 2, 3], "secondClasses": []},
                {"channel": 1, "channelName": "网站", "msgTypes": [1, 2, 3], "secondClasses": []},
                {"channel": 5, "channelName": "微博", "msgTypes": [1, 2, 3], "secondClasses": []},
                {"channel": 40, "channelName": "微信", "msgTypes": [1, 2, 3], "secondClasses": []},
                {"channel": 11, "channelName": "APP", "msgTypes": [1, 2, 3], "secondClasses": []},
                {"channel": 9, "channelName": "电子报", "msgTypes": [1, 2, 3], "secondClasses": []},
                {"channel": 2, "channelName": "论坛", "msgTypes": [1, 2, 3], "secondClasses": []},
                {"channel": 41, "channelName": "问答", "msgTypes": [1, 2, 3], "secondClasses": []},
                {"channel": 901, "channelName": "今日头条", "msgTypes": [1, 2, 3], "secondClasses": []},
                {"channel": 51, "channelName": "聚合平台", "msgTypes": [1, 2, 3], "secondClasses": []},
            ],
            "to": None,
            "userId": None,
            "msgTypes": [],
            "areaScopes": [],
            "categories": [],
            "regTypes": [],
            "authorGenders": [],
            "nfans": [],
            "nfol": [],
            "ninteract": [],
            "nlike": [],
            "nrply": [],
            "nfwd": [],
            "duration": [],
            "readTypes": [],
            "merge": False,
            "mediaClasses": [],
            "langs": [],
            "registerLocations": [],
            "mediaName": [],
            "topicId": project_id,
            "topicName": project_name,
            "searchFlag": 0
        }
        
        result = await self._request(
            "POST", "/topic/list/doc",
            json=payload,
            headers={**self.headers, "Content-Type": "application/json"}
        )
        
        if result.get("status") == 200 and result.get("success"):
            data = result.get("data", {})
            docs_data = data.get("docs", {})
            hits_data = docs_data.get("hits", {})
            docs = hits_data.get("hits", [])
            total = hits_data.get("total", 0)
            
            # 格式化返回数据
            formatted_docs = []
            for doc in docs:
                source = doc.get("_source", doc) if isinstance(doc, dict) else {}
                content = source.get("cont", "")
                
                # 处理时间戳
                pt = source.get("pt")
                publish_time = ""
                if isinstance(pt, int):
                    from datetime import datetime
                    publish_time = datetime.fromtimestamp(pt / 1000).strftime("%Y-%m-%d %H:%M:%S")
                
                # 处理情感值
                senti = source.get("senti")
                sentiment_str = str(senti) if senti is not None else None
                
                # 处理互动数据
                nlike = source.get("nlike")
                nfwd = source.get("nfwd")
                nrply = source.get("nrply")
                nfol = source.get("nfol")
                nfans = source.get("nfans")
                
                # 处理关键词
                lkey = source.get("lkey", [])
                vkey = source.get("vkey", [])
                
                # 处理位置
                post_loc = source.get("post_loc", [])
                register_loc = source.get("register_loc")
                
                # 处理图片
                lrt_pic = source.get("lrt_pic", [])
                lpic = source.get("lpic", [])
                images = lrt_pic if lrt_pic else lpic
                
                formatted_docs.append({
                    "id": doc.get("_id", source.get("id")),
                    "title": source.get("title") if source.get("title") else None,
                    "content": content[:500] + "..." if len(content) > 500 else content,
                    "url": source.get("url"),
                    "source": source.get("mediaName"),
                    "channel": source.get("channelName"),
                    "publishTime": publish_time,
                    "sentiment": sentiment_str,
                    # 扩展字段
                    "author_name": source.get("author_name"),
                    "author_alias": source.get("author_alias"),
                    "author_id": source.get("author_id"),
                    "post_loc": post_loc,
                    "register_loc": register_loc,
                    "nlike": nlike,
                    "nfwd": nfwd,
                    "nrply": nrply,
                    "nfol": nfol,
                    "nfans": nfans,
                    "tags": source.get("tags", []),
                    "lkey": lkey,
                    "vkey": vkey,
                    "common_senti": source.get("common_senti"),
                    "senti_base": source.get("senti_base"),
                    "nsimilar": source.get("nsimilar"),
                    "media_class": source.get("media_class"),
                    "images": images,
                    "rt_cont": source.get("rt_cont"),
                    "rt_author_name": source.get("rt_author_name"),
                    "rt_url": source.get("rt_url"),
                })
            
            return {
                "success": True,
                "message": f"获取专项「{project_name}」数据成功",
                "data": {
                    "project_id": project_id,
                    "project_name": project_name,
                    "total": total,
                    "page_num": page_num,
                    "page_size": page_size,
                    "start_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_timestamp / 1000)),
                    "end_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(end_timestamp / 1000)),
                    "docs": formatted_docs
                }
            }
        else:
            return {
                "success": False,
                "error": result.get("message", "Unknown error"),
                "message": f"获取专项数据失败: {result.get('message', 'Unknown error')}"
            }


def _get_cookie_from_config() -> str:
    """从 ~/.xuanji/config.json 读取 cookie"""
    from xuanji.commands.config import get_config
    config = get_config()
    return config.get('cookie', '')


class ProjectMCPClientSync:
    """同步接口包装器 - 返回类型化数据模型
    
    自动从 ~/.xuanji/config.json 读取 cookie，提供同步方法和结构化错误处理。
    """

    def __init__(self):
        self._cookie = _get_cookie_from_config()
        self._client = ProjectMCPClient(
            base_url=DEFAULT_BASE_URL,
            cookie=self._cookie
        )

    def list_projects(self) -> list[dict]:
        """列出所有专项"""
        logging.getLogger('httpx').setLevel(logging.WARNING)

        async def fetch():
            resp = await self._client.list_all_projects()
            if resp.get("status") == 200:
                projects = resp.get("data", {}).get("menu", [])
                return [
                    {
                        "id": str(p.get("id")),
                        "name": p.get("name"),
                        "keyword": ""
                    }
                    for p in projects
                ]
            return []

        return asyncio.run(fetch())

    def get_project_by_name(self, name: str) -> Optional[ProjectInfo]:
        """根据名称查找专项"""
        projects = self.list_projects()
        for p in projects:
            if p.get("name") == name:
                return ProjectInfo(**p)
        return None

    def create_project(self, keyword: str, name: str) -> ProjectInfo:
        """创建专项

        错误处理：返回结构化错误信息，支持 LLM 自我修复
        """
        logging.getLogger('httpx').setLevel(logging.WARNING)

        async def _create():
            return await self._client.create_project(
                keyword_include=keyword,
                name=name
            )

        result = asyncio.run(_create())

        if not result.get("success"):
            raise ProjectCreateError(
                project_name=name,
                details=result.get("message", "Unknown error"),
                original_error=None,
                context={
                    "keyword": keyword,
                    "error": result.get("error"),
                    "vendor_response": result
                }
            )

        # 创建成功后等待后端同步，然后重试获取项目
        max_retries = 5
        retry_delay = 1.0
        last_error = None

        for attempt in range(max_retries):
            time.sleep(retry_delay)
            try:
                project = self.get_project_by_name(name)
                if project:
                    return project
            except Exception as e:
                last_error = str(e)
            retry_delay *= 1.5

        raise ProjectCreateError(
            project_name=name,
            details=f"创建成功但查询超时（{max_retries}次重试）",
            original_error=None,
            context={
                "keyword": keyword,
                "max_retries": max_retries,
                "last_error": last_error,
                "vendor_response": result,
                "suggestion_for_llm": "项目可能已创建成功，请使用 'xuanji project list' 验证"
            }
        )

    def get_or_create_project(self, keyword: str, name: str) -> ProjectInfo:
        """获取或创建专项"""
        existing = self.get_project_by_name(name)
        if existing:
            return existing
        return self.create_project(keyword, name)

    def get_data(self, project_id: str, project_name: str, limit: int = 100) -> list[Post]:
        """获取专项数据 - 返回 Post 模型列表"""
        logging.getLogger('httpx').setLevel(logging.WARNING)

        async def fetch():
            all_posts = []
            page_num = 1
            page_size = min(limit, 100)

            while len(all_posts) < limit:
                result = await self._client.get_project_data(
                    project_id=project_id,
                    project_name=project_name,
                    page_num=page_num,
                    page_size=page_size
                )

                if result.get("success"):
                    docs = result.get("data", {}).get("docs", [])
                    if not docs:
                        break

                    for i, doc in enumerate(docs):
                        if len(all_posts) >= limit:
                            break

                        source = doc.get("source") or doc.get("channel")
                        if not source:
                            url = doc.get("url", "")
                            if "weibo.com" in url or "weibo.cn" in url:
                                source = "微博"
                            elif "zhihu.com" in url:
                                source = "知乎"
                            elif "bilibili.com" in url:
                                source = "B站"
                            elif "douyin.com" in url or "tiktok.com" in url:
                                source = "抖音"
                            elif "xiaohongshu.com" in url:
                                source = "小红书"
                            elif "baidu.com" in url:
                                source = "百度"
                            else:
                                source = "其他"

                        time_val = doc.get("publishTime", "")
                        if isinstance(time_val, int):
                            time_val = datetime.fromtimestamp(time_val / 1000).strftime("%Y-%m-%d %H:%M:%S")

                        sentiment = doc.get("sentiment")
                        if sentiment is not None:
                            sentiment = str(sentiment)

                        def safe_int(val):
                            if val is None:
                                return None
                            try:
                                return int(val)
                            except (ValueError, TypeError):
                                return None

                        images = doc.get("images", [])
                        if not isinstance(images, list):
                            images = []

                        all_posts.append(Post(
                            id=str(doc.get("id", i)),
                            title=doc.get("title"),
                            content=doc.get("content", ""),
                            source=source,
                            time=time_val,
                            url=doc.get("url"),
                            author=doc.get("author_name"),
                            sentiment=sentiment,
                            author_id=str(doc.get("author_id")) if doc.get("author_id") else None,
                            author_alias=doc.get("author_alias"),
                            location=doc.get("post_loc"),
                            register_location=doc.get("register_loc"),
                            likes=safe_int(doc.get("nlike")),
                            forwards=safe_int(doc.get("nfwd")),
                            replies=safe_int(doc.get("nrply")),
                            author_followers=safe_int(doc.get("nfol")),
                            author_fans=safe_int(doc.get("nfans")),
                            tags=doc.get("tags") if doc.get("tags") else None,
                            keywords=doc.get("lkey") if doc.get("lkey") else None,
                            weighted_keywords=doc.get("vkey") if doc.get("vkey") else None,
                            sentiment_detail=doc.get("common_senti") if doc.get("common_senti") else None,
                            sentiment_base=safe_int(doc.get("senti_base")),
                            similar_count=safe_int(doc.get("nsimilar")),
                            media_class=doc.get("media_class"),
                            images=images if images else None,
                            repost_content=doc.get("rt_cont"),
                            repost_author=doc.get("rt_author_name"),
                            repost_url=doc.get("rt_url"),
                        ))

                    page_num += 1

                    if len(docs) < page_size:
                        break
                else:
                    error_msg = result.get("message", "Unknown error")
                    raise DataFetchError(
                        project_id=project_id,
                        reason=error_msg,
                        context={"project_name": project_name, "page_num": page_num}
                    )

            return all_posts

        return asyncio.run(fetch())

    def delete_project(self, project_id: str) -> bool:
        """删除专项"""
        logging.getLogger('httpx').setLevel(logging.WARNING)

        async def _delete():
            result = await self._client.delete_project(project_id)
            return result.get("success", False)

        return asyncio.run(_delete())


# 别名，保持向后兼容
ProjectMCPClient_Sync = ProjectMCPClientSync
ProjectMCPError = XuanjiError



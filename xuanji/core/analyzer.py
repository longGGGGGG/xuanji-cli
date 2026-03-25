"""AI analysis engine for public opinion data"""
import hashlib
import json
import random
import time
from pathlib import Path
from typing import Optional

from xuanji.core.models import Post, AnalysisResult, AnalysisFunction
from xuanji.core.llm import LLMClient, LLMError
from xuanji.commands.config import get_config


# 分层采样策略配置
SAMPLING_STRATEGIES = {
    "summary": {"method": "stratified", "limit": 100, "description": "分层采样，优先高互动和负面"},
    "opinion": {"method": "stratified", "limit": 100, "description": "分层采样，观点多样性"},
    "sentiment": {"method": "random", "limit": 50, "description": "随机采样，情感分布"},
    "kol": {"method": "by_fans", "limit": 50, "description": "按粉丝数排序，Top KOL"},
    "geography": {"method": "all", "limit": None, "description": "全量，地域统计"},
    "engagement": {"method": "by_engagement", "limit": 100, "description": "按互动量排序"},
    "topics": {"method": "stratified", "limit": 100, "description": "分层采样，主题覆盖"},
    "entities": {"method": "stratified", "limit": 100, "description": "分层采样，实体识别"},
}

# 全量直传阈值
FULL_BATCH_THRESHOLD = 100


class DataSampler:
    """数据采样器 - 分层递进采样"""
    
    @staticmethod
    def sample(posts: list[Post], method: str, limit: int) -> list[Post]:
        """
        根据策略采样数据
        
        Args:
            posts: 原始帖子列表
            method: 采样方法
            limit: 采样数量
        
        Returns:
            采样后的帖子列表
        """
        if not limit or len(posts) <= limit:
            return posts
        
        if method == "random":
            return DataSampler._random_sample(posts, limit)
        elif method == "by_fans":
            return DataSampler._by_fans_sample(posts, limit)
        elif method == "by_engagement":
            return DataSampler._by_engagement_sample(posts, limit)
        elif method == "stratified":
            return DataSampler._stratified_sample(posts, limit)
        elif method == "all":
            return posts
        else:
            # 默认随机采样
            return DataSampler._random_sample(posts, limit)
    
    @staticmethod
    def _random_sample(posts: list[Post], limit: int) -> list[Post]:
        """随机采样"""
        return random.sample(posts, min(limit, len(posts)))
    
    @staticmethod
    def _by_fans_sample(posts: list[Post], limit: int) -> list[Post]:
        """按粉丝数排序采样 - 用于KOL分析"""
        sorted_posts = sorted(
            posts, 
            key=lambda p: p.author_fans or 0, 
            reverse=True
        )
        return sorted_posts[:limit]
    
    @staticmethod
    def _by_engagement_sample(posts: list[Post], limit: int) -> list[Post]:
        """按互动量排序采样"""
        def engagement_score(p: Post) -> int:
            return (p.likes or 0) + (p.forwards or 0) * 2 + (p.replies or 0) * 3
        
        sorted_posts = sorted(posts, key=engagement_score, reverse=True)
        return sorted_posts[:limit]
    
    @staticmethod
    def _stratified_sample(posts: list[Post], limit: int) -> list[Post]:
        """
        分层采样 - 综合策略
        1. 高互动帖子（必采）
        2. 高粉丝作者帖子（必采）
        3. 负面情感帖子（必采，风险预警）
        4. 不同来源的代表性帖子
        5. 随机采样补足
        """
        sampled = []
        remaining = set(range(len(posts)))
        
        # 1. 高互动帖子（点赞>100）
        high_engagement = [
            i for i in remaining 
            if (posts[i].likes or 0) > 100
        ]
        sampled.extend(high_engagement[:limit // 5])
        remaining -= set(high_engagement[:limit // 5])
        
        # 2. 高粉丝作者（粉丝>10000）
        kol_indices = [
            i for i in remaining 
            if (posts[i].author_fans or 0) > 10000
        ]
        sampled.extend(kol_indices[:limit // 5])
        remaining -= set(kol_indices[:limit // 5])
        
        # 3. 负面情感帖子
        negative = [
            i for i in remaining 
            if posts[i].sentiment == "2" or (
                posts[i].sentiment_detail and 
                len(posts[i].sentiment_detail) >= 2 and
                posts[i].sentiment_detail[1] > posts[i].sentiment_detail[0]
            )
        ]
        sampled.extend(negative[:limit // 5])
        remaining -= set(negative[:limit // 5])
        
        # 4. 不同来源的代表性帖子
        sources = {}
        for i in remaining:
            source = posts[i].source
            if source not in sources:
                sources[source] = []
            sources[source].append(i)
        
        for source_indices in sources.values():
            if len(sampled) < limit * 4 // 5:
                sampled.append(source_indices[0])
                remaining.discard(source_indices[0])
        
        # 5. 随机采样补足
        remaining_slots = limit - len(sampled)
        if remaining_slots > 0 and remaining:
            random_sample = random.sample(
                list(remaining), 
                min(remaining_slots, len(remaining))
            )
            sampled.extend(random_sample)
        
        # 去重并保持原始顺序
        seen = set()
        result = []
        for i in sampled:
            if i not in seen and len(result) < limit:
                seen.add(i)
                result.append(posts[i])
        
        return result


class AnalysisCache:
    """分析结果缓存"""
    
    def __init__(self, cache_dir: Optional[str] = None):
        self.cache_dir = Path(cache_dir or "~/.xuanji/cache").expanduser()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = 3600  # 缓存1小时
    
    def _make_key(self, posts: list[Post], function_name: str) -> str:
        """生成缓存键"""
        # 基于帖子ID和时间戳生成哈希
        content = json.dumps({
            "post_ids": sorted([p.id for p in posts]),
            "function": function_name,
            "count": len(posts)
        }, sort_keys=True)
        return hashlib.md5(content.encode()).hexdigest()
    
    def get(self, posts: list[Post], function_name: str) -> Optional[AnalysisResult]:
        """获取缓存结果"""
        key = self._make_key(posts, function_name)
        cache_file = self.cache_dir / f"{key}.json"
        
        if not cache_file.exists():
            return None
        
        # 检查是否过期
        if time.time() - cache_file.stat().st_mtime > self.ttl:
            cache_file.unlink()
            return None
        
        try:
            data = json.loads(cache_file.read_text())
            return AnalysisResult(**data)
        except Exception:
            return None
    
    def set(self, posts: list[Post], function_name: str, result: AnalysisResult):
        """设置缓存"""
        key = self._make_key(posts, function_name)
        cache_file = self.cache_dir / f"{key}.json"
        
        try:
            cache_file.write_text(json.dumps(result.model_dump(), ensure_ascii=False))
        except Exception:
            pass  # 缓存失败不影响主流程


class MapReduceAnalyzer:
    """
    MapReduce 分析器 - 大规模数据分块处理
    
    架构：
    1. Map 阶段：数据分块 → 子任务并行分析（使用轻量级模型 qwen3.5-flash）
    2. Reduce 阶段：合并所有子结果 → 主模型生成最终报告
    
    优势：
    - 子任务用轻量模型（更快、更便宜）
    - 合并阶段用主模型（保证质量）
    - 支持 500+ 条数据的全量分析
    """
    
    # 子任务配置（从配置文件读取）
    DEFAULT_CHUNK_SIZE = 50  # 每块50条
    DEFAULT_MAX_WORKERS = 3  # 并行数
    
    def __init__(self, 
                 main_base_url: str, 
                 main_api_key: str, 
                 main_model: str = "qwen3.5-plus",
                 sub_base_url: Optional[str] = None,
                 sub_api_key: Optional[str] = None,
                 sub_model: Optional[str] = None,
                 chunk_size: int = DEFAULT_CHUNK_SIZE,
                 max_workers: int = DEFAULT_MAX_WORKERS):
        """
        初始化 MapReduce 分析器
        
        Args:
            main_base_url: 主模型 API URL
            main_api_key: 主模型 API Key
            main_model: 主模型名称（默认 qwen3.5-plus，质量优先）
            sub_base_url: 子任务模型 API URL（默认与主模型相同）
            sub_api_key: 子任务模型 API Key（默认与主模型相同）
            sub_model: 子任务模型名称（默认 qwen3.5-flash，速度优先）
            chunk_size: 每块数据量（默认50条）
            max_workers: 并行任务数（默认3）
        """
        # 从配置文件读取轻量模型配置
        config = get_config()
        llm_light = config.get('llm_light', {})
        
        # 轻量模型配置：优先使用参数 > 配置文件 > 主模型
        actual_sub_model = sub_model or llm_light.get('model_name') or main_model
        actual_sub_base_url = sub_base_url or llm_light.get('base_url') or main_base_url
        actual_sub_api_key = sub_api_key or llm_light.get('api_key') or main_api_key
        
        self.main_client = LLMClient(main_base_url, main_api_key, main_model)
        self.sub_client = LLMClient(
            actual_sub_base_url, 
            actual_sub_api_key, 
            actual_sub_model
        )
        self.sub_model = actual_sub_model
        self.chunk_size = chunk_size
        self.max_workers = max_workers
    
    def get_available_functions(self) -> list[str]:
        """获取支持的分析功能列表"""
        return ['summary', 'opinion', 'sentiment', 'kol', 'geography', 'engagement', 'topics', 'entities']
    
    def _chunk_posts(self, posts: list[Post]) -> list[list[Post]]:
        """将帖子列表分块"""
        return [
            posts[i:i + self.chunk_size] 
            for i in range(0, len(posts), self.chunk_size)
        ]
    
    def _create_sub_prompt(self, posts: list[Post], function_name: str, chunk_index: int) -> str:
        """创建子任务 prompt（简化版，适合轻量模型）"""
        # 简化格式：只保留关键信息
        lines = [f"【数据块 {chunk_index + 1}】"]
        for i, post in enumerate(posts, 1):
            lines.append(f"[{i}] {post.author or '匿名'}: {post.content[:200]}")
        
        posts_text = "\n".join(lines)
        
        # 简化的任务描述
        sub_prompts = {
            'summary': f"""请简要概括以下舆情数据的核心要点（3-5句话）：

{posts_text}

请输出：
1. 主要话题
2. 舆论倾向（正面/负面/中性）
3. 关键争议点（如有）""",
            
            'opinion': f"""请提取以下舆情数据中的主要观点：

{posts_text}

请输出：
1. 支持观点（简要）
2. 反对/质疑观点（简要）
3. 中立观点（简要）""",
            
            'sentiment': f"""请分析以下舆情数据的情感分布：

{posts_text}

请输出：正面X条，负面Y条，中性Z条""",
            
            'kol': f"""请识别以下舆情数据中的关键作者（KOL）：

{posts_text}

请输出：按粉丝数排序的前5名作者及其观点""",
            
            'geography': f"""请统计以下舆情数据的地域分布：

{posts_text}

请输出：各地区帖子数量排名""",
            
            'engagement': f"""请分析以下舆情数据的互动情况：

{posts_text}

请输出：高互动帖子的特征""",
            
            'topics': f"""请识别以下舆情数据的讨论主题：

{posts_text}

请输出：3-5个主要主题""",
            
            'entities': f"""请提取以下舆情数据中的关键实体：

{posts_text}

请输出：人名、品牌名、产品名（各最多5个）"""
        }
        
        return sub_prompts.get(function_name, f"请分析以下数据：\n\n{posts_text}")
    
    def _create_merge_prompt(self, sub_results: list[str], function_name: str, total_count: int) -> str:
        """创建合并任务 prompt（给主模型）"""
        combined = "\n\n---\n\n".join([f"【子分析 {i+1}】\n{r}" for i, r in enumerate(sub_results)])
        
        merge_prompts = {
            'summary': f"""你是资深舆情分析师。以下是多个数据块的子分析结果，请综合生成一份完整的舆情摘要报告。

总数据量：{total_count} 条

{combined}

请生成：
1. 一段连贯的摘要（200-300字），包含时间线和关键节点
2. 整体舆论倾向
3. 1-2个关键争议点

使用中文，段落连贯。""",
            
            'opinion': f"""你是观点分析专家。以下是多个数据块的子分析结果，请综合提炼出完整的观点分析报告。

总数据量：{total_count} 条

{combined}

请生成：
1. 主要观点或立场（3-5个）
2. 不同观点之间的核心分歧
3. 各观点的支持依据
4. 最具代表性的原话引用

使用中文，分点阐述。""",
            
            'sentiment': f"""你是情感分析专家。以下是多个数据块的子分析结果，请综合统计整体情感分布。

总数据量：{total_count} 条

{combined}

请生成：
1. 整体情感分布（正面: X%, 负面: Y%, 中性: Z%）
2. 情感表达最强烈的3个观点摘要
3. 主要情感触发因素

使用中文，结构化输出。""",
            
            'kol': f"""你是社交媒体分析专家。以下是多个数据块的子分析结果，请综合识别关键意见领袖（KOL）。

总数据量：{total_count} 条

{combined}

请生成：
1. 关键KOL（按影响力排序，最多5个）
2. 每个KOL的影响力评估
3. KOL的主要观点立场
4. KOL对舆情走向的潜在影响

使用中文，结构化输出。""",
            
            'geography': f"""你是地域分析专家。以下是多个数据块的子分析结果，请综合生成地域分布报告。

总数据量：{total_count} 条

{combined}

请生成：
1. 主要传播地区排名（前5）
2. 各地区的话题关注点差异
3. 地域情感倾向对比
4. 可能的舆情扩散路径

使用中文，结构化输出。""",
            
            'engagement': f"""你是互动数据分析专家。以下是多个数据块的子分析结果，请综合分析互动特征。

总数据量：{total_count} 条

{combined}

请生成：
1. 整体互动热度评估
2. 高互动内容特征分析
3. 互动情感倾向
4. 传播力强的内容类型

使用中文，结构化输出。""",
            
            'topics': f"""你是主题分析专家。以下是多个数据块的子分析结果，请综合识别热门话题。

总数据量：{total_count} 条

{combined}

请生成：
1. 主要讨论主题（3-5个）
2. 每个主题的关键词标签
3. 话题热度排序
4. 话题间的关联性

使用中文输出。""",
            
            'entities': f"""你是实体识别专家。以下是多个数据块的子分析结果，请综合提取关键实体。

总数据量：{total_count} 条

{combined}

请生成：
1. 人名（提及的人物）
2. 地名（涉及的地区）
3. 机构/组织名
4. 产品/品牌名
5. 每个实体的提及频次

使用中文，分类列出。"""
        }
        
        return merge_prompts.get(function_name, f"请综合以下子分析结果：\n\n{combined}")
    
    def analyze(self, posts: list[Post], function_name: str) -> AnalysisResult:
        """
        执行 MapReduce 分析
        
        Args:
            posts: 帖子列表（可超过100条）
            function_name: 分析功能名称
        
        Returns:
            分析结果
        """
        import concurrent.futures
        
        total_count = len(posts)
        chunks = self._chunk_posts(posts)
        
        # Map 阶段：并行处理子任务（使用轻量模型）
        sub_results = []
        
        print(f"  [MapReduce] 总数据 {total_count} 条 → 分 {len(chunks)} 块（每块 {self.chunk_size} 条）")
        print(f"  [MapReduce] 子任务模型: {self.sub_model}，并行数: {self.max_workers}")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有子任务
            future_to_index = {
                executor.submit(
                    self._analyze_chunk, 
                    chunk, 
                    function_name, 
                    i
                ): i 
                for i, chunk in enumerate(chunks)
            }
            
            # 收集结果
            for future in concurrent.futures.as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    result = future.result()
                    sub_results.append((index, result))
                    print(f"    ✓ 子任务 {index + 1}/{len(chunks)} 完成")
                except Exception as e:
                    print(f"    ✗ 子任务 {index + 1}/{len(chunks)} 失败: {e}")
                    sub_results.append((index, f"[分析失败: {e}]"))
        
        # 按原始顺序排序
        sub_results.sort(key=lambda x: x[0])
        sub_results_text = [r[1] for r in sub_results]
        
        # Reduce 阶段：合并结果（使用主模型）
        print(f"  [MapReduce] 合并 {len(sub_results)} 个子结果...")
        merge_prompt = self._create_merge_prompt(sub_results_text, function_name, total_count)
        
        try:
            final_content = self.main_client.complete(merge_prompt, max_tokens=2500)
            
            return AnalysisResult(
                function=function_name,
                content=final_content.strip(),
                metadata={
                    'post_count': total_count,
                    'chunks': len(chunks),
                    'chunk_size': self.chunk_size,
                    'sub_model': self.sub_model,
                    'main_model': self.main_client.model_name,
                    'method': 'mapreduce'
                }
            )
        except LLMError as e:
            # 如果合并失败，返回子结果拼接（降级方案）
            fallback_content = "\n\n---\n\n".join(sub_results_text)
            return AnalysisResult(
                function=function_name,
                content=f"[合并阶段失败，以下为子结果拼接]\n\n{fallback_content}",
                metadata={
                    'post_count': total_count,
                    'chunks': len(chunks),
                    'error': str(e),
                    'method': 'mapreduce_fallback'
                }
            )
    
    def _analyze_chunk(self, posts: list[Post], function_name: str, chunk_index: int) -> str:
        """分析单个数据块（子任务）"""
        prompt = self._create_sub_prompt(posts, function_name, chunk_index)
        
        # 使用轻量模型（更快、更便宜）
        result = self.sub_client.complete(prompt, max_tokens=1000, temperature=0.5)
        return result.strip()


class AIAnalyzer:
    """AI 分析引擎 - 分层递进架构"""
    
    BUILTIN_FUNCTIONS = {
        'summary': AnalysisFunction(
            name='summary',
            description='生成整体摘要，概括舆情主要内容和趋势',
            prompt_template="""你是一个专业的舆情分析师。请对以下舆情数据进行摘要分析，输出一段连贯的摘要文字：

{posts_text}

要求：
1. 用一段话概括主要话题和核心事件（200-300字）
2. 如果涉及具体事件，请按时间顺序梳理关键节点（时间线）
3. 说明整体舆论倾向（正面/负面/中性）
4. 提及1-2个关键争议点或热点
5. 使用中文输出，段落连贯，不要分点罗列

格式示例：
近期，XX事件引发广泛关注。该事件始于X月X日...（时间线梳理）。舆论整体呈现XX态度，主要关注点集中在...和...两个方面。其中，XX问题成为争议焦点。

请直接输出摘要段落。"""
        ),
        'sentiment': AnalysisFunction(
            name='sentiment',
            description='情感分析，统计正面/负面/中性情绪分布',
            prompt_template="""你是一个情感分析专家。请分析以下舆情数据的情感倾向：

{posts_text}

请输出：
1. 整体情感分布（正面: X%, 负面: Y%, 中性: Z%）
2. 情感表达最强烈的3个观点摘要
3. 主要情感触发因素

使用中文，结构化输出。"""
        ),
        'opinion': AnalysisFunction(
            name='opinion',
            description='观点提取，识别主要立场和意见分歧',
            prompt_template="""你是一个观点分析专家。请从以下舆情数据中提取主要观点：

{posts_text}

请输出：
1. 主要观点或立场（3-5个）
2. 不同观点之间的核心分歧
3. 各观点的支持依据/论据
4. 最具代表性的原话引用

使用中文，分点阐述。"""
        ),
        'topics': AnalysisFunction(
            name='topics',
            description='主题聚类，识别讨论热点和话题分布',
            prompt_template="""你是一个主题分析专家。请分析以下舆情数据的热门话题：

{posts_text}

请输出：
1. 主要讨论主题（3-5个）
2. 每个主题的关键词标签
3. 话题热度排序
4. 话题间的关联性

使用中文输出。"""
        ),
        'entities': AnalysisFunction(
            name='entities',
            description='实体识别，提取人名、地名、机构名等关键实体',
            prompt_template="""你是一个实体识别专家。请从以下舆情数据中提取关键实体：

{posts_text}

请识别并输出：
1. 人名（提及的人物）
2. 地名（涉及的地区）
3. 机构/组织名
4. 产品/品牌名
5. 每个实体的提及频次（估计）

使用中文，分类列出。"""
        ),
        'kol': AnalysisFunction(
            name='kol',
            description='KOL分析，识别关键意见领袖及其影响力',
            prompt_template="""你是一个社交媒体分析专家。请分析以下舆情数据中的关键意见领袖（KOL）：

{posts_text}

数据包含作者粉丝数、互动量（点赞/转发/评论）等信息。

请输出：
1. 识别出的关键KOL（按影响力排序，最多5个）
2. 每个KOL的影响力评估（粉丝数、互动量、内容传播力）
3. KOL的主要观点立场
4. KOL对舆情走向的潜在影响

使用中文，结构化输出。"""
        ),
        'geography': AnalysisFunction(
            name='geography',
            description='地域分析，识别舆情传播的地域分布特征',
            prompt_template="""你是一个地域分析专家。请分析以下舆情数据的地域分布：

{posts_text}

数据包含发帖地点、注册地点等地理信息。

请输出：
1. 主要传播地区排名（前5）
2. 各地区的话题关注点差异
3. 地域情感倾向对比
4. 可能的舆情扩散路径

使用中文，结构化输出。"""
        ),
        'engagement': AnalysisFunction(
            name='engagement',
            description='互动分析，分析点赞、转发、评论等互动数据',
            prompt_template="""你是一个互动数据分析专家。请分析以下舆情数据的互动特征：

{posts_text}

数据包含点赞数、转发数、评论数等互动指标。

请输出：
1. 整体互动热度评估
2. 高互动内容特征分析
3. 互动情感倾向（正面互动 vs 负面互动）
4. 传播力强的内容类型

使用中文，结构化输出。"""
        ),
    }
    
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None, 
                 model_name: Optional[str] = None):
        """
        初始化 AI 分析器
        
        Args:
            base_url: LLM API 基础 URL
            api_key: LLM API 密钥
            model_name: 模型名称
        """
        self._llm_client: Optional[LLMClient] = None
        self.sampler = DataSampler()
        self.cache = AnalysisCache()
        
        # 如果未提供参数，尝试从配置读取
        config = get_config()
        self.base_url = base_url or config.get('llm', {}).get('base_url')
        self.api_key = api_key or config.get('llm', {}).get('api_key')
        self.model_name = model_name or config.get('llm', {}).get('model_name')
    
    def _get_llm_client(self) -> LLMClient:
        """延迟初始化 LLM 客户端"""
        if self._llm_client is None:
            if not all([self.base_url, self.api_key, self.model_name]):
                raise LLMError(
                    "LLM 未配置。请先运行以下命令配置：\n"
                    "  xuanji config set llm.base_url \"https://api.example.com/v1/\"\n"
                    "  xuanji config set llm.api_key \"your-api-key\"\n"
                    "  xuanji config set llm.model_name \"gpt-4\""
                )
            self._llm_client = LLMClient(self.base_url, self.api_key, self.model_name)
        return self._llm_client
    
    def get_available_functions(self) -> dict[str, AnalysisFunction]:
        """获取所有可用的分析功能"""
        return self.BUILTIN_FUNCTIONS.copy()
    
    def _format_posts(self, posts: list[Post]) -> str:
        """格式化帖子为文本 - 增强版，包含更多字段"""
        lines = []
        for i, post in enumerate(posts, 1):
            lines.append(f"[{i}] 来源: {post.source}")
            if post.title:
                lines.append(f"标题: {post.title}")
            
            # 作者信息
            if post.author:
                author_info = f"作者: {post.author}"
                if post.author_alias and post.author_alias != post.author:
                    author_info += f"({post.author_alias})"
                if post.author_fans:
                    author_info += f" [粉丝: {post.author_fans}]"
                if post.author_followers:
                    author_info += f" [关注: {post.author_followers}]"
                lines.append(author_info)
            
            # 地域信息
            if post.location:
                lines.append(f"地点: {' / '.join(post.location)}")
            if post.register_location:
                lines.append(f"注册地: {post.register_location}")
            
            # 互动数据
            engagement = []
            if post.likes is not None:
                engagement.append(f"点赞: {post.likes}")
            if post.forwards is not None:
                engagement.append(f"转发: {post.forwards}")
            if post.replies is not None:
                engagement.append(f"评论: {post.replies}")
            if engagement:
                lines.append(f"互动: {', '.join(engagement)}")
            
            # 情感标签
            if post.sentiment:
                lines.append(f"情感: {post.sentiment}")
            if post.sentiment_detail:
                lines.append(f"情感分值: 正面={post.sentiment_detail[0]}, 负面={post.sentiment_detail[1]}")
            
            # 关键词
            if post.keywords:
                lines.append(f"关键词: {', '.join(post.keywords[:10])}")  # 最多10个
            
            # 内容
            lines.append(f"内容: {post.content}")
            
            # 转发信息
            if post.repost_content:
                lines.append(f"转发内容: {post.repost_content}")
            if post.repost_author:
                lines.append(f"转发自: {post.repost_author}")
            
            lines.append("")
        return "\n".join(lines)
    
    def analyze(self, posts: list[Post], function_name: str, use_sampling: bool = True) -> AnalysisResult:
        """
        执行单一分析功能 - 分层递进架构
        
        Args:
            posts: 帖子列表
            function_name: 分析功能名称
            use_sampling: 是否使用采样策略（默认True）
        
        Returns:
            分析结果
        """
        if function_name not in self.BUILTIN_FUNCTIONS:
            raise ValueError(f"未知的分析功能: {function_name}")
        
        # 1. 检查缓存
        cached_result = self.cache.get(posts, function_name)
        if cached_result:
            return cached_result
        
        # 2. 智能采样决策
        strategy = SAMPLING_STRATEGIES.get(function_name, {"method": "stratified", "limit": 100})
        original_count = len(posts)
        
        if use_sampling and original_count > FULL_BATCH_THRESHOLD:
            # 需要根据策略采样
            sampled_posts = self.sampler.sample(
                posts, 
                strategy["method"], 
                strategy["limit"]
            )
            sampling_info = {
                "original_count": original_count,
                "sampled_count": len(sampled_posts),
                "sampling_method": strategy["method"],
                "sampling_strategy": strategy.get("description", ""),
                "full_batch_threshold": FULL_BATCH_THRESHOLD
            }
        else:
            # 数据量小或禁用采样，使用全量
            sampled_posts = posts
            sampling_info = {
                "original_count": original_count,
                "sampled_count": original_count,
                "sampling_method": "full_batch" if original_count <= FULL_BATCH_THRESHOLD else "disabled",
                "full_batch_threshold": FULL_BATCH_THRESHOLD
            }
        
        # 3. 执行分析
        function = self.BUILTIN_FUNCTIONS[function_name]
        posts_text = self._format_posts(sampled_posts)
        prompt = function.prompt_template.format(posts_text=posts_text)
        
        try:
            llm_client = self._get_llm_client()
            content = llm_client.complete(prompt, max_tokens=2000)
            result = AnalysisResult(
                function=function_name,
                content=content.strip(),
                metadata={
                    'post_count': len(sampled_posts),
                    'original_count': original_count,
                    'sampling': sampling_info,
                    'model': self.model_name,
                    'source': 'llm'
                }
            )
            # 缓存结果
            self.cache.set(posts, function_name, result)
            return result
        except LLMError as e:
            # 重新抛出错误，让上层处理
            raise LLMError(f"LLM 调用失败: {e}") from e
    
    def analyze_multi(self, posts: list[Post], functions: list[str], delay: float = 1.0, verbose: bool = True) -> list[AnalysisResult]:
        """
        执行多个分析功能，带间隔延迟和采样信息展示
        
        Args:
            posts: 帖子列表
            functions: 分析功能名称列表
            delay: 分析之间的延迟秒数（默认1秒）
            verbose: 是否打印采样信息
        """
        import time
        
        results = []
        for i, func_name in enumerate(functions):
            try:
                # 非第一次调用时添加延迟
                if i > 0 and delay > 0:
                    time.sleep(delay)
                
                # 获取采样策略信息
                strategy = SAMPLING_STRATEGIES.get(func_name, {"method": "stratified", "limit": 100})
                original_count = len(posts)
                
                if verbose and original_count > FULL_BATCH_THRESHOLD:
                    print(f"  [{func_name}] 数据量: {original_count} → 采样 {strategy['limit']} 条 ({strategy['description']})")
                
                result = self.analyze(posts, func_name)
                
                # 打印采样结果信息
                if verbose and result.metadata.get('sampling'):
                    sampling = result.metadata['sampling']
                    if sampling.get('original_count', 0) > sampling.get('sampled_count', 0):
                        print(f"    ✓ 实际分析: {sampling['sampled_count']}/{sampling['original_count']} 条 (方法: {sampling['sampling_method']})")
                
                results.append(result)
            except Exception as e:
                results.append(AnalysisResult(
                    function=func_name,
                    content=f"[分析失败: {e}]",
                    metadata={'error': str(e)}
                ))
        return results

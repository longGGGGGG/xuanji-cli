"""LLM client for AI analysis - 需要显式配置"""
import json
import time
import urllib.request
import urllib.error


class LLMError(Exception):
    """LLM 调用错误"""
    pass


class LLMClient:
    """大语言模型客户端 - 需要配置 base_url, api_key, model_name"""
    
    def __init__(self, base_url: str, api_key: str, model_name: str):
        """
        初始化 LLM 客户端
        
        Args:
            base_url: API 基础 URL，例如 https://api.openai.com/v1/
            api_key: API 密钥
            model_name: 模型名称，例如 gpt-4, claude-3-opus, k2p5
        """
        self.base_url = base_url.rstrip('/') + '/'  # 确保以 / 结尾
        self.api_key = api_key
        self.model_name = model_name
        
        if not self.api_key:
            raise LLMError("api_key 不能为空")
        if not self.base_url:
            raise LLMError("base_url 不能为空")
        if not self.model_name:
            raise LLMError("model_name 不能为空")
    
    def complete(self, prompt: str, max_tokens: int = 2000, temperature: float = 0.7, 
                 retries: int = 3, delay: float = 2.0) -> str:
        """调用 LLM 完成提示，带重试机制
        
        Args:
            prompt: 提示文本
            max_tokens: 最大生成 token 数
            temperature: 温度参数
            retries: 失败重试次数（默认3次）
            delay: 重试间隔秒数（默认2秒）
        """
        url = f"{self.base_url}chat/completions"
        
        data = {
            "model": self.model_name,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        last_error = None
        for attempt in range(retries):
            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(data).encode('utf-8'),
                    headers=headers,
                    method='POST'
                )
                
                with urllib.request.urlopen(req, timeout=120) as response:
                    result = json.loads(response.read().decode('utf-8'))
                    return result['choices'][0]['message']['content']
                    
            except urllib.error.HTTPError as e:
                error_body = e.read().decode('utf-8')
                last_error = LLMError(f"API error {e.code}: {error_body}")
                # 4xx 错误不重试
                if 400 <= e.code < 500:
                    raise last_error
            except Exception as e:
                last_error = LLMError(f"Request failed: {e}")
                # 最后一次尝试，直接抛出
                if attempt == retries - 1:
                    raise last_error
            
            # 等待后重试
            if attempt < retries - 1:
                time.sleep(delay * (attempt + 1))  # 指数退避
        
        raise last_error

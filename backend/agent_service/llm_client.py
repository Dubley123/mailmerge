"""
LLM Client - 统一的LLM交互接口
提供标准化的LLM调用方法，支持Tool Calling
"""
from typing import Dict, Any, List, Optional
import json

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from .config import Config


class LLMClient:
    """LLM客户端 - 统一的LLM交互接口
    
    提供标准化的方法供各个ACTION子目录调用
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.client = None
        
        if OPENAI_AVAILABLE and self.config.API_KEY:
            self.client = OpenAI(
                api_key=self.config.API_KEY,
                base_url=self.config.BASE_URL,
                timeout=self.config.TIMEOUT
            )
    
    def chat(
        self,
        system_prompt: str,
        user_message: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.1
    ) -> Dict[str, Any]:
        """基础对话接口
        
        Args:
            system_prompt: 系统提示词
            user_message: 用户消息
            tools: 工具定义列表（Tool Calling）
            temperature: 温度参数
            
        Returns:
            {
                "type": "text" | "tool_call",
                "content": str,  # type=text时的回复内容
                "tool_calls": [...],  # type=tool_call时的工具调用
                "raw_response": {...}  # 原始响应
            }
        """
        if not self.client:
            raise RuntimeError("LLM客户端未初始化，请检查API_KEY配置")
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        try:
            kwargs = {
                "model": self.config.MODEL_NAME,
                "messages": messages,
                "temperature": temperature
            }
            
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            
            response = self.client.chat.completions.create(**kwargs)
            message = response.choices[0].message
            
            # 解析响应
            if message.tool_calls:
                # Tool Calling响应
                return {
                    "type": "tool_call",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "name": tc.function.name,
                            "arguments": json.loads(tc.function.arguments)
                        }
                        for tc in message.tool_calls
                    ],
                    "raw_response": response
                }
            else:
                # 普通文本响应
                return {
                    "type": "text",
                    "content": message.content,
                    "tool_calls": None,
                    "raw_response": response
                }
                
        except Exception as e:
            raise RuntimeError(f"LLM调用失败: {str(e)}")
    
    def chat_with_history(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.1
    ) -> Dict[str, Any]:
        """带历史记录的对话接口
        
        Args:
            messages: 消息历史列表 [{"role": "user/assistant/system", "content": "..."}]
            tools: 工具定义列表
            temperature: 温度参数
            
        Returns:
            与chat()方法相同的返回格式
        """
        if not self.client:
            raise RuntimeError("LLM客户端未初始化，请检查API_KEY配置")
        
        try:
            kwargs = {
                "model": self.config.MODEL_NAME,
                "messages": messages,
                "temperature": temperature
            }
            
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"
            
            response = self.client.chat.completions.create(**kwargs)
            message = response.choices[0].message
            
            if message.tool_calls:
                return {
                    "type": "tool_call",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "name": tc.function.name,
                            "arguments": json.loads(tc.function.arguments)
                        }
                        for tc in message.tool_calls
                    ],
                    "raw_response": response
                }
            else:
                return {
                    "type": "text",
                    "content": message.content,
                    "tool_calls": None,
                    "raw_response": response
                }
                
        except Exception as e:
            raise RuntimeError(f"LLM调用失败: {str(e)}")

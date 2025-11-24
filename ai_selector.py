#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
AI选股引擎
使用LLM生成选股策略并执行
"""
import re
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, date
import logging
from openai import OpenAI

from models import Strategy, SelectionResult, StrategyCreateRequest
from tdx_reader import get_tdx_reader
from database import get_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AISelector:
    """AI选股引擎"""
    
    def __init__(self, api_key: str, api_base: str = "https://api.deepseek.com/v1", model: str = "deepseek-chat"):
        """
        初始化AI选股引擎
        
        Args:
            api_key: API密钥
            api_base: API基础URL
            model: 模型名称
        """
        self.client = OpenAI(api_key=api_key, base_url=api_base)
        self.model = model
        self.tdx_reader = get_tdx_reader()
        self.db = get_db()
    
    def generate_strategy_code(self, user_input: str) -> str:
        """
        根据用户输入生成选股策略代码
        
        Args:
            user_input: 用户输入的选股条件描述
            
        Returns:
            生成的Python代码
        """
        system_prompt = """你是一个专业的量化选股助手。用户会描述选股条件,你需要生成Python函数来实现选股逻辑。

**可用的数据字段:**
- stock_data: List[StockDayData] - 股票的日线数据列表,按日期升序排列
- 每个StockDayData包含: date, open, high, low, close, amount, volume, prev_close

**生成要求:**
1. 必须生成一个名为 `select_stock(code, stock_data)` 的函数
2. 函数接收参数: code (股票代码), stock_data (日线数据列表)
3. 函数返回 True/False 表示是否选中该股票
4. 可以返回一个字典包含 selected 和 metrics 字段,如: {'selected': True, 'metrics': {'pe': 15.5}}
5. 只使用Python标准库,可以使用 statistics 模块进行统计计算
6. 代码必须安全,不能有文件操作、网络请求等危险操作
7. 只返回函数代码,不要有其他解释

**示例:**
用户输入: "选出最近5天平均成交量大于1000万手的股票"
你应该生成:
```python
def select_stock(code, stock_data):
    if len(stock_data) < 5:
        return False
    
    recent_5 = stock_data[-5:]
    avg_volume = sum(d.volume for d in recent_5) / 5
    
    if avg_volume > 10000000:
        return {
            'selected': True,
            'metrics': {
                'avg_volume': avg_volume,
                'latest_close': stock_data[-1].close
            }
        }
    return False
```"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            generated_code = response.choices[0].message.content
            
            # 提取代码块
            code_match = re.search(r'```python\n(.*?)\n```', generated_code, re.DOTALL)
            if code_match:
                generated_code = code_match.group(1)
            
            logger.info(f"生成策略代码成功")
            return generated_code.strip()
            
        except Exception as e:
            logger.error(f"生成策略代码失败: {e}")
            raise
    
    def validate_code(self, code: str) -> bool:
        """
        验证代码安全性
        
        Args:
            code: Python代码
            
        Returns:
            是否安全
        """
        # 危险关键字检测
        dangerous_keywords = [
            'import os', 'import sys', 'import subprocess',
            'open(', 'exec(', 'eval(', '__import__',
            'compile(', 'globals(', 'locals(',
            'file', 'socket', 'urllib', 'requests'
        ]
        
        code_lower = code.lower()
        for keyword in dangerous_keywords:
            if keyword.lower() in code_lower:
                logger.warning(f"检测到危险关键字: {keyword}")
                return False
        
        # 检查必须包含 select_stock 函数
        if 'def select_stock' not in code:
            logger.warning("代码缺少 select_stock 函数")
            return False
        
        return True
    
    def execute_strategy(self, strategy: Strategy, max_stocks: int = 100) -> List[SelectionResult]:
        """
        执行选股策略
        
        Args:
            strategy: 策略对象
            max_stocks: 最多返回股票数
            
        Returns:
            选股结果列表
        """
        # 验证代码安全性
        if not self.validate_code(strategy.generated_code):
            raise ValueError("策略代码未通过安全检查")
        
        results = []
        start_time = time.time()
        
        # 获取所有股票列表
        all_stocks = self.tdx_reader.list_all_stocks()
        logger.info(f"开始执行策略,共 {len(all_stocks)} 只股票")
        
        # 执行选股
        namespace = {}
        try:
            exec(strategy.generated_code, namespace)
        except Exception as e:
            logger.error(f"策略代码执行失败: {e}")
            raise ValueError(f"策略代码执行失败: {e}")
        
        select_stock = namespace.get('select_stock')
        if not callable(select_stock):
            raise ValueError("未找到可调用的 select_stock 函数")
        
        selected_count = 0
        for stock_info in all_stocks:
            if selected_count >= max_stocks:
                break
            
            try:
                # 读取股票数据
                stock_data = self.tdx_reader.read_day_data(stock_info.code)
                if not stock_data:
                    continue
                
                # 执行选股函数
                result = select_stock(stock_info.code, stock_data)
                
                # 处理返回结果
                selected = False
                metrics = None
                
                if isinstance(result, bool):
                    selected = result
                elif isinstance(result, dict):
                    selected = result.get('selected', False)
                    metrics = result.get('metrics')
                
                if selected:
                    selection_result = SelectionResult(
                        strategy_id=strategy.id,
                        code=stock_info.code,
                        name=stock_info.name,
                        metrics=metrics
                    )
                    results.append(selection_result)
                    selected_count += 1
                    logger.info(f"选中: {stock_info.code}")
            
            except Exception as e:
                logger.warning(f"处理股票 {stock_info.code} 时出错: {e}")
                continue
        
        execution_time = time.time() - start_time
        logger.info(f"选股完成,耗时 {execution_time:.2f}秒,选中 {len(results)} 只股票")
        
        return results
    
    def create_and_execute_strategy(
        self, 
        request: StrategyCreateRequest,
        auto_save: bool = True,
        max_stocks: int = 100
    ) -> Dict[str, Any]:
        """
        创建并执行策略(一站式服务)
        
        Args:
            request: 策略创建请求
            auto_save: 是否自动保存策略和结果
            max_stocks: 最多返回股票数
            
        Returns:
            包含策略和结果的字典
        """
        start_time = time.time()
        
        # 生成策略代码
        logger.info(f"生成策略: {request.user_input}")
        generated_code = self.generate_strategy_code(request.user_input)
        
        # 创建策略对象
        strategy = Strategy(
            name=request.name,
            description=request.description,
            user_input=request.user_input,
            generated_code=generated_code
        )
        
        # 保存策略
        if auto_save:
            strategy.id = self.db.save_strategy(strategy)
        
        # 执行策略
        results = self.execute_strategy(strategy, max_stocks)
        
        # 保存结果
        if auto_save and results:
            self.db.save_selection_results(results)
        
        execution_time = time.time() - start_time
        
        return {
            'strategy': strategy,
            'results': results,
            'total_count': len(results),
            'execution_time': execution_time
        }


# 全局AI选股器实例
ai_selector: Optional[AISelector] = None


def get_ai_selector() -> AISelector:
    """获取AI选股器实例"""
    global ai_selector
    if ai_selector is None:
        raise RuntimeError("AI选股器未初始化")
    return ai_selector


def init_ai_selector(api_key: str, api_base: str = "https://api.deepseek.com/v1", model: str = "deepseek-chat"):
    """初始化AI选股器"""
    global ai_selector
    ai_selector = AISelector(api_key, api_base, model)
    logger.info("AI选股器已初始化")

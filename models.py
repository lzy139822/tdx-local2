#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
数据模型定义
使用Pydantic进行数据验证
"""
from __future__ import annotations
from typing import List, Optional, Dict, Any
from datetime import datetime
import datetime as dt
from pydantic import BaseModel, Field


class StockDayData(BaseModel):
    """日线数据模型"""
    code: str = Field(..., description="股票代码")
    date: dt.date = Field(..., description="交易日期")
    open: float = Field(..., description="开盘价")
    high: float = Field(..., description="最高价")
    low: float = Field(..., description="最低价")
    close: float = Field(..., description="收盘价")
    amount: float = Field(..., description="成交额(元)")
    volume: int = Field(..., description="成交量(手)")
    prev_close: Optional[float] = Field(None, description="上日收盘价")


class StockInfo(BaseModel):
    """股票基本信息"""
    code: str = Field(..., description="股票代码")
    name: Optional[str] = Field(None, description="股票名称")
    market: str = Field(..., description="市场(sh/sz)")
    latest_date: Optional[dt.date] = Field(None, description="最新数据日期")
    data_count: Optional[int] = Field(None, description="数据记录数")


class StockQueryRequest(BaseModel):
    """股票查询请求"""
    codes: List[str] = Field(..., description="股票代码列表")
    start_date: Optional[dt.date] = Field(None, description="开始日期")
    end_date: Optional[dt.date] = Field(None, description="结束日期")
    fields: Optional[List[str]] = Field(None, description="返回字段")


class Strategy(BaseModel):
    """选股策略模型"""
    id: Optional[int] = None
    name: str = Field(..., description="策略名称")
    description: Optional[str] = Field(None, description="策略描述")
    user_input: str = Field(..., description="用户输入的选股条件")
    generated_code: str = Field(..., description="生成的Python代码")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class StrategyCreateRequest(BaseModel):
    """创建策略请求"""
    name: str = Field(..., description="策略名称")
    description: Optional[str] = Field(None, description="策略描述")
    user_input: str = Field(..., description="用户输入的选股条件")


class SelectionResult(BaseModel):
    """选股结果模型"""
    id: Optional[int] = None
    strategy_id: int = Field(..., description="策略ID")
    code: str = Field(..., description="股票代码")
    name: Optional[str] = Field(None, description="股票名称")
    selected_at: datetime = Field(default_factory=datetime.now, description="选中时间")
    metrics: Optional[Dict[str, Any]] = Field(None, description="相关指标")


class SelectionResponse(BaseModel):
    """选股结果响应"""
    strategy: Strategy
    results: List[SelectionResult]
    total_count: int
    execution_time: float = Field(..., description="执行耗时(秒)")

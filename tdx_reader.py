#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
通达信本地数据读取模块  
支持读取日线数据(.day文件)
"""
import os
import struct
from typing import List, Optional, Dict
from datetime import datetime, date
from pathlib import Path
import logging
from functools import lru_cache

from models import StockDayData, StockInfo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TDXReader:
    """通达信数据读取器"""
    
    def __init__(self, tdx_path: str):
        """
        初始化TDX数据读取器
        
        Args:
            tdx_path: 通达信安装路径
        """
        self.tdx_path = Path(tdx_path)
        self.sh_lday_path = self.tdx_path / "vipdoc" / "sh" / "lday"
        self.sz_lday_path = self.tdx_path / "vipdoc" / "sz" / "lday"
        
        # 验证路径
        if not self.sh_lday_path.exists():
            logger.warning(f"上海日线数据路径不存在: {self.sh_lday_path}")
        if not self.sz_lday_path.exists():
            logger.warning(f"深圳日线数据路径不存在: {self.sz_lday_path}")
    
    @staticmethod
    def _is_a_share_stock(full_code: str) -> bool:
        """
        判断是否为A股股票(排除ETF、债券、指数等)
        
        Args:
            full_code: 包含市场前缀的完整代码,如 sh600000, sz000001
        
        A股代码规则:
        - 上海A股: sh60xxxx (主板), sh68xxxx (科创板)
        - 深圳A股: sz00xxxx (主板), sz30xxxx (创业板)
        
        排除:
        - 指数: sh000xxx, sz399xxx
        - ETF: sh51xxxx, sz15xxxx
        - 债券: sh11xxxx, sh12xxxx, sz12xxxx
        """
        code_lower = full_code.lower()
        
        # 上海A股: sh60开头或sh68开头
        if code_lower.startswith(('sh60', 'sh68')):
            return True
        
        # 深圳A股: sz00开头或sz30开头  
        if code_lower.startswith(('sz00', 'sz30')):
            return True
        
        return False
    
    def _parse_day_file(self, file_path: Path) -> List[Dict]:
        """
        解析.day文件
        
        Args:
            file_path: .day文件路径
            
        Returns:
            日线数据列表
        """
        data_list = []
        
        try:
            with open(file_path, 'rb') as f:
                buffer = f.read()
                size = len(buffer)
                row_size = 32  # 每32个字节一组数据
                
                for i in range(0, size, row_size):
                    if i + row_size > size:
                        break
                        
                    # 解包数据
                    row = struct.unpack('IIIIIfII', buffer[i:i + row_size])
                    
                    # 解析日期 (YYYYMMDD格式)
                    date_int = row[0]
                    try:
                        trade_date = datetime.strptime(str(date_int), '%Y%m%d').date()
                    except ValueError:
                        logger.warning(f"无效日期: {date_int}")
                        continue
                    
                    # 价格除以100转为实际价格
                    data_list.append({
                        'date': trade_date,
                        'open': row[1] / 100.0,
                        'high': row[2] / 100.0,
                        'low': row[3] / 100.0,
                        'close': row[4] / 100.0,
                        'amount': row[5],
                        'volume': row[6],
                        'prev_close': row[7] / 100.0
                    })
        except Exception as e:
            logger.error(f"解析文件 {file_path} 失败: {e}")
            
        return data_list
    
    def _get_stock_file_path(self, code: str) -> Optional[Path]:
        """
        获取股票数据文件路径
        
        Args:
            code: 股票代码 (如 sh600000, sz000001)
            
        Returns:
            文件路径或None
        """
        code_lower = code.lower()
        
        # 文件名格式: sh600000.day, sz000001.day
        # 确定市场和文件路径
        if code_lower.startswith('sh'):
            market_path = self.sh_lday_path
            file_name = f"{code_lower}.day"
        elif code_lower.startswith('sz'):
            market_path = self.sz_lday_path
            file_name = f"{code_lower}.day"
        else:
            # 没有前缀,根据代码判断
            if code.startswith('6'):
                market_path = self.sh_lday_path
                file_name = f"sh{code}.day"
            elif code.startswith(('0', '3')):
                market_path = self.sz_lday_path
                file_name = f"sz{code}.day"
            else:
                logger.error(f"无法识别的股票代码: {code}")
                return None
        
        file_path = market_path / file_name
        
        if not file_path.exists():
            logger.warning(f"文件不存在: {file_path}")
            return None
            
        return file_path
    
    @lru_cache(maxsize=100)
    def read_day_data(self, code: str) -> List[StockDayData]:
        """
        读取股票日线数据(带缓存)
        
        Args:
            code: 股票代码
            
        Returns:
            日线数据列表
        """
        file_path = self._get_stock_file_path(code)
        if not file_path:
            return []
        
        data_list = self._parse_day_file(file_path)
        
        # 转换为StockDayData模型
        result = []
        for data in data_list:
            result.append(StockDayData(
                code=code,
                date=data['date'],
                open=data['open'],
                high=data['high'],
                low=data['low'],
                close=data['close'],
                amount=data['amount'],
                volume=data['volume'],
                prev_close=data['prev_close']
            ))
        
        logger.info(f"读取 {code} 数据: {len(result)} 条记录")
        return result
    
    def read_day_data_range(
        self, 
        code: str, 
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[StockDayData]:
        """
        读取指定时间范围的日线数据
        
        Args:
            code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            日线数据列表
        """
        all_data = self.read_day_data(code)
        
        # 过滤日期范围
        if not start_date and not end_date:
            return all_data
        
        filtered_data = []
        for data in all_data:
            if start_date and data.date < start_date:
                continue
            if end_date and data.date > end_date:
                continue
            filtered_data.append(data)
        
        return filtered_data
    
    def list_all_stocks(self) -> List[StockInfo]:
        """
        列出所有A股股票(排除ETF、债券、指数等)
        
        Returns:
            股票信息列表
        """
        stocks = []
        
        # 上海市场 - 文件名格式: sh600000.day
        if self.sh_lday_path.exists():
            for file in self.sh_lday_path.glob("*.day"):
                code = file.stem  # 获取不带.day的文件名,如 sh600000
                # 检查是否为A股代码(sh60或sh68开头)
                if self._is_a_share_stock(code):
                    stocks.append(StockInfo(
                        code=code,
                        market="sh"
                    ))
        
        # 深圳市场 - 文件名格式: sz000001.day
        if self.sz_lday_path.exists():
            for file in self.sz_lday_path.glob("*.day"):
                code = file.stem  # 获取不带.day的文件名,如 sz000001
                # 检查是否为A股代码(sz00或sz30开头)
                if self._is_a_share_stock(code):
                    stocks.append(StockInfo(
                        code=code,
                        market="sz"
                    ))
        
        logger.info(f"共找到 {len(stocks)} 只A股股票 (已过滤ETF、债券和指数)")
        return stocks
    
    def get_latest_date(self, code: str) -> Optional[date]:
        """
        获取股票最新数据日期
        
        Args:
            code: 股票代码
            
        Returns:
            最新日期或None
        """
        data = self.read_day_data(code)
        if data:
            return max(d.date for d in data)
        return None
    
    def get_stock_info(self, code: str) -> Optional[StockInfo]:
        """
        获取股票详细信息
        
        Args:
            code: 股票代码
            
        Returns:
            股票信息或None
        """
        data = self.read_day_data(code)
        if not data:
            return None
        
        market = "sh" if code.lower().startswith("sh") or code.startswith("6") else "sz"
        
        return StockInfo(
            code=code,
            market=market,
            latest_date=max(d.date for d in data),
            data_count=len(data)
        )
    
    def clear_cache(self):
        """清空缓存"""
        self.read_day_data.cache_clear()
        logger.info("缓存已清空")


# 全局实例(将在API服务中初始化)
tdx_reader: Optional[TDXReader] = None


def get_tdx_reader() -> TDXReader:
    """获取TDX读取器实例"""
    global tdx_reader
    if tdx_reader is None:
        raise RuntimeError("TDX读取器未初始化")
    return tdx_reader


def init_tdx_reader(tdx_path: str):
    """初始化TDX读取器"""
    global tdx_reader
    tdx_reader = TDXReader(tdx_path)
    logger.info(f"TDX读取器已初始化: {tdx_path}")

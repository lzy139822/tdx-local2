#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
SQLite数据库管理模块
用于保存选股策略和结果
"""
import sqlite3
import json
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import logging

from models import Strategy, SelectionResult

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Database:
    """数据库管理类"""
    
    def __init__(self, db_path: str = "./stock_selector.db"):
        """
        初始化数据库
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        
        cursor = self.conn.cursor()
        
        # 创建策略表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS strategies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                user_input TEXT NOT NULL,
                generated_code TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建选股结果表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS selection_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_id INTEGER NOT NULL,
                code TEXT NOT NULL,
                name TEXT,
                selected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metrics TEXT,
                FOREIGN KEY (strategy_id) REFERENCES strategies(id)
            )
        ''')
        
        # 创建索引
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_strategy_id 
            ON selection_results(strategy_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_code 
            ON selection_results(code)
        ''')
        
        self.conn.commit()
        logger.info(f"数据库初始化完成: {self.db_path}")
    
    def save_strategy(self, strategy: Strategy) -> int:
        """
        保存策略
        
        Args:
            strategy: 策略对象
            
        Returns:
            策略ID
        """
        cursor = self.conn.cursor()
        
        cursor.execute('''
            INSERT INTO strategies (name, description, user_input, generated_code)
            VALUES (?, ?, ?, ?)
        ''', (
            strategy.name,
            strategy.description,
            strategy.user_input,
            strategy.generated_code
        ))
        
        self.conn.commit()
        strategy_id = cursor.lastrowid
        
        logger.info(f"策略已保存: ID={strategy_id}, Name={strategy.name}")
        return strategy_id
    
    def get_strategy(self, strategy_id: int) -> Optional[Strategy]:
        """
        获取策略
        
        Args:
            strategy_id: 策略ID
            
        Returns:
            策略对象或None
        """
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM strategies WHERE id = ?', (strategy_id,))
        row = cursor.fetchone()
        
        if row:
            return Strategy(
                id=row['id'],
                name=row['name'],
                description=row['description'],
                user_input=row['user_input'],
                generated_code=row['generated_code'],
                created_at=datetime.fromisoformat(row['created_at']),
                updated_at=datetime.fromisoformat(row['updated_at'])
            )
        return None
    
    def list_strategies(self, limit: int = 100, offset: int = 0) -> List[Strategy]:
        """
        列出所有策略
        
        Args:
            limit: 返回数量限制
            offset: 偏移量
            
        Returns:
            策略列表
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM strategies 
            ORDER BY created_at DESC 
            LIMIT ? OFFSET ?
        ''', (limit, offset))
        
        strategies = []
        for row in cursor.fetchall():
            strategies.append(Strategy(
                id=row['id'],
                name=row['name'],
                description=row['description'],
                user_input=row['user_input'],
                generated_code=row['generated_code'],
                created_at=datetime.fromisoformat(row['created_at']),
                updated_at=datetime.fromisoformat(row['updated_at'])
            ))
        
        return strategies
    
    def update_strategy(self, strategy_id: int, **kwargs):
        """
        更新策略
        
        Args:
            strategy_id: 策略ID
            **kwargs: 更新字段
        """
        valid_fields = ['name', 'description', 'user_input', 'generated_code']
        update_fields = []
        values = []
        
        for field, value in kwargs.items():
            if field in valid_fields:
                update_fields.append(f"{field} = ?")
                values.append(value)
        
        if not update_fields:
            return
        
        values.append(datetime.now().isoformat())
        values.append(strategy_id)
        
        cursor = self.conn.cursor()
        cursor.execute(f'''
            UPDATE strategies 
            SET {', '.join(update_fields)}, updated_at = ?
            WHERE id = ?
        ''', values)
        
        self.conn.commit()
        logger.info(f"策略已更新: ID={strategy_id}")
    
    def delete_strategy(self, strategy_id: int):
        """
        删除策略及其结果
        
        Args:
            strategy_id: 策略ID
        """
        cursor = self.conn.cursor()
        
        # 删除选股结果
        cursor.execute('DELETE FROM selection_results WHERE strategy_id = ?', (strategy_id,))
        
        # 删除策略
        cursor.execute('DELETE FROM strategies WHERE id = ?', (strategy_id,))
        
        self.conn.commit()
        logger.info(f"策略已删除: ID={strategy_id}")
    
    def save_selection_results(self, results: List[SelectionResult]) -> int:
        """
        批量保存选股结果
        
        Args:
            results: 选股结果列表
            
        Returns:
            保存的记录数
        """
        cursor = self.conn.cursor()
        
        for result in results:
            metrics_json = json.dumps(result.metrics) if result.metrics else None
            
            cursor.execute('''
                INSERT INTO selection_results (strategy_id, code, name, metrics)
                VALUES (?, ?, ?, ?)
            ''', (
                result.strategy_id,
                result.code,
                result.name,
                metrics_json
            ))
        
        self.conn.commit()
        logger.info(f"保存了 {len(results)} 条选股结果")
        return len(results)
    
    def get_selection_results(
        self, 
        strategy_id: int,
        limit: int = 1000,
        offset: int = 0
    ) -> List[SelectionResult]:
        """
        获取选股结果
        
        Args:
            strategy_id: 策略ID
            limit: 返回数量限制
            offset: 偏移量
            
        Returns:
            选股结果列表
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM selection_results 
            WHERE strategy_id = ?
            ORDER BY selected_at DESC
            LIMIT ? OFFSET ?
        ''', (strategy_id, limit, offset))
        
        results = []
        for row in cursor.fetchall():
            metrics = json.loads(row['metrics']) if row['metrics'] else None
            
            results.append(SelectionResult(
                id=row['id'],
                strategy_id=row['strategy_id'],
                code=row['code'],
                name=row['name'],
                selected_at=datetime.fromisoformat(row['selected_at']),
                metrics=metrics
            ))
        
        return results
    
    def clear_selection_results(self, strategy_id: int):
        """
        清空策略的选股结果
        
        Args:
            strategy_id: 策略ID
        """
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM selection_results WHERE strategy_id = ?', (strategy_id,))
        self.conn.commit()
        logger.info(f"已清空策略 {strategy_id} 的选股结果")
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            logger.info("数据库连接已关闭")


# 全局数据库实例
db: Optional[Database] = None


def get_db() -> Database:
    """获取数据库实例"""
    global db
    if db is None:
        raise RuntimeError("数据库未初始化")
    return db


def init_db(db_path: str = "./stock_selector.db"):
    """初始化数据库"""
    global db
    db = Database(db_path)
    logger.info("数据库已初始化")

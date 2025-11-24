#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
FastAPI中转服务
提供TDX数据查询和AI选股API
"""
import os
from typing import List, Optional
from datetime import date
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import configparser
import logging

from models import (
    StockDayData, StockInfo, StockQueryRequest, 
    Strategy, StrategyCreateRequest, SelectionResult,
    SelectionResponse
)
from tdx_reader import init_tdx_reader, get_tdx_reader
from database import init_db, get_db
from ai_selector import init_ai_selector, get_ai_selector
from tdx_exporter import export_selection_results

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="通达信数据中转服务",
    description="提供通达信本地数据查询和AI选股功能",
    version="1.0.0"
)

# 添加CORS支持
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 数据查询API ====================

@app.get("/api/stocks", response_model=List[StockInfo])
async def list_stocks():
    """获取所有股票列表"""
    try:
        reader = get_tdx_reader()
        stocks = reader.list_all_stocks()
        return stocks
    except Exception as e:
        logger.error(f"获取股票列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stocks/{code}", response_model=StockInfo)
async def get_stock_info(code: str):
    """获取单个股票信息"""
    try:
        reader = get_tdx_reader()
        stock_info = reader.get_stock_info(code)
        if not stock_info:
            raise HTTPException(status_code=404, detail=f"股票 {code} 不存在")
        return stock_info
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取股票信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stocks/{code}/day", response_model=List[StockDayData])
async def get_stock_day_data(
    code: str,
    start: Optional[date] = Query(None, description="开始日期"),
    end: Optional[date] = Query(None, description="结束日期")
):
    """获取股票日线数据"""
    try:
        reader = get_tdx_reader()
        
        if start or end:
            data = reader.read_day_data_range(code, start, end)
        else:
            data = reader.read_day_data(code)
        
        if not data:
            raise HTTPException(status_code=404, detail=f"未找到股票 {code} 的数据")
        
        return data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取日线数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/stocks/batch", response_model=dict)
async def batch_query_stocks(request: StockQueryRequest):
    """批量查询股票数据"""
    try:
        reader = get_tdx_reader()
        results = {}
        
        for code in request.codes:
            try:
                data = reader.read_day_data_range(code, request.start_date, request.end_date)
                results[code] = [d.model_dump() for d in data]
            except Exception as e:
                logger.warning(f"查询 {code} 失败: {e}")
                results[code] = []
        
        return {
            "success": True,
            "data": results,
            "total": len(results)
        }
    except Exception as e:
        logger.error(f"批量查询失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== AI选股API ====================

@app.post("/api/strategies", response_model=Strategy)
async def create_strategy(request: StrategyCreateRequest):
    """创建选股策略(仅生成代码,不执行)"""
    try:
        selector = get_ai_selector()
        
        # 生成策略代码
        generated_code = selector.generate_strategy_code(request.user_input)
        
        # 创建策略对象
        strategy = Strategy(
            name=request.name,
            description=request.description,
            user_input=request.user_input,
            generated_code=generated_code
        )
        
        # 保存到数据库
        db = get_db()
        strategy.id = db.save_strategy(strategy)
        
        return strategy
    except Exception as e:
        logger.error(f"创建策略失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/strategies", response_model=List[Strategy])
async def list_strategies(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """获取策略列表"""
    try:
        db = get_db()
        strategies = db.list_strategies(limit, offset)
        return strategies
    except Exception as e:
        logger.error(f"获取策略列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/strategies/{strategy_id}", response_model=Strategy)
async def get_strategy(strategy_id: int):
    """获取单个策略"""
    try:
        db = get_db()
        strategy = db.get_strategy(strategy_id)
        if not strategy:
            raise HTTPException(status_code=404, detail=f"策略 {strategy_id} 不存在")
        return strategy
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取策略失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/strategies/{strategy_id}/execute")
async def execute_strategy(
    strategy_id: int,
    max_stocks: int = Query(100, ge=1, le=1000, description="最多返回股票数")
):
    """执行选股策略"""
    try:
        db = get_db()
        selector = get_ai_selector()
        
        # 获取策略
        strategy = db.get_strategy(strategy_id)
        if not strategy:
            raise HTTPException(status_code=404, detail=f"策略 {strategy_id} 不存在")
        
        # 清空旧结果
        db.clear_selection_results(strategy_id)
        
        # 执行策略
        import time
        start_time = time.time()
        results = selector.execute_strategy(strategy, max_stocks)
        execution_time = time.time() - start_time
        
        # 保存结果
        if results:
            db.save_selection_results(results)
        
        return {
            "strategy": strategy.model_dump(),
            "results": [r.model_dump() for r in results],
            "total_count": len(results),
            "execution_time": execution_time
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"执行策略失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/strategies/create-and-execute")
async def create_and_execute_strategy(
    request: StrategyCreateRequest,
    max_stocks: int = Query(100, ge=1, le=1000)
):
    """创建并执行策略(一站式)"""
    try:
        selector = get_ai_selector()
        result = selector.create_and_execute_strategy(request, auto_save=True, max_stocks=max_stocks)
        
        strategy = result['strategy']
        results = result['results']
        return {
            "strategy": strategy.model_dump(),
            "results": [r.model_dump() for r in results],
            "total_count": result['total_count'],
            "execution_time": result['execution_time']
        }
    except Exception as e:
        logger.error(f"创建并执行策略失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/strategies/{strategy_id}/results", response_model=List[SelectionResult])
async def get_selection_results(
    strategy_id: int,
    limit: int = Query(1000, ge=1, le=10000),
    offset: int = Query(0, ge=0)
):
    """获取选股结果"""
    try:
        db = get_db()
        results = db.get_selection_results(strategy_id, limit, offset)
        return results
    except Exception as e:
        logger.error(f"获取选股结果失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/strategies/{strategy_id}/export")
async def export_results(
    strategy_id: int,
    format: str = Query("csv", regex="^(text|csv|detailed|all)$")
):
    """导出选股结果为文件"""
    try:
        db = get_db()
        
        # 获取结果
        results = db.get_selection_results(strategy_id, limit=10000)
        if not results:
            raise HTTPException(status_code=404, detail="没有选股结果")
        
        # 导出文件
        export_info = export_selection_results(results, format)
        
        return {
            "success": True,
            "message": "导出成功",
            "data": export_info
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"导出结果失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/strategies/{strategy_id}")
async def delete_strategy(strategy_id: int):
    """删除策略"""
    try:
        db = get_db()
        db.delete_strategy(strategy_id)
        return {"success": True, "message": "删除成功"}
    except Exception as e:
        logger.error(f"删除策略失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 系统API ====================

@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "TDX Relay Service",
        "version": "1.0.0"
    }


@app.post("/api/cache/clear")
async def clear_cache():
    """清空数据缓存"""
    try:
        reader = get_tdx_reader()
        reader.clear_cache()
        return {"success": True, "message": "缓存已清空"}
    except Exception as e:
        logger.error(f"清空缓存失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 静态文件服务 ====================

# 挂载静态文件目录
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    """返回首页"""
    static_index = "static/index.html"
    if os.path.exists(static_index):
        return FileResponse(static_index)
    return {
        "message": "通达信数据中转服务",
        "docs": "/docs",
        "api": "/api"
    }


# ==================== 启动初始化 ====================

@app.on_event("startup")
async def startup_event():
    """应用启动时初始化"""
    logger.info("正在启动服务...")
    
    # 读取配置
    config = configparser.ConfigParser()
    config.read('./config.ini', encoding='utf-8')
    
    # 初始化TDX读取器
    tdx_path = config.get('TDX', 'INSTALL_PATH', fallback='D:/new_tdx')
    init_tdx_reader(tdx_path)
    
    # 初始化数据库
    db_path = config.get('DATABASE', 'SQLITE_PATH', fallback='./stock_selector.db')
    init_db(db_path)
    
    # 初始化AI选股器
    api_key = config.get('AI', 'API_KEY', fallback='')
    api_base = config.get('AI', 'API_BASE', fallback='https://api.deepseek.com/v1')
    model = config.get('AI', 'MODEL', fallback='deepseek-chat')
    
    if api_key:
        init_ai_selector(api_key, api_base, model)
        logger.info("AI选股器已启用")
    else:
        logger.warning("未配置AI API密钥,AI选股功能将不可用")
    
    logger.info("服务启动完成!")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理"""
    logger.info("正在关闭服务...")
    
    try:
        db = get_db()
        db.close()
    except:
        pass
    
    logger.info("服务已关闭")


if __name__ == "__main__":
    import uvicorn
    
    # 读取配置
    config = configparser.ConfigParser()
    config.read('./config.ini', encoding='utf-8')
    
    host = config.get('API', 'HOST', fallback='0.0.0.0')
    port = config.getint('API', 'PORT', fallback=8000)
    
    uvicorn.run(app, host=host, port=port)

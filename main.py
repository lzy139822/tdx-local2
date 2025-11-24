#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
主启动文件
启动TDX中转服务和AI选股系统
"""
import uvicorn
import configparser
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """主函数"""
    # 读取配置
    config = configparser.ConfigParser()
    try:
        config.read('./config.ini', encoding='utf-8')
    except Exception as e:
        logger.error(f"读取配置文件失败: {e}")
        return
    
    # 获取API配置
    host = config.get('API', 'HOST', fallback='0.0.0.0')
    port = config.getint('API', 'PORT', fallback=8000)
    
    # 检查AI配置
    api_key = config.get('AI', 'API_KEY', fallback='')
    if not api_key or api_key == 'your-api-key-here':
        logger.warning("=" * 60)
        logger.warning("警告: 未配置AI API密钥!")
        logger.warning("请编辑 config.ini 文件,设置 [AI] 部分的 API_KEY")
        logger.warning("AI选股功能将不可用,但数据查询功能正常")
        logger.warning("=" * 60)
    
    logger.info("=" * 60)
    logger.info("通达信数据中转服务启动中...")
    logger.info(f"访问地址: http://{host if host != '0.0.0.0' else 'localhost'}:{port}")
    logger.info(f"API文档: http://{host if host != '0.0.0.0' else 'localhost'}:{port}/docs")
    logger.info("=" * 60)
    
    # 启动服务
    uvicorn.run(
        "api_service:app",
        host=host,
        port=port,
        reload=False,
        log_level="info"
    )


if __name__ == "__main__":
    main()

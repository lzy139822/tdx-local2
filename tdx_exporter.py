#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
通达信自选股导出工具
生成通达信可导入的自选股文件
"""
import struct
from typing import List
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TDXExporter:
    """通达信自选股导出器"""
    
    @staticmethod
    def export_to_text(codes: List[str], output_file: str = "selected_stocks.txt"):
        """
        导出为文本文件(最简单,手动导入)
        
        Args:
            codes: 股票代码列表
            output_file: 输出文件路径
        """
        with open(output_file, 'w', encoding='utf-8') as f:
            for code in codes:
                # 去掉市场前缀,通达信格式
                clean_code = code.replace('sh', '').replace('sz', '')
                
                # 确定市场代码
                if code.lower().startswith('sh') or code.startswith('6'):
                    market = '1'  # 上海
                else:
                    market = '0'  # 深圳
                
                # 格式: 市场代码\t股票代码
                f.write(f"{market}\t{clean_code}\n")
        
        logger.info(f"导出文本文件成功: {output_file}, 共 {len(codes)} 只股票")
        return output_file
    
    @staticmethod
    def export_to_csv(codes: List[str], names: List[str] = None, output_file: str = "selected_stocks.csv"):
        """
        导出为CSV文件
        
        Args:
            codes: 股票代码列表
            names: 股票名称列表
            output_file: 输出文件路径
        """
        import csv
        
        with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['市场', '代码', '名称'])
            
            for i, code in enumerate(codes):
                clean_code = code.replace('sh', '').replace('sz', '')
                
                if code.lower().startswith('sh') or code.startswith('6'):
                    market = '上海'
                else:
                    market = '深圳'
                
                name = names[i] if names and i < len(names) else ''
                writer.writerow([market, clean_code, name])
        
        logger.info(f"导出CSV文件成功: {output_file}, 共 {len(codes)} 只股票")
        return output_file
    
    @staticmethod
    def generate_import_instructions(output_file: str) -> str:
        """
        生成导入说明
        
        Args:
            output_file: 输出文件路径
            
        Returns:
            导入说明文本
        """
        instructions = f"""
通达信自选股导入说明
===================

方法一: 使用文本文件导入(推荐)
1. 打开通达信软件
2. 进入自选股界面(快捷键: Ctrl+D 或点击"自选")
3. 右键点击空白处,选择"批量导入"
4. 选择文件: {output_file}
5. 确认导入

方法二: 手动添加
1. 打开通达信软件
2. 进入自选股界面
3. 逐个输入股票代码添加

注意事项:
- 导入前建议备份现有自选股
- 导入后请检查是否有重复股票
- 部分停牌或退市股票可能无法导入
"""
        return instructions
    
    @staticmethod
    def export_with_metrics(
        codes: List[str],
        metrics_list: List[dict],
        output_file: str = "selected_stocks_detailed.csv"
    ):
        """
        导出详细信息(包含选股指标)
        
        Args:
            codes: 股票代码列表
            metrics_list: 指标列表
            output_file: 输出文件路径
        """
        import csv
        
        # 收集所有指标字段
        all_fields = set()
        for metrics in metrics_list:
            if metrics:
                all_fields.update(metrics.keys())
        
        all_fields = sorted(list(all_fields))
        
        with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            
            # 写入表头
            header = ['市场', '代码'] + all_fields
            writer.writerow(header)
            
            # 写入数据
            for i, code in enumerate(codes):
                clean_code = code.replace('sh', '').replace('sz', '')
                
                if code.lower().startswith('sh') or code.startswith('6'):
                    market = '上海'
                else:
                    market = '深圳'
                
                row = [market, clean_code]
                
                metrics = metrics_list[i] if i < len(metrics_list) else {}
                for field in all_fields:
                    value = metrics.get(field, '') if metrics else ''
                    # 格式化数值
                    if isinstance(value, float):
                        value = f"{value:.2f}"
                    row.append(value)
                
                writer.writerow(row)
        
        logger.info(f"导出详细CSV文件成功: {output_file}, 共 {len(codes)} 只股票")
        return output_file


def export_selection_results(results: List, export_format: str = "csv") -> dict:
    """
    导出选股结果
    
    Args:
        results: SelectionResult列表
        export_format: 导出格式(text/csv/detailed)
        
    Returns:
        导出信息字典
    """
    exporter = TDXExporter()
    
    codes = [r.code for r in results]
    names = [r.name or '' for r in results]
    metrics_list = [r.metrics for r in results]
    
    exported_files = []
    
    if export_format == "text":
        file = exporter.export_to_text(codes)
        exported_files.append(file)
    
    elif export_format == "csv":
        file = exporter.export_to_csv(codes, names)
        exported_files.append(file)
    
    elif export_format == "detailed":
        file = exporter.export_with_metrics(codes, metrics_list)
        exported_files.append(file)
    
    else:  # all
        exported_files.append(exporter.export_to_text(codes))
        exported_files.append(exporter.export_to_csv(codes, names))
        if any(metrics_list):
            exported_files.append(exporter.export_with_metrics(codes, metrics_list))
    
    # 生成导入说明
    instructions = exporter.generate_import_instructions(exported_files[0])
    
    # 保存说明文件
    instructions_file = "导入说明.txt"
    with open(instructions_file, 'w', encoding='utf-8') as f:
        f.write(instructions)
    exported_files.append(instructions_file)
    
    return {
        'files': exported_files,
        'count': len(codes),
        'instructions': instructions
    }

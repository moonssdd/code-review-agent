# 设计文档

## 目标
掌握 LLM 调用、Prompt 设计、工具集成。

## 架构
读取代码 → AST 结构分析 + 静态检查 → 拼接 Prompt → 调用 LLM → 输出 Markdown 报告

## 模块
- read_file：读取代码
- analyze_python_structure：AST 分析函数、类、导入
- simple_static_checks：检查 eval、裸 except、TODO、长函数、缺 docstring
- call_llm：调用大模型
- main：主流程
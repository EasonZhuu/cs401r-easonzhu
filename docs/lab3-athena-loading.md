# 第 4/14 节：Athena 读取训练数据

对应老师英文指南 Task 1 → Requirements 的 Feature Store / Athena 取数要求，以及中文要求整理 4.1。

## 本节修改

在 `churn_training_skeleton.py` 的 `load_features_from_feature_store()` 中，保留老师提供的 SQL，完成执行、等待、记录查询 ID、读取结果与返回 DataFrame 的部分，移除该函数原来的 `NotImplementedError`。

```python
query.run(query_string=query_string,
          output_location=f"s3://{artifacts_bucket}/artifacts/athena-results/")
query.wait()
print(f"Athena QueryExecutionId: {query.get_query_execution()['QueryExecution']['QueryExecutionId']}")
df = query.as_dataframe()
if df.empty:
    raise ValueError("No Feature Store rows in the requested ingest-date range")
print(f"Loaded {len(df):,} customer rows from Feature Store via Athena")
return df
```

`run()` 提交 SQL，并让 Athena 把查询结果写入原 bucket 的 `artifacts/athena-results/`；`wait()` 等待云端执行完成。随后打印真实 QueryExecutionId，供最终证据脚本从 Athena 导出 SQL 和运行状态。`as_dataframe()` 下载的是本次 Athena 查询的结果，而不是开发用的 CSV 输入。空结果报错用于明确提示写入日期范围问题，避免带着空数据进入训练。

还按老师要求在 `docs/lab3-model-design.md` 顶部声明 `Track: A+B`；设计正文留在后续相应小节完成。

## 保留的 SQL 为什么这样写

1. 日期转换成 UTC epoch 秒，因为 `event_time` 是 Fractional；这次使用 `2026-01-01` 至 `2027-01-01`，覆盖实际写入时间。它不是特征观察窗口 T。
2. 通过 `ROW_NUMBER()` 按客户分组，以 `event_time DESC, write_time DESC` 保留最新记录，避免 Feature Store 多版本记录导致重复客户。
3. `NOT is_deleted` 排除软删除记录。
4. `ORDER BY customer_id` 固定返回行顺序，使后面的固定随机种子划分可复现。
5. 返回会员等级，但它不在 `FEATURE_COLUMNS` 中，用于后面的切片评估。老师默认也排除了规则分数 `churn_risk_score`。

## 实际验证

运行的是这个函数本身，未进入 `main()` 的训练流程。资源名通过当前 `terraform output -json` 读取，使用本机课程 IAM 用户身份，未切换到 MLEngineer。

| 检查 | 结果 |
|---|---|
| 第 3 节前置复核 | 保存的数据就绪状态为 true，原就绪查询在 Athena 中仍为 SUCCEEDED |
| 本节取数查询 | `1cd550a0-6d3e-4949-a042-fe5d6a52c75a`，SUCCEEDED |
| DataFrame | 9,999 行、14 列 |
| 14 列的构成 | 客户 ID + 11 个模型特征 + churn_label + loyalty_tier |
| 客户 ID | 9,999 个唯一值，升序排列 |
| 缺失值 | 0 |
| 标签 | 7,799 个 0，2,200 个 1 |
| 数据一致性 | 全部返回字段与本次重新生成的特征一致；允许 CSV 解析造成的数值类型差异，浮点容差 rtol=1e-8、atol=1e-8 |
| 取数路径 | Feature Store offline table → Athena，未调用本地数据加载器 |

[完整 SQL、身份、扫描量与核验结果](lab3-athena-loader-check.json)已保存。临时 CSV 与核验日志位于 D 盘课程 `.tools/lab3/`，没有新安装软件。

本次属于取数函数验证，不是最终用于评分的训练运行。后续最终训练仍要实际调用该函数，并在 `train-final.log` 中保存那次运行自己的 QueryExecutionId。

本节完成后进度为 **4/14**。下一节实现数据预处理与 XGBoost 训练。

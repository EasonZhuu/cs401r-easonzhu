# Lab 3 第 3 节：AWS、Bedrock 和训练数据准备

对应中文指南 4.1「从哪里取训练数据」。本节按完整教学部分连续完成，不再将每个 AWS 操作拆成一次需要用户说“继续”的停顿。

**第 3/14 节已完成。**最终验证时间：2026-10-17 22:24:11 UTC（America/Denver：2026-10-17 16:24:11）。

## 目标和路径

让后续训练代码能用本机的课程 AWS 身份，通过 Athena 查询真实的 Feature Store offline table。

数据路径：

```text
Lab 2 原始合成交易 CSV
  -> S3 raw/customers/
  -> Glue crawler 登记 schema
  -> transform job 清洗交易
  -> S3 processed/customers/
  -> feature-engineer job 聚合客户特征和 outcome-window 标签
  -> Feature Store PutRecord
  -> online store / 异步 offline store
  -> Athena 聚合检查
```

只恢复 Terraform 平台不能满足目标；平台不会自动装入客户记录。直接上传旧 offline Parquet 也不能证明本次真实写入，因此本次只上传原始 CSV，让原管道重新计算并写入 Feature Store。

## 已完成的实际检查

| 项目 | 本次实际结果 |
|---|---|
| Bedrock | Titan 1024 维和 Haiku `OK` 已在本节前面的实际调用中通过，见原验证记录 |
| Terraform | 42 项资源恢复成功，恢复后 plan 为 No changes |
| 原始 CSV | 163,255 行，13,582,469 字节 |
| 原始 SHA256 | `38b19325c00ee0d5e05b4588066d16aa124a8cc822c3362709d6145e0ba612b2`，与原 Lab 2 审计及本次 S3 读回一致 |
| Crawler | `SUCCEEDED`，`northstar_dev.customers` 指向正确 raw 路径 |
| transform job | `SUCCEEDED`，执行 127 秒；4 个 Parquet，157,627 条交易 |
| feature-engineer job | `SUCCEEDED`，执行 163 秒；2 个 Parquet，9,999 位唯一客户 |
| 标签 | 7,799 个 `churn_label=0`，2,200 个 `churn_label=1` |
| 所有客户特征 | 除本次生成的 `event_time` 外，全部字段与已审计备份一致，数值比较容差为 `rtol=1e-8, atol=1e-8` |
| online store | 抽查 `CUST-10000000` 和 `CUST-10009999`，16 个字段均与本次生成的特征一致 |
| offline store | 状态 `Active`，54 个实际生成的 Parquet 文件 |
| Athena | `SUCCEEDED`；9,999 行、9,999 位唯一客户；标签 7,799 / 2,200；0 个无效标签；最早和最晚 event_time 均等于本次写入时间 |

CSV 上传的首次 multipart 传输被网络重置，后改用此文件的单次传输并完整读回 SHA256 核对；没有更换数据内容。每个 Glue Run ID 都在启动后保存，等待时查询同一个 run，没有重复启动来检查状态。

Athena 就绪查询 ID：`ff101954-d10b-405b-85d8-8e58f8708d49`。SQL 查询实际的 `northstar_dev.northstar_dev_customer_features`，按客户保留最新记录并排除 soft-deleted 行；本次扫描 186,443 字节，未复用旧查询结果。SQL、状态、扫描量和返回值均保存在恢复 JSON 中。

## 数据时间含义

- 特征使用 `2026-04-01` 及以前的购买记录。
- 标签来自 `(2026-04-01, 2026-06-30]` 的 outcome window。
- 本次 `event_time` 是重新写入 Feature Store 的时间，不是特征观察窗口截止日期。后续训练的查询日期参数必须覆盖实际写入时间。

## 证据与下一节边界

- [本次数据恢复、Run ID 和查询证据](lab3-data-restoration.json)
- [平台恢复](lab3-platform-restore.md)
- [已有 Bedrock 实际验证](bedrock-access-verification.txt)

本节的 Athena 查询只做数据就绪检查；不是最终训练取数证据。第 4 节再实现 `churn_training_skeleton.py` 中的 `load_features_from_feature_store()`，执行完整有序取数并保存那次训练运行自己的 QueryExecutionId。当前没有修改训练骨架、训练模型或运行 RAG 评测。

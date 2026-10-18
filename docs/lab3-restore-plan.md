# Lab 3：训练数据资源恢复预览

预览时间：2026-10-17 09:10:18 UTC（America/Denver：2026-10-17 03:10:18）。

对应教学第 3/14 节，以及中文指南 4.1「从哪里取训练数据」。

## 已核对的结果

- 原 `infrastructure/environments/dev` 配置通过 `terraform validate`。
- 读取原远程 backend，`terraform state list` 成功且没有资源；plan JSON 的 prior state 也没有受管资源。
- Terraform 1.16.2，沿用锁定的 AWS provider 5.100.0，没有升级工具或修改基础设施配置。
- `cost-pause.auto.tfvars` 实际设置为 `enable_nat_gateway = true`，plan 中也确认开启。
- 完整计划：**42 to add, 0 to change, 0 to destroy**。`-detailed-exitcode` 返回 2 表示存在计划变更，生成成功。
- 本次没有执行 `terraform apply`，没有恢复数据或运行 Glue，也没有训练模型。

最初在受限执行环境中单独运行 validate，provider schema 进程未能响应；在与成功 plan 相同的执行权限下重新运行后通过。未通过修改配置绕过验证。

## 42 项分别做什么

| Terraform 模块 | 新增数 | 用途 |
|---|---:|---|
| `storage` | 9 | 数据 S3 bucket、访问保护、加密、版本、生命周期和四个目录前缀 |
| `feature_store` | 1 | `northstar-dev-customer-features`，提供后续真实的 Feature Store offline 数据来源 |
| `glue` | 8 | `northstar_dev` 数据库、两种连接、crawler、两项数据处理 job 及其脚本 |
| `iam` | 9 | DataEngineer、MLEngineer、ModelMonitor 的角色、策略和绑定 |
| `vpc` | 13 | VPC、子网、路由、安全组、Internet Gateway、NAT Gateway 和 EIP |
| `sagemaker` | 2 | SageMaker Studio domain 和用户配置 |
| **合计** | **42** | 恢复原 Lab 2 平台的完整配置 |

该计划包含 Studio 和整套网络；本地 XGBoost 训练本身不需要 Studio。之所以出现在预览中，是因为原 dev 根配置也管理它们，不能将此完整计划描述为只创建数据 bucket 或最小训练环境。

NAT Gateway、公共 IPv4 等资源会在创建后持续计费，其他存储与服务操作也可能产生费用。此处没有估算金额；恢复后应按照课程流程及时清理。

## 为什么创建资源后还不能立即训练

Terraform 恢复的是平台结构。此计划会上传两个 Glue 脚本、创建 S3 前缀，但不会自动上传客户原始数据、执行 ETL 或向 Feature Group 写入客户记录。

后续还需要恢复课程数据，完成实际 Feature Store 写入并等离线数据可查询，再通过 Athena 验证记录数、标签和查询来源。此前校验过的本地快照能帮助恢复，但不能替代评分要求的 Feature Store offline store / Athena 取数。

## 本地预览文件

保存于课程目录下的私有工具目录，不放入公开仓库：

- `.tools/lab3/restore-preview.tfplan`：二进制计划。
- `.tools/lab3/restore-preview.json`：完整 JSON，可能包含敏感状态信息。
- `.tools/lab3/restore-preview.log`：文本预览。

以上路径相对于 `D:/A study/BYU/05 26 Fall/CS 401`。本文件只是可阅读的摘要；后续实施前应重新核对云端状态和计划，不能把旧计划当作资源已经恢复的证明。

# Lab 3：云端平台恢复

2026-10-17，教学第 3/14 节；对应中文指南 4.1「从哪里取训练数据」。

本文件记录平台刚恢复时的状态，后续客户数据管道与 Athena 已完成；最新结果见[第 3 节完整检查](lab3-data-readiness.md)。下文“尚未导入”描述的是平台恢复当时。

## 做了什么

先确认 AWS 账户与原课程 backend 一致，重新生成并核对计划仍为 42 项新增、0 修改、0 删除，再应用这份新计划。原 Terraform 配置没有修改。

实际结果：`Apply complete! Resources: 42 added, 0 changed, 0 destroyed.`

恢复后重新运行 Terraform plan，退出码为 0：`No changes. Your infrastructure matches the configuration.`

## 实际服务检查

- 数据 S3 bucket 已存在。
- `northstar-dev-customer-features` 状态 `Created`，online store 已启用。
- Glue database `northstar_dev` 与 Feature Store offline table `northstar_dev_customer_features` 已存在。
- transform、feature-engineer 两个 Glue job 及脚本已恢复，尚未运行 job。
- DataEngineer、MLEngineer、ModelMonitor 三个角色已恢复。
- Studio domain 与 MLEngineer 用户状态均为 `InService`。
- VPC 中 NAT Gateway 状态为 `available`。
- 客户数据目录中非空文件为 0；Feature Store 自动生成的零字节文件不算客户数据。

检查脚本最初将 `terraform state list` 中的 3 项 data source 也算进云资源，造成误判；核对地址后已修正为 **42 项受管资源、3 项 data source**。也修正了零字节服务文件的统计。没有因此重复 apply 或修改云端配置。

## 为什么还不能训练

现在已有平台、权限和表结构。Terraform 不会自动把备份客户数据变成 Feature Store 记录；客户数据还没有导入，也没有执行 ETL。

下一小步恢复原始数据并检查输入；后续通过实际管道写入 Feature Store，等待 offline store 可查询，再用 Athena 验证训练数据。当前不得将 `platform_ready` 当作 `training_data_ready`。

NAT 等已创建资源现已开始产生相应使用费用，完成课程验证后按指南清理。

## 记录

- [AWS 服务核验结果](lab3-platform-verification.json)
- [Terraform apply 完整输出](lab3-platform-apply-output.txt)
- [先前计划的资源用途说明](lab3-restore-plan.md)

新计划、完整 JSON、恢复后 plan 日志和核验脚本保存在课程 D 盘 `.tools/lab3/`，没有加入公开仓库。没有导入客户数据、启动 Studio 计算应用、运行 Glue job 或训练模型，也没有修改原评分 tag。

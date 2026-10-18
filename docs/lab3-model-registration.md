# Lab 3 Section 8: Model Registry

对应老师指南：**Task 1 — Churn Prediction Model → Requirements → Final model registered in the Model Registry with status PendingManualApproval**，以及 **Your final, graded run** 和 **One chain of numbers** 的证据一致性要求。

本节输入是第 7 节已评估的模型、指标和 lineage；输出是原课程账户中可追溯的模型版本。注册保存模型版本和推理配置，审批状态仍需人工决定。

## 本次实际结果

- Model package group：`northstar-churn-models`
- Version：`1`
- ARN：`arn:aws:sagemaker:us-east-1:173506956686:model-package/northstar-churn-models/1`
- 注册状态：`Completed`
- 审批状态：`PendingManualApproval`
- MLflow run：`6d3dfd0d527543feafe2d37712a54b92`
- Athena query：`a4a936c4-dcbe-46d7-bf7c-d2d1627e6c9f`
- AUC：0.7838；Precision@10%：0.7133；Recall@10%：0.3242
- AUC 提升 CI：[0.0415, 0.0802]

模型字节与第 7 节完全相同，SHA256 为 `8ef39c2469667a6e718318826294962f88679b4ac30c3c259ea1d6b88a1d95dc`。本节未重新训练。

## 改了什么以及原因

1. `churn_training_skeleton.py` 中补完 `save_and_register_model()`。保存模型和 metadata 后先完成 MLflow run，再调用注册函数，这样注册前可以检查 run 已 FINISHED、指标一致，并把 run ID 写入 Registry。后续完整训练入口会执行这条顺序。
2. 新增 `scripts/register_churn_model.py`。它也可独立使用，允许把已经完成的实际训练结果注册，无需重训。先检查模型 SHA、三个评分门槛、MLflow 指标与 query ID；再上传打包文件、读回核验、创建或复用指定 group，并调用 `create_model_package()`。所有评估指标转为字符串写入 `CustomerMetadataProperties`，同时写入模型/source/bundle SHA 和两个来源 ID。审批状态在代码中固定为 `PendingManualApproval`。
3. 新增 `inference/churn/inference.py`。`model_fn()` 检查模型哈希、XGBoost 版本与特征顺序，然后加载原生模型。`transform_fn()` 接收按训练顺序的 JSON/CSV 行或具有明确特征名的 JSON records，检查 11 列输入，返回流失概率。

打包结构为：

```text
model.tar.gz
  model.xgb                 # 实际为 XGBoost 3.2.0 UBJSON
  model_metadata.json
  evaluation_metrics.json
  training-lineage.json
  code/inference.py
```

本地 SageMaker v2 SDK 的镜像配置表滞后于 AWS 新镜像版本，`image_uris.retrieve()` 无法解析新的版本标签。因此从 SDK 取 region 对应的官方 registry 账户，再通过 ECR `BatchGetImage` 实查 `3.2-0` 标签，使用返回的 digest 固定镜像。AWS 的部分通用 XGBoost 文档仍列到 3.0；当前 [AWS available images](https://aws.github.io/deep-learning-containers/reference/available_images/) 列有 3.2-0，实查结果也确认镜像存在。没有修改环境依赖版本。

容器配置为框架模式，设置 `SAGEMAKER_PROGRAM=inference.py` 和 `SAGEMAKER_SUBMIT_DIRECTORY=/opt/ml/model/code`，以便使用自定义原生模型加载器。不是将 UBJSON 文件交给旧版容器默认 pickle 加载器。

## 复核范围

进入本节前，重新检查上一节的实际 Athena 查询、MLflow metrics 与 6 个服务端 artifacts，全部通过。

注册后独立调用 `DescribeModelPackage`，确认 version 1、Completed、PendingManualApproval；所有指标及 lineage 字段与原记录一致。重新从 Registry 指向的 S3 地址下载 tar.gz，压缩包哈希一致；包内模型也与本地模型及重新下载的 MLflow 模型一致。原训练源码另从 MLflow 下载核验，保留原 hash，没有用后来添加注册功能的源码覆盖历史 artifact。

使用包内推理脚本，对原验证集 3,000 行重新预测，所有概率逐项完全一致；AUC、top-300 名单命中 214 人、precision 和 recall 都与报告相同。JSON 行、具名 JSON records、CSV 及四种错误输入检查通过。

当前检查限于本地 handler 和注册内容；没有运行完整 Docker 镜像启动测试或部署 SageMaker endpoint。

`train-final.log` 是将被选定的最终模型原始日志 `train-evaluation.log` 原样复制到老师要求的文件名。原日志仍有当时尚未实现注册的 TODO，实际后续注册记录单独保存在 `model-registration.log`，两者通过模型 hash 和 run ID 对应。

证据：

- [Registry 完整读回](lab3-evidence/model-registry.json)
- [注册请求](lab3-evidence/model-registration-request.json)
- [注册日志](lab3-evidence/model-registration.log)
- [独立核验](lab3-registry-check.json)
- [最终指标及正式评估报告](lab3-evaluation-report.md)

第 8/14 节完成。第 9 节进入 Task 2 的 RAG 政策文档与 prompt 模板检查。

# 第 6/14 节：MLflow App 实验记录与参数比较

对应老师指南 **Experiment tracking — use an MLflow App, and read the warning first**。

## 本节目标

训练结果要能够从 MLflow 服务端检索，不能只存在于本地控制台。App 是提供跟踪功能的服务；`northstar-churn` 是组织实验的 experiment；每个 run 对应一组训练条件与结果；artifact 是保存的模型、源码和指标文件。

## 创建的服务与复用的资源

- 使用 `CreateMlflowApp` 创建 `northstar-mlflow`，实际状态 `Created`，服务端 MLflow 3.10.1。
- 复用原 Terraform outputs 中的 `northstar-dev-MLEngineer` 及数据 bucket，artifact store 为原 bucket 的 `artifacts/mlflow/`。
- 模型自动注册模式为 `AutoModelRegistrationDisabled`，模型注册留到第 8 节。
- 创建前查询没有已有 App，也没有 Tracking Server；本次只调用 App 创建 API，没有创建 Tracking Server、bucket 或 IAM role。

[App 实际配置](lab3-mlflow-app.json)记录完整 ARN、角色、路径与状态。App 创建成功后再开始写入实验记录。

## 代码具体改了什么

实现 `churn_training_skeleton.py` 的 `track_run()`：

1. 检查传入的是 `mlflow-app/` ARN，并要求传入已经计算好的类别权重。
2. `mlflow.set_tracking_uri()` 指向该 App，`set_experiment()` 选中 `northstar-churn`。
3. `start_run()` 新建或继续一条明确的 run，`log_params()` 保存参数，`log_metrics()` 保存数值指标。
4. 除训练超参数外，还记录 XGBoost 版本、实际类别权重、缺失值策略、输入列顺序与查询日期范围。
5. 用 tags 关联 Athena QueryExecutionId、原始训练时间和数据摘要；上传模型、训练源码及指标 JSON。
6. 将真实 Run ID 写回 `args.mlflow_run_id` 并打印，供后续运行证据使用。

为传递数据来源，Athena 取数函数现在把 QueryExecutionId 同时放入 `df.attrs`；`main()` 从中获取，并记录训练开始/完成时间交给 `track_run()`。数据内容与 SQL 没有改变。

## 如何补记第 5 节

第 5 节的模型和训练源码均先按原 SHA256 核对。将原模型加载后重新预测，AUC 与原记录一致，再上传原模型和原源码，没有重新训练来冒充那次运行。

该 run 标记 `recorded_after_training=true`，保留实际的原始训练开始和完成时间，同时注明此次记录上传时间。第 5 节报告现在包含真实 MLflow Run ID，状态不再是 pending。

## 三组受控比较

重新通过 Athena 取数，确认有序数据 SHA256 与第 5 节一致，再确认训练/验证矩阵、标签和会员等级与原划分逐项相同。三组均使用 6,999/3,000 划分、seed 42、XGBoost 3.2.0、类别权重 3.544805194805195、最多 200 轮及 20 轮 early stopping。每个新配置只改变一个因素。

| Run | max_depth | eta | 验证 AUC | 验证 logloss | 保留轮数 |
|---|---:|---:|---:|---:|---:|
| development-depth6-eta0.1（第 5 节补记） | 6 | 0.1 | 0.783813 | 0.555894 | 11 |
| depth3-eta0.1 | 3 | 0.1 | 0.780360 | 0.532251 | 48 |
| depth6-eta0.05 | 6 | 0.05 | 0.782694 | 0.537005 | 32 |

`max_depth=3` 检查更浅的树是否改善泛化，`eta=0.05` 检查更小的学习步长是否改善排序。按这个固定验证集的 AUC，原配置最高；另外两组 logloss 更低。因此只能说原配置在本次 AUC 比较中暂时领先，不能据此宣称在所有指标上更优，也没有做统计显著性结论。

## 从服务端验证了什么

- `mlflow.search_runs()` 实际返回预期的 3 条 run，均为 `FINISHED`。
- 参数、实际类别权重和全部已记录指标读回后与本地一致。
- 三个模型都通过 MLflow artifact 下载接口重新下载，SHA256 与本地训练文件一致。
- 下载的模型重新加载后，全部验证预测与本地模型一致。
- 原运行保留原 Athena QueryExecutionId；两次新训练共享本次真正执行的 Athena 取数 ID，输入数据及划分相同。

[完整服务端记录与核验](lab3-mlflow-comparison.json)，以及[服务端查询导出的比较表](lab3-mlflow-runs.csv)均已保存。模型与下载验证文件保存在课程 D 盘 `.tools/lab3/step6-runs/`。

本节使用开发 AUC 和 logloss 做实验比较。正式 baseline、提升置信区间、precision/recall 与会员等级切片评估留在第 7 节；最终用于评分的训练也要有自己的 MLflow run 和证据链。当前没有注册或批准模型。

进度：**6/14 已完成**。下一节：Baseline、业务指标、置信区间和分组评估。

API 依据：[AWS CreateMlflowApp](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_CreateMlflowApp.html)。

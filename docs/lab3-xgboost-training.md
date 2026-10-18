# 第 5/14 节：预处理与 XGBoost 训练

对应老师指南 Task 1 → Requirements 中 Model、Hyperparameters、Class imbalance，以及 Guard against leakage。路线为 A+B。

## 输入、输出和本节范围

输入：第 4 节函数从真实 Feature Store offline store / Athena 读回的 9,999 位客户，14 列。模型只用 `FEATURE_COLUMNS` 中的 11 个数值特征；客户 ID、`churn_label`、会员等级不进入输入矩阵，规则分数 `churn_risk_score` 也保持老师的默认排除设置。

输出：一个本地训练的 XGBoost Booster，返回验证 AUC 最佳的轮次，并保存开发模型、验证预测和数据划分记录。正式的 baseline、CI、精确率/召回率门槛、分组评估和注册留在后续小节，本节的单个 AUC 不能代替完整评分评估。

## 本次修改

### 预处理

`preprocess_features()` 原先将特征缺失值填成 -1，并静默删除缺失标签的行。现在：

- 明确检查必需列；标签只允许 0/1，缺失或其他标签立即报错。
- 不静默删行，保证客户、特征、标签和会员等级保持行对应。
- `X` 转为 float64，`y` 转为 int32；拒绝无穷值。
- 保留 NaN，让 XGBoost 原生处理特征缺失，不使用人为 -1，也不在全数据上拟合填补器。本次真实输入中缺失值为 0，因此该策略没有改变当前任何特征值。

### 数据划分

保留老师规定的 `test_size=0.30, random_state=42, stratify=y`。在同一次 `train_test_split()` 中传入会员等级，给后续分组评估保留对应关系。验证驱动还同步划分 customer_id，确认训练和验证没有客户重叠、等级与客户一致。

### 训练

老师已经提供 `train_model()` 的 DMatrix、参数化 XGBoost 调用和训练集类别权重计算，这些继续复用。

- `objective=binary:logistic`，输出流失概率。
- `max_depth=6, eta=0.1, num_round=200, min_child_weight=5, subsample=0.8, colsample_bytree=0.8`，从命令行参数传入。
- `scale_pos_weight` 使用训练集负类数/正类数：`5459 / 1540 = 3.544805194805195`，不是从全部数据或参考值硬编码。
- 将默认 early stopping 改为显式 `EarlyStopping(rounds=20, data_name="validation", metric_name="auc", maximize=True, save_best=True)`，确保返回验证 AUC 最佳的模型。

这是必要的区别：`xgb.train()` 的普通 early stopping 默认返回最后一轮，而非最佳轮；后续直接 `model.predict()` 会使用返回模型中保留的树。`save_best=True` 使保存和预测都使用最佳轮次。已对照本机 XGBoost 3.2.0 的 callback 实现验证。

## 实际运行结果

| 项目 | 结果 |
|---|---|
| XGBoost | 3.2.0 |
| 取数 | 本次重新执行 Athena，9,999 行；有序数据 SHA256 与第 4 节一致 |
| 输入矩阵 | `(9999, 11)`，缺失值 0 |
| 训练集 | 6,999：负类 5,459、正类 1,540 |
| 验证集 | 3,000：负类 2,340、正类 660 |
| 客户重叠 | 0，会员等级对齐 |
| 类别权重 | 3.544805194805195 |
| 最佳迭代编号 | 10，从 0 开始计数 |
| 返回模型的 boosting 轮数 | 11；200 是允许的最大轮数 |
| 开发验证 AUC | 0.783813，详细精度见 JSON |
| 输出概率 | 全部有限，均在 [0,1] 内 |
| 序列化验证 | 保存 UBJ 后重新加载，所有验证预测完全一致 |

本次是开发运行。AUC 说明这一轮模型的排序表现，不表示已完成精确率、召回率、baseline lift CI 或切片评估。

## 文件与后续

- [本次参数、查询来源、指标和模型摘要](lab3-training-check.json)
- [完整开发训练日志](lab3-training-check.log)
- 模型、数据划分和验证预测保存在课程 D 盘 `.tools/lab3/step5-training/`。
- 后续第 6 节已把本次保留的真实运行记录与原模型补记到 MLflow App，并通过服务端读回及 artifact 下载核验。`lab3-training-check.json` 中已有真实 Run ID；详情见 [MLflow 实验记录](lab3-mlflow-experiments.md)。

本节未创建 SageMaker Training Job、端点或新 bucket/role，也未注册模型。总体进度：**5/14 已完成**。

## API 依据

- [XGBoost API：训练、early stopping 与 save_best](https://xgboost.readthedocs.io/en/stable/python/python_api.html)
- [XGBoost FAQ：缺失值处理](https://xgboost.readthedocs.io/en/stable/faq.html#how-to-deal-with-missing-values)

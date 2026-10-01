# Lab 2 架构图说明

这张图按照最新 Lab 2 Full Guide 画出完成实验后的 NorthStar 平台，包含 Lab 1 基础设施和 Lab 2 新增资源。沿用 Lab 1 的 draw.io、AWS 图标、Helvetica 字体和分区配色。

- [完整架构图](lab2-architecture-diagram.png)
- [可编辑 draw.io 文件](lab2-architecture-diagram.drawio)
- [矢量 SVG](lab2-architecture-diagram.svg)
- 来源：[Canvas Lab 2](https://byu.instructure.com/courses/38938/assignments/1476008)、[Full Guide](https://byu.instructure.com/courses/38938/files/13861988?wrap=1)

图表示目标设计；部署是否成功需要之后的 Terraform、Glue job run 和 Feature Store 查询证据确认。

## 1. 上半部分：程序在哪里运行、怎么联网

从外向内读边框：AWS Region `us-east-1` → VPC `10.0.0.0/16` → AZ `us-east-1a` → 两个子网。

| 区域 | 里面的资源 | 作用 |
| --- | --- | --- |
| 公有子网 `10.0.100.0/24` | NAT Gateway，关联一个 Elastic IP | 为私有子网提供出站通道 |
| 私有子网 `10.0.1.0/24` | SageMaker Domain / Studio、Glue ETL workers | 程序在这里运行，启动时不分配公有 IP |
| VPC 外的区域级服务 | S3、Glue Catalog、Feature Store、ECR、CloudWatch | 通过服务 API 访问 |
| 全局服务 | IAM | 决定身份及资源操作权限 |

Lab 1 的 Studio 原来在公有子网。Lab 2 把它迁到私有子网，并设置 `app_network_access_type = "VpcOnly"`。公有子网留下来放 NAT。

私有计算资源访问外部服务时，路径是：

```text
Studio / Glue worker
  → 私有路由表：0.0.0.0/0 → NAT Gateway
  → 公有子网中的 NAT（使用 Elastic IP）
  → 公有路由表：0.0.0.0/0 → Internet Gateway
  → Internet / AWS 公共 API
```

NAT 允许资源主动建立连接并接收返回流量。外网不能经这个 NAT 主动发起连接到私有资源。图中 ECR、CloudWatch 的虚线表达逻辑服务访问，实际出站仍经过上述路径。

SageMaker 沿用 Lab 1 的安全组。Glue 作业通过 NETWORK connection 绑定私有子网和 Glue 安全组；Glue 安全组需要引用自身的全端口入站规则，供 worker 之间通信。安全组控制网络通信，IAM 控制 API 操作，两者都要配置。

## 2. 中间部分：数据如何变成训练特征

图中各个 S3 方框是同一个 Bucket `northstar-dev-data-{account-id}` 内的不同前缀。Bucket 沿用 Lab 1 的版本控制、SSE-S3 和阻止公有访问设置。

按绿色实线从左向右读：

```text
northstar-raw-sample.csv
  → raw/customers/                 CSV，交易级别
  → Glue Transform
  → processed/customers/           Parquet，仍是交易级别
  → Glue Feature Engineer
      ├─ features/customers/       作业自己写出的客户级 Parquet
      └─ Feature Store PutRecord   客户特征记录
           ├─ online store         在线读取
           └─ features/offline-store/  服务管理的离线存储
```

每个客户原始数据里可以有多笔交易。Transform 负责类型转换、空值处理、日期规范化和按 `transaction_id` 去重。它不会把所有客户交易聚合成一条：输出中 `customer_id` 仍然可以重复。

Feature Engineer 再把交易聚合为客户特征，最后每位客户一行。Feature Group `northstar-dev-customer-features` 有 16 个定义：2 个 key、13 个特征、1 个 `churn_label`。记录标识是 `customer_id`；`event_time` 使用 Fractional 类型，传入 Unix epoch 秒。

图上方还有一条元数据支路：

```text
raw/customers/ → Glue Crawler → Glue Catalog → Transform 读取 schema
```

Crawler 扫描 CSV 的结构，在数据库 `northstar_dev` 注册表 `customers`。Catalog 保存字段、类型和数据位置；交易数据仍在 S3。Transform 使用 Catalog 找到和解释数据，再从 S3 读取内容。图用虚线区分这条 schema 支路。

`artifacts/glue/` 存放两个 Glue 脚本，由 Terraform 上传。DataEngineer 必须能读取这些脚本，但不需要向 `artifacts/` 写入。

`features/customers/` 和 `features/offline-store/` 必须分别使用。前者是我们的脚本直接写出的 Parquet；后者由 Feature Store 使用执行角色权限管理目录和写入。Feature Store 的 offline store 约有 15 分钟延迟。

## 3. 时间窗口：避免把未来结果放进特征

固定 `T = FEATURE_CUTOFF = 2026-04-01`，`SNAPSHOT = 2026-06-30`。

| 数据范围 | 用途 |
| --- | --- |
| `purchase_date <= T` | 计算全部客户特征 |
| `T < purchase_date <= SNAPSHOT` | 生成客户之后是否流失的标签 |

例如客户在 3 月买过东西，之后直到 6 月 30 日都没有购买：用 4 月 1 日以前的数据计算特征，标签为 `churn_label = 1`。如果结果窗口有购买，标签为 0。

不能用 `today()` 或整份数据最大日期计算特征；否则运行日期会改变结果，或者把未来信息泄漏进去。Starter Kit 把结果窗口叫 `holdout`，这里指时间线上的结果窗口。Lab 3 才将已标记的客户行划分为机器学习训练集和测试集。

## 4. 下半部分：三个角色各做什么

| 角色 | 负责的工作 | 主要权限边界 |
| --- | --- | --- |
| `northstar-dev-DataEngineer` | 运行 Crawler、Transform、Feature Engineer，写特征 | 可读写 `raw/`、`processed/`、`features/`；只读 `artifacts/glue/`；不能写 `artifacts/`，不能启动训练 |
| `northstar-dev-MLEngineer` | Studio 开发、以后读取特征并训练模型 | 沿用 Lab 1；可读写 `features/`、`artifacts/`；不能写 `raw/`、`processed/` |
| `northstar-dev-ModelMonitor` | 观察指标、告警和处理作业元数据 | 只读 `artifacts/`；可操作 CloudWatch 指标/告警并写日志；不能写 S3、调用 endpoint 或启动 processing job |

DataEngineer 的 trust policy 包含 Glue、Lambda 和 SageMaker。SageMaker 信任关系用于 Feature Group 的执行角色；因此图里不用额外创建 Lambda 资源。

ModelMonitor 是观察角色。后续 Lab 的漂移分析执行角色 `ModelMonitorExecution` 是另一件事，当前 Lab 2 不需要把执行资源提前加进图。

## 5. S3 的五条生命周期规则

| 规则名 | 操作对象 | 时限 |
| --- | --- | --- |
| `expire-raw-data` | `raw/` 当前版本 | 90 天 |
| `expire-raw-versions` | `raw/` 非当前版本 | 30 天 |
| `expire-processed-versions` | `processed/` 非当前版本 | 30 天 |
| `expire-feature-versions` | `features/` 非当前版本 | 60 天 |
| `expire-datacapture` | `datacapture/` 当前版本 | 7 天 |

“非当前版本”指开启版本控制后被新版本替代的旧版本。`datacapture/` 的保留规则在 Lab 2 设置，实际写入数据的组件到 Lab 5 才出现。

## 6. 图对应哪些 Terraform 模块

| 模块 | 图中负责的内容 |
| --- | --- |
| `modules/vpc/` | 私有子网、NAT、EIP、私有路由表和关联；保留 Lab 1 公有网络 |
| `modules/storage/` | 原有 S3 Bucket、前缀和五条生命周期规则 |
| `modules/iam/` | 原有 MLEngineer，加 DataEngineer、ModelMonitor |
| `modules/sagemaker/` | Domain 迁到私有子网，设置 VpcOnly |
| `modules/glue/` | Catalog database、Crawler、两个 ETL jobs、网络连接及脚本对象 |
| `modules/feature_store/` | Feature Group、16 项定义、online/offline 配置 |

架构图这一步完成后，下一步是修改 `modules/vpc/`。网络先配置好，后续 Studio 和 Glue 才能使用私有子网。

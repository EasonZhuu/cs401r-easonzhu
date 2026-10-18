# Lab 3 Section 9: Policy and prompt audit

对应老师指南：**Task 2 — LLM System → Track B: Offer Generation (RAG)**；具体代码材料是 `prompt_templates/offer_generation_prompts.md` 的 **Template 1、2、3、5**。Template 4 的三种检索方式留给第 11 节，第 10 节先准备 chunk 和 embedding。

## 目标与输入输出

第 8 节已经有预测流失风险的模型。本节准备 RAG 生成优惠文案所需的事实来源和提示词：画像说明这个客户买什么，政策说明可以承诺什么。语料中没有商品目录、SKU、价格和库存，不能从它虚构商品或促销。

输入为四篇老师政策文件及老师 harness 的四个画像案例。输出为修正的工作模板、`rag_prompts.py` 中的提示词组装函数，以及静态核验记录。本节没有做向量检索、调用生成模型或运行 RAGAS。

## 政策来源与三个错误

四篇政策文件逐字节与原 Starter Kit 对比一致，未修改。原始 prompt 模板也仍保存在课程 `03-Lab3/Starter-Kit/`；修改发生在工作仓库的模板中。

| 文件 / document ID | 用途 |
|---|---|
| `loyalty-program-terms.md` / POL-LOY-011 | 等级门槛、积分、权益和 retention offer 条款 |
| `shipping-policy.md` / POL-SHP-007 | 标准/加急配送、地区限制和大件附加费 |
| `return-policy.md` / POL-RET-004 | 退货窗口、购买时等级、final sale 排除 |
| `customer-faq.md` / KB-FAQ-022 | FAQ 摘要；发生冲突时原政策优先 |

Template 3 的三个植入错误已改正：

| 原模板错误 | 正确规则 | 来源 |
|---|---|---|
| Gold 为 $2,000–$9,999.99 | $2,000–$4,999.99 | POL-LOY-011 §2 |
| Platinum 从 $10,000 起 | 从 $5,000 起 | POL-LOY-011 §2 |
| Gold 满 $200 免费 expedited shipping | 所有等级的 expedited / overnight 都按原价收费 | POL-SHP-007 §2 |

上述门槛基于 **trailing 12-month qualifying spend**，不是 lifetime value。

## 提示词改动与理由

Template 1 现在明确接收校验后的画像等级，并要求条件式表达，例如 `If your current membership is Gold...`。原 Template 2 本来就有等级字段，因此问题不只是“模型没看到等级”，还在于没有明确处理这个字段的可靠性。Lab 2 按 lifetime value 生成的等级近似值，不能替代会员系统的实际等级，更不能证明 Silver 客户“再花 $15 就升级”。

Template 2 保留原始数值，并增加明确标为 heuristic 的解释：online ratio ≤0.30 为主要线下，≥0.70 为主要线上，其余混合；diversity ×8 约等于观察到的类别数。这些阈值是实现选择，没有声称能提高客户响应率。文案只推荐 `top_categories` 中已知的类别，不将 diversity 解释成购买过某个未知类别。

Template 3 修正三个错误，并移除“可以直接给折扣/bonus points”“credit 一定未用且没有增量成本”等无充分证据的建议。它保留为人工核对参考；运行时组装 Templates 1、2、5，政策主张仍需实际检索片段支持，避免把人工权益表当作检索缺失时的替代事实。

Template 5 继续约束 final sale、过期 offer、越权请求及 prompt injection。增加或强化的边界包括：30% 上限不代表可以自行创设折扣；生日奖励、剩余 gear credit、积分余额、当前 sale 均不能假定已存在；45 天默认有效期不能证明已签发一张 offer；免费标准配送不能忽略 Mexico 和 oversized 限制。

Body 长度按最新主指南收敛为 **2–3 句**；Subject 与内部 Rationale 分开。Rationale 可说明选择理由，客户可见 Body 不暴露 churn probability、内部 ID 或 lifetime value。没有足够上下文时，明确不足，不为了凑一个 incentive 而编造。

`rag_prompts.py` 的 `build_prompts(customer, retrieved_context)` 读取 Markdown fenced code blocks，代入字段，返回 `system` 和 `user` 两段文本。它不发起 AWS 调用；未知等级、空类别、越界比例或空政策证据会报错。这是输入检查，不能证明模型一定遵守提示词。

## 数据与评分更新

实际 `DescribeFeatureGroup` 返回 16 个字段，包含 loyalty tier、lifetime value 等，但**没有 `top_categories`**。本节只使用 harness 给出的类别。第 12 节处理真实客户时，需要从 feature cutoff 之前的交易历史补充类别，并记录来源。不能把 harness fixture 描述成从当前 Feature Group 读到的真实类别字段。

模板原有的 RAGAS 0.80 / 0.75 / 0.70 门槛已按主指南及 2026-10-12 公告修正：四个案例至少跑两次，报告逐例得分、均值与范围、judge model、每个指标的限制及一次实测 before/after。后续还需把 customer profile 加入评价 contexts，让 judge 看得到画像事实来源。当前没有任何 RAGAS 分数，prompt 更改是否改善结果尚待第 13 节实测。

## 本节实际验证

- 进入本节前重新从 AWS 检查 Registry、MLflow 和模型包；上一节的版本 1、PendingManualApproval、原模型 hash 及 3,000 条预测一致性仍通过。
- 四篇政策与老师原文件的字节一致性通过，SHA256 已记录。
- Gold、Bronze、Platinum、Silver 四个 harness 案例全部完成本地 prompt 填充，等级和已知类别存在，无未替换的预期字段；`ground_truth` 未注入 prompt。
- 四种错误输入检查通过：未知等级、空类别、online ratio 越界、空政策证据。
- Python 语法检查通过。实际模型调用数为 0；本地预览使用全部四篇政策文本，仅用于字段填充检查，不是假称已经完成检索。

核验结果见 [lab3-prompt-check.json](lab3-prompt-check.json)。第 9/14 节完成；下一节准备文本切块与 Titan embeddings。

# Lab 3 Section 11: FAISS retrieval and Template 4

对应老师指南：**Task 2 → Track B → Vector store / Document whether you re-rank**，以及工作 prompt 文件的 **Template 4: Retrieval Query Construction → Option A / B / C**。

本节输入是第 10 节保存的 48 个政策片段和 48×1,024 Titan V2 向量。输出是持久化 FAISS 索引、三种可调用的检索方式、四案例的真实检索结果。尚未调用优惠生成模型或 RAGAS judge，因此不能据此宣布某一种策略的 context recall 最高。

## 索引及相似度

新增 `rag_retrieval.py`。`build_faiss_index()` 先复核 chunk/source/hash 和归一化矩阵，再创建 `faiss.IndexFlatIP(1024)` 并按原顺序加入 48 行；索引保存在 `artifacts/lab3-rag/policy.faiss`，配置及文件 hash 保存在 `faiss-manifest.json`。

查询先用与政策相同的 Titan V2、dimensions=1024、normalize=true 生成向量，再执行 FAISS search。两个向量都为单位长度时，内积对应 cosine similarity；分数用于政策片段排序，不代表权益适用概率。依据：[FAISS metrics documentation](https://github.com/facebookresearch/faiss/wiki/MetricType-and-distances)。

选择 Flat exact search 的理由是语料只有 48 行，直接比较全部向量足够简单，也便于验证。当前没有引入近似索引或独立 re-ranker；后续的排序质量与冗余片段问题要通过生成/评价观察。FAISS 返回的 row ID 对应原 chunk 顺序，加载时逐元素重建并核对索引与原向量矩阵。

## 三种查询的实际实现

| 策略 | 查询意图 | 范围 |
|---|---|---|
| A | 指定客户 tier，查 points、shipping threshold、return window、birthday reward | 全部四篇政策 |
| B | 查 final sale、expired offers、validity、single use、combinability | 全部四篇政策 |
| C | 按 tier 和 online/in-store 描述查 entitlements、shipping thresholds | 仅 POL-LOY-011、POL-SHP-007 |

`query_spec()` 忠实保留老师 Template 4 的 query 文本和 C 的过滤范围。C 使用模板原来的 `online_to_store_ratio > 0.5` 判 online；第 9 节画像解释的 0.30/0.70 是另一项独立 heuristic，不改写这里用于比较的原始查询。

老师将 C 命名为 Hybrid with metadata filter；这里实际实现的是“画像相关向量查询 + document ID 过滤”，没有额外的 BM25 词法融合。

当前每次取 **top_k=4**。对这个小语料先完整搜索 48 行，再限制到 allowed document IDs，最后取 top 4；与在允许子集上精确搜索等价。这样不会先截断四条后再过滤，导致明明有允许片段却只剩一两条。若允许集合为空或没有匹配项，结果为空，不扩大过滤范围。

返回值包含 query、过滤范围、embedding request 来源，以及每条结果的 rank、score、row ID、chunk ID、document ID、章节和原文。`format_context()` 用实际 chunk ID 与来源标签组装下一节将使用的政策上下文；画像和评测 ground_truth 不参与索引或检索查询。

## 四案例的实测结果

Gold、Bronze、Platinum、Silver 各执行 A/B/C，共 **12 次检索**，每次返回 4 个片段。共有 **9 个不同查询文本**：A 四条，C 四条，B 为一条所有客户共享的限制查询。首次成功的 query embedding 请求 9 次、共 **142 input tokens**，B 后三次命中缓存。

以下表格仅记录特定政策表/原句是否在当前 top 4 中出现：

| 检索内容 | A | B | C |
|---|---:|---:|---:|
| POL-LOY-011 §4 会员权益表 | 4/4 | 0/4 | 4/4 |
| POL-SHP-007 §2 配送门槛原章节 | 0/4 | 0/4 | 4/4 |
| 明确写出没有免费加急配送的原句 | 0/4 | 0/4 | 4/4 |
| final sale 直接限制（原退货政策或 FAQ） | 0/4 | 4/4 | 0/4 |
| POL-LOY-011 §5.1 retention offer 条款 | 0/4 | 4/4 | 0/4 |

这是片段存在性诊断，**不是 RAGAS context recall、完整政策覆盖率或模型正确率**。B 在四个客户中使用相同查询，4/4 不代表四次独立的新查询实验。

Gold 的实际 A 排序：

1. POL-LOY-011 §4 Tier Benefits，score **0.6969**。
2. KB-FAQ-022 Loyalty，score **0.5395**。
3. POL-RET-004 §1.1 Platinum extended window，score **0.4574**。
4. POL-LOY-011 §2 Tiers，score **0.4560**。

因此 A 已经找到了最关键的 tier table，但较相近的 FAQ/等级片段占用了其余位置，遗漏配送和 final sale 限制。B 能补充限制，但单独使用 B 又缺少具体 tier 权益。C 改善了配送信息覆盖，不过固定过滤范围排除了原退货政策和 FAQ，因此无法取到 final sale 直接规则。

这些现象支持后续比较“权益查询与限制查询组合、去重”的方案；当前还没有执行该改动或宣称效果提高。第 12 节先接生成，第 13 节再对三种原始策略运行 RAGAS，并记录一次明确的 before/after 改动及结果。

## 验证范围

- 先复核上一节保存文件、向量形状/范数/hash、全部 48 个缓存与原矩阵逐元素一致，未重复调用政策 embedding。
- 保存后重新读取 FAISS，确认 48 行、1,024 维、inner-product metric，与原矩阵逐元素一致。
- 用全部 48 个政策向量分别测试五种过滤集合，**240 次**排序与分数独立对照 NumPy；再对 **12 次实际查询**独立计算 dot product，结果一致，分数误差容限 1e-6。
- 未知 document ID / 空过滤集合返回空；k 大于语料时只返回已有 48 条；零向量、错误维度、NaN 和非正 k 共四项错误输入被拒绝。
- 每条返回原文与 chunk ID 对应；将实际检索结果接入第 9 节 prompt renderer，所有来源 ID 保留。没有执行生成。
- 禁止网络后重放全部 12 次检索，结果及分数一致，额外模型调用 0。

可查看：[完整片段和分数](lab3-evidence/retrieval-probe.json)、[核验 JSON](lab3-retrieval-check.json)、[实际检索日志](lab3-retrieval-probe.log)、[FAISS manifest](../artifacts/lab3-rag/faiss-manifest.json)。

在项目目录运行项目 Python 加 `rag_retrieval.py --build-index` 可重建本地索引；可用 `--query` 指定政策问题、`--doc-id` 限定来源。未缓存的 query 会调用 Titan；原有缓存可以复用。第 11/14 节完成，下一节接入 Bedrock 优惠生成。

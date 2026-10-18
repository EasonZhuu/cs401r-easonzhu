# Lab 3 Section 10: Policy chunks and Titan embeddings

对应老师指南：**Task 2 — LLM System → Track B: Offer Generation (RAG) → Requirements** 中的 **Embedding model** 和 **Chunking strategy documented: size, overlap, and why**。

## 目标与输入输出

输入是第 9 节核对过的四篇英文政策原文。输出是带来源信息的 48 个文本块，以及真实 Titan 模型返回的 48×1,024 数值矩阵。下一节才能用它建立 FAISS 索引、比较检索方式；当前没有执行检索、生成优惠或 RAGAS 评测。

Embedding 将文本映射为向量，让后续检索能比较查询与政策片段的语义相似度。单个维度不是一个命名业务特征，embedding 也不会替模型判断权益是否真的适用；原文和来源必须一起保留。

## 切块设计

`rag_index.py` 的 `chunk_documents()` 按 Markdown 的 `##`、`###` 分章节，保留章节中的段落和完整表格。只有标题、没有正文的父章节与第一个子章节合并，例如配送问题及其第一个子问题，避免产生只有标题的向量。

- 上限：每个原文块 **250 个 whitespace-separated words**，不是 Titan tokenizer 的 250 tokens。
- 实际范围：**21–245 words**。
- overlap：**0 words**。当前每个章节都能完整放入，不需要通过滑动窗口重叠重复句子；来源偏移连续覆盖原文。跨章节的权益与限制仍需下一节检索同时找全，0 overlap 不代表已解决上下文完整性问题。
- 保留表格：四篇文件共 **6 张 Markdown 表格**均完整保留；不把表头与各等级的行拆开。
- 遇到未来超过上限的章节会明确报错，需要重新审查切块方式，避免静默截断规则。

| 文件 | 块数 |
|---|---:|
| customer-faq.md | 6 |
| loyalty-program-terms.md | 15 |
| return-policy.md | 14 |
| shipping-policy.md | 13 |
| 合计 | **48** |

每块保存 `chunk_id`、`doc_id`、文件名、title、effective_date、章节路径、原文起止字符、原文件/块内容 SHA256，以及原文 `text`。传给 embedding 的 `embedding_text` 在原文前加 document ID、标题和章节路径，让短章节也有出处语境。没有加入改写后的优惠指南、评测答案或客户画像。

例如 `POL-SHP-007:003:c163e7eb41` 是 `2. Free Shipping Thresholds`，包含整个标准配送门槛表，也包含“Expedited and overnight are charged at full rate for all tiers”的限制句。这样不会只取到 Gold 免费标准配送的一行而丢掉同章节的加急限制。

## 模型与调用

模型：`amazon.titan-embed-text-v2:0`，region：`us-east-1`，输出 **1,024 维 float32**，请求显式设置 `normalize=True`。

选择理由：语料和检索查询都是英文，Titan V2 面向文本检索；课程已完成该模型的访问验证，能够沿用 Bedrock 账户和现有依赖。保留 1,024 维作为首个可复现配置，当前数据量只有 48 行，无需先压缩维度。尚未与 Cohere 比较，因此不声称 Titan 的检索质量更高。正式模型选择与对照结论留给最终报告。

Titan embedding 使用 `bedrock-runtime.invoke_model`。请求 body 是 `inputText`、`dimensions`、`normalize`；不传文本生成用的 maxTokens、temperature 或 topP。客户端复用，配置连接/读取超时与有限次数 adaptive retry；读取响应后关闭 StreamingBody。

官方依据：[Titan V2 请求/响应格式](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-titan-embed-text.html)、[Titan embeddings 模型说明及按逻辑段落切分建议](https://docs.aws.amazon.com/bedrock/latest/userguide/titan-embedding-models.html)。

## 实际运行与缓存

本次 48 个块均为首次 embedding，完成 48 次成功的 InvokeModel 请求；服务端返回的 `inputTextTokenCount` 合计 **6,515 tokens**，单次 **70–342 tokens**。此计数含额外的文档/章节前缀，与原文 whitespace word count 不同。每块请求 ID 和 token 数均保存在 manifest。

缓存键包含输入文本 SHA256、model ID、region、dimensions、normalize。成功响应逐个落盘，避免中断后重做所有块；缓存内容身份与向量形状也会检查。缓存目录仅在本地保留，不进入 Git；可复核的 chunks、矩阵及 manifest 保留在项目内。

输出位于项目 `artifacts/lab3-rag/`：

| 文件 | 内容 | 本次大小 |
|---|---|---:|
| chunks.jsonl | 一行一个原文块与 metadata | 76,771 bytes |
| embeddings.npy | 按块顺序排列的 48×1,024 float32 矩阵 | 196,736 bytes |
| manifest.json | 输入哈希、参数、行顺序、输出哈希、请求来源 | 12,053 bytes |
| cache/ | 48 个可复用 embedding 响应，本地忽略 | — |

`manifest.json` 的 `chunk_ids_in_row_order` 说明矩阵第 i 行对应哪个块。下一节建立 FAISS 时必须保持这个映射；只有数字、没有原文映射的矩阵不能用于可追溯回答。

## 验证与运行方式

进入本节前，复查第 9 节的政策文件与模板 hash、四案例填充、没有将 ground_truth 注入 prompt，均通过。AWS CLI 和当前账户有效，控制面读回 Titan V2 为 ACTIVE，随后真实模型调用成功。

切块后按文件顺序拼接 `text`，与每个原文件 UTF-8 解码后的字符串完全一致；每块字符偏移和内容哈希一致，没有漏字、重复覆盖或跨文件合并。所有 chunk ID 唯一，6 张表格完整。

保存后重新加载矩阵，形状、dtype、输出哈希和块顺序全部一致；所有数字 finite，向量范数范围约 **0.99999994–1.00000012**。再将客户端替换为“任何联网即报错”的检查对象，读取全部 48 条缓存，逐元素与原矩阵完全一致，额外模型调用数为 0。

在项目目录，使用项目 `.venv` 的 Python 运行 `rag_index.py` 可只预览切块；加 `--embed` 会为未缓存文本生成向量；`--verify` 只检查已保存结果，不访问网络。没有安装新软件。

证据：[embedding 核验](lab3-embedding-check.json)、[实际调用日志](lab3-embedding-build.log)、[manifest](../artifacts/lab3-rag/manifest.json)。本节检查证明数据完整、向量有效及缓存可重用；检索是否召回正确政策，需第 11 节检验。

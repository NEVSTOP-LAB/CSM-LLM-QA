# Contributing to CSM-LLM-QA

感谢你对本项目的兴趣！本文档面向希望参与开发、运行测试或理解代码结构的贡献者。

---

## 开发安装

克隆仓库后以可编辑模式安装，并附带测试依赖：

```bash
git clone https://github.com/NEVSTOP-LAB/CSM-LLM-QA.git
cd CSM-LLM-QA
pip install -e .[test]
```

---

## 项目结构

```
.
├── csm_llm_qa/                 # SDK 主包（pip install -e . 后可 import）
│   ├── __init__.py         # 导出 CSM_QA / Message / AnswerResult
│   ├── api.py              # CSM_QA 主类
│   ├── llm.py              # OpenAI 兼容 LLM 客户端
│   ├── rag.py              # ChromaDB + Embedding 检索器
│   ├── providers.py        # provider 预设（deepseek / openai_compatible）
│   ├── prompts.py          # 默认 system prompt
│   ├── types.py            # Message / AnswerResult / Usage
│   └── sync_wiki.py        # CLI: python -m csm_llm_qa.sync_wiki
├── csm-wiki/               # 默认知识库目录（放置 .md 文档）
├── examples/
│   ├── basic_usage.py
│   └── multi_turn.py
├── tests/                  # 单元测试
├── pyproject.toml
└── requirements.txt
```

---

## 运行测试

```bash
python -m pytest tests/ -v
```

测试用 mock OpenAI 客户端 + 词袋式 fake embedding，无需真实 API key 与模型下载。

---

## 发布

本项目通过 GitHub Actions（[`.github/workflows/publish.yml`](.github/workflows/publish.yml)）在推送 `v*` 标签时自动发布到 PyPI，使用 OIDC Trusted Publisher 认证。

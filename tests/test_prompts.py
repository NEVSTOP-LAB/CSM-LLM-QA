"""Prompt 模板测试。"""

from csm_llm_qa.prompts import (
    CONTENT_RULES_BLOCK,
    CONTEXT_BLOCK_TEMPLATE,
    DEFAULT_SYSTEM_PROMPT,
    DEFAULT_WIKI_BASE_URL,
    EMPTY_CONTEXT_PLACEHOLDER,
    LENGTH_GUIDE_BLOCK,
    ROLE_BLOCK,
    SYNTAX_REFERENCE_BLOCK,
    _filter_empty_contexts,
    build_system_message,
    build_system_prompt,
)


# ─── 模块常量独立性测试 ─────────────────────────────────────────

def test_role_block_contains_csm_and_labview():
    assert "CSM" in ROLE_BLOCK
    assert "LabVIEW" in ROLE_BLOCK


def test_length_guide_block_contains_format_rules():
    assert "【回答长度与格式】" in LENGTH_GUIDE_BLOCK
    assert "确认/肯定性消息" in LENGTH_GUIDE_BLOCK
    assert "简单事实问题" in LENGTH_GUIDE_BLOCK


def test_content_rules_block_contains_rules():
    assert "【内容原则】" in CONTENT_RULES_BLOCK
    assert "仅据参考资料回答" in CONTENT_RULES_BLOCK
    assert "严格使用 CSM 官方语法" in CONTENT_RULES_BLOCK
    # 反幻觉规则 #9
    assert "禁止杜撰" in CONTENT_RULES_BLOCK
    assert "推断，请以官方文档为准" in CONTENT_RULES_BLOCK


def test_syntax_reference_block_contains_csm_syntax():
    assert "【CSM 语法参考】" in SYNTAX_REFERENCE_BLOCK
    assert "StateName >> Arguments" in SYNTAX_REFERENCE_BLOCK
    assert "StateName >> Arguments -@ TargetModule" in SYNTAX_REFERENCE_BLOCK
    assert "StateName >> Arguments -> TargetModule" in SYNTAX_REFERENCE_BLOCK
    assert "StateName >> Arguments ->| TargetModule" in SYNTAX_REFERENCE_BLOCK


def test_default_system_prompt_is_concatenation_of_blocks():
    """DEFAULT_SYSTEM_PROMPT 应由四个模块常量拼接而成。"""
    assert DEFAULT_SYSTEM_PROMPT.startswith(ROLE_BLOCK)
    assert LENGTH_GUIDE_BLOCK in DEFAULT_SYSTEM_PROMPT
    assert CONTENT_RULES_BLOCK in DEFAULT_SYSTEM_PROMPT
    assert SYNTAX_REFERENCE_BLOCK in DEFAULT_SYSTEM_PROMPT


# ─── 向后兼容性测试（与旧版行为一致）─────────────────────────────

def test_default_system_prompt_mentions_csm():
    assert "CSM" in DEFAULT_SYSTEM_PROMPT
    assert "LabVIEW" in DEFAULT_SYSTEM_PROMPT


def test_default_system_prompt_requires_wiki_links():
    """默认提示词应要求把关键信息写成指向 csm-wiki 的 Markdown 超链接。"""
    assert "Markdown" in DEFAULT_SYSTEM_PROMPT
    assert "链接" in DEFAULT_SYSTEM_PROMPT
    assert "csm-wiki" in DEFAULT_SYSTEM_PROMPT


def test_default_system_prompt_requires_csm_syntax_examples():
    """默认提示词应要求 CSM 消息示例严格使用官方语法。"""
    assert "官方语法" in DEFAULT_SYSTEM_PROMPT
    assert "StateName >> Arguments" in DEFAULT_SYSTEM_PROMPT
    assert "StateName >> Arguments -@ TargetModule" in DEFAULT_SYSTEM_PROMPT
    assert "StateName >> Arguments -> TargetModule" in DEFAULT_SYSTEM_PROMPT
    assert "StateName >> Arguments ->| TargetModule" in DEFAULT_SYSTEM_PROMPT
    assert "-><status>" in DEFAULT_SYSTEM_PROMPT
    assert "-><register>" in DEFAULT_SYSTEM_PROMPT


def test_default_wiki_base_url_points_to_csm_wiki_repo():
    assert DEFAULT_WIKI_BASE_URL.startswith("https://")
    assert "CSM-Wiki" in DEFAULT_WIKI_BASE_URL


# ─── build_system_prompt 测试 ────────────────────────────────────

def test_build_system_prompt_defaults_match_constant():
    """不传参时 build_system_prompt() 应与 DEFAULT_SYSTEM_PROMPT 完全一致。"""
    result = build_system_prompt()
    assert result == DEFAULT_SYSTEM_PROMPT


def test_build_system_prompt_custom_role():
    """替换 role 模块应生效，其余模块保持默认。"""
    custom = build_system_prompt(role="You are a pirate.")
    assert custom.startswith("You are a pirate.")
    assert LENGTH_GUIDE_BLOCK in custom
    assert CONTENT_RULES_BLOCK in custom
    assert SYNTAX_REFERENCE_BLOCK in custom


def test_build_system_prompt_custom_multiple_blocks():
    """同时替换多个模块。"""
    custom = build_system_prompt(
        role="Custom role.",
        content_rules="Rule 1. Be nice.",
    )
    assert custom.startswith("Custom role.")
    assert LENGTH_GUIDE_BLOCK in custom
    assert "Rule 1. Be nice." in custom
    assert "【内容原则】" not in custom  # 内置规则被完全替换
    assert SYNTAX_REFERENCE_BLOCK in custom


def test_build_system_prompt_preserves_syntax_reference():
    """替换其他模块时，语法参考默认保留。"""
    custom = build_system_prompt(role="Expert.")
    assert SYNTAX_REFERENCE_BLOCK in custom
    assert "-> TargetModule" in custom


# ─── build_system_message 测试 ───────────────────────────────────

def test_build_system_message_with_contexts():
    out = build_system_message(
        DEFAULT_SYSTEM_PROMPT, ["片段A", "片段B"]
    )
    assert out.startswith(DEFAULT_SYSTEM_PROMPT)
    assert "[片段 1]" in out
    assert "片段A" in out
    assert "[片段 2]" in out
    assert "片段B" in out


def test_build_system_message_empty_contexts():
    out = build_system_message(DEFAULT_SYSTEM_PROMPT, [])
    # 没有片段时应显示增强的占位提示（不再是简单的 "（无）"）
    assert EMPTY_CONTEXT_PLACEHOLDER in out
    assert "csm-wiki 仓库" in out


def test_build_system_message_all_empty_text_contexts():
    """全部 context 的 text 为空字符串时应视为空上下文。"""
    contexts = [
        {"text": "", "source": "a.md", "heading": "H"},
        {"text": "   ", "source": "b.md"},
    ]
    out = build_system_message(DEFAULT_SYSTEM_PROMPT, contexts)
    assert EMPTY_CONTEXT_PLACEHOLDER in out
    # 不应有片段编号（没有有效片段）
    assert "[片段 1]" not in out


def test_build_system_message_mixed_empty_and_valid_texts():
    """混合空 text 和有效 text 时，仅保留有效片段并正确编号。"""
    contexts = [
        {"text": "   ", "source": "empty.md"},            # 应被过滤
        {"text": "有效内容", "source": "valid.md"},        # 保留
        {"text": "", "source": "also_empty.md"},           # 应被过滤
    ]
    out = build_system_message(DEFAULT_SYSTEM_PROMPT, contexts)
    assert "有效内容" in out
    assert "[片段 1]" in out
    assert "valid.md" in out
    # 被过滤的 source 不应出现
    assert "empty.md" not in out
    assert "also_empty.md" not in out
    # 只有 1 个有效片段，不应出现 [片段 2]
    assert "[片段 2]" not in out


def test_build_system_message_with_metadata_includes_wiki_link():
    """传入带 source 的 dict 时，应把 source 拼成指向 csm-wiki 的链接。"""
    contexts = [
        {"text": "正文A", "source": "guide/intro.md", "heading": "概述"},
        {"text": "正文B", "source": "api/state.md", "heading": "Untitled"},
    ]
    out = build_system_message(DEFAULT_SYSTEM_PROMPT, contexts)
    assert "正文A" in out and "正文B" in out
    assert "来源: guide/intro.md" in out
    assert "小节: 概述" in out
    # Untitled 不显示
    assert "小节: Untitled" not in out
    # 链接以默认 wiki base url 拼接
    assert f"{DEFAULT_WIKI_BASE_URL}/guide/intro.md" in out
    assert f"{DEFAULT_WIKI_BASE_URL}/api/state.md" in out


def test_build_system_message_with_custom_wiki_base_url():
    contexts = [{"text": "x", "source": "foo.md", "heading": "H"}]
    out = build_system_message(
        DEFAULT_SYSTEM_PROMPT, contexts, wiki_base_url="https://wiki.example.com/docs"
    )
    assert "https://wiki.example.com/docs/foo.md" in out


def test_build_system_message_handles_missing_metadata_fields():
    """source/heading 为空或缺失时不应抛错，且不应输出空的 ``来源:``/``小节:`` 行。"""
    contexts = [
        {"text": "无元数据", "source": "", "heading": ""},
        {"text": "仅 source", "source": "only_src.md"},
    ]
    out = build_system_message(DEFAULT_SYSTEM_PROMPT, contexts)
    assert "无元数据" in out
    assert "仅 source" in out
    # 没有 source 时不应出现空 "来源: " 行；也不应生成空链接
    assert "来源: \n" not in out and "来源:  " not in out
    assert "链接: \n" not in out
    # 有 source 时应正常拼链接
    assert f"{DEFAULT_WIKI_BASE_URL}/only_src.md" in out


def test_build_system_message_treats_unknown_source_as_missing():
    """``(unknown)`` 占位符应被视为缺失，不输出 ``来源:`` 行也不生成链接。"""
    contexts = [{"text": "正文", "source": "(unknown)", "heading": "H"}]
    out = build_system_message(DEFAULT_SYSTEM_PROMPT, contexts)
    # 仅检查参考资料段（系统提示词本身含有 "来源"/"链接" 等关键字）
    ctx_section = out.split("【参考资料】", 1)[1]
    assert "正文" in ctx_section
    assert "(unknown)" not in ctx_section
    assert "来源:" not in ctx_section
    assert "链接:" not in ctx_section


def test_build_system_message_empty_base_url_skips_link():
    """``wiki_base_url`` 为空/空白时不应生成形如 ``/foo.md`` 的无效链接。"""
    contexts = [{"text": "x", "source": "foo.md", "heading": "H"}]
    out = build_system_message(DEFAULT_SYSTEM_PROMPT, contexts, wiki_base_url="   ")
    ctx_section = out.split("【参考资料】", 1)[1]
    assert "x" in ctx_section
    assert "来源: foo.md" in ctx_section
    # 不应出现链接行，也不应注入相对路径式的 "/foo.md"
    assert "链接:" not in ctx_section
    assert "/foo.md" not in ctx_section


def test_context_block_template_structure():
    # 模板必须包含 {contexts} 占位符，以便上层注入
    assert "{contexts}" in CONTEXT_BLOCK_TEMPLATE


def test_context_block_template_no_longer_promises_every_fragment_has_source():
    """重构后模板不再承诺"每个"片段都有来源（因为可能因 unknown 缺失）。"""
    assert "每个片段附带" not in CONTEXT_BLOCK_TEMPLATE


def test_fragment_separator_is_not_markdown_hr():
    """片段分隔符不应是 Markdown 水平线 ``---``（避免模型误解）。"""
    out = build_system_message(DEFAULT_SYSTEM_PROMPT, ["A", "B"])
    assert "───" in out
    # 确保不是 Markdown 水平线（三个减号）
    assert "\n---\n" not in out


# ─── _filter_empty_contexts 单元测试 ────────────────────────────

def test_filter_empty_contexts_removes_all_empty():
    items = [
        {"text": "", "source": "a.md"},
        "   ",
        {"text": "\n", "source": "b.md"},
    ]
    result = _filter_empty_contexts(items)
    assert result == []


def test_filter_empty_contexts_keeps_valid():
    items = [
        {"text": "hello", "source": "a.md"},
        "world",
        "",
    ]
    result = _filter_empty_contexts(items)
    assert len(result) == 2
    assert result[0] == {"text": "hello", "source": "a.md"}
    assert result[1] == "world"


def test_filter_empty_contexts_empty_list():
    assert _filter_empty_contexts([]) == []

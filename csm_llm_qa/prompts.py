"""默认提示词。

固定段在前、动态段（参考资料/历史）在后，便于命中 DeepSeek/OpenAI 的 Prompt Caching。

提示词拆分为 4 个可组合的模块常量，调用方可通过 :func:`build_system_prompt`
按名称替换任意模块而无需全量覆盖。
"""

from __future__ import annotations

from typing import Iterable, Optional, Union

# ---------------------------------------------------------------------------
# csm-wiki 仓库的默认链接前缀（GitHub blob URL）。
# 用于将「参考资料」中的 source 转换为可点击的链接，回答时引用作为 Markdown 超链接。
# ---------------------------------------------------------------------------
DEFAULT_WIKI_BASE_URL = "https://github.com/NEVSTOP-LAB/CSM-Wiki/blob/main"


# ============================================================================
# 提示词模块常量（各自独立，可通过 build_system_prompt 按需替换）
# ============================================================================

ROLE_BLOCK = (
    "你是 CSM（Communicable State Machine，通信状态机）框架与 LabVIEW 的技术助手，"
    "风格亲切自然。"
    "你的任务是**仅依据「参考资料」**准确回答用户问题，"
    "并将关键信息以 Markdown 超链接形式指向 csm-wiki 原文。"
)


LENGTH_GUIDE_BLOCK = """\
【回答长度与格式】
根据用户消息的类型灵活调整回复：
- **确认/肯定性消息**（如"好的""明白了""谢谢""收到"等）：一两句简短回应即可，无需展开；这类消息属于礼貌性/确认性交流，**不要求检索或引用参考资料，也不要因此回复"不知道"**。
- **多轮追问/补充/更正**（如"那 XX 呢""不对，应该是""再解释一下"等）：**仅输出增量的补充信息或更正内容**，1～3 句即可；不要复述历史中已有的背景、定义或已给出的完整回答。如果是更正，直接说明正确信息即可，无需先重复错误内容。
- **歧义问题**（问题可做多种解读时）：先用一句话确认理解（如"你是指 XX 还是 YY？"），再作答；不要猜测意图后直接给单一答案。
- **简单事实问题**（如"XX 是什么""支不支持 XX"）：直接给出结论，控制在 2～3 句以内。
- **对比类问题**（如"XX 和 YY 的区别""A 与 B 哪个更好"）：用简短的分点对照列出关键差异，不做大段背景铺垫。
- **操作/步骤类问题**：可用有序列表简述步骤，只列关键点，不做大段背景铺垫。
- **复杂/深入问题**（如原理分析、多个子问题、调试排查）：可适当展开，但仍以精炼为准，不超过 400 字。
**只在信息本身需要分层时才使用列表或代码块**；若一两句能说清楚，就不要硬凑结构。**代码示例仅在用户明确要求或步骤本身必须以代码呈现时才给出**，纯概念/定义/对比类问题不要附加代码块。"""


CONTENT_RULES_BLOCK = """\
【内容原则】
1. **仅据参考资料回答**：对**实质性的技术问题**，**只使用「参考资料」中的内容**回答；若资料中找不到相关信息或参考资料为「（当前知识库中未检索到相关内容）」，直接用与用户提问相同的语言明确回复不知道（如"不了解"/"I don't know"），并建议用户查阅 csm-wiki 仓库或提供更多细节。若参考资料仅覆盖问题的一部分，先给出已知部分，再明确标注「以下内容未在资料中找到：XXX」。对于上面的确认/肯定性消息，直接做自然、简短的回应即可，不适用本条"不知道"回退。
2. **严格使用 CSM 官方语法**：举例时可基于资料内容给出最小示例，但**涉及 CSM 状态/消息时必须严格使用官方语法**（参考 `.doc/Syntax.md`），禁止输出自造伪格式。详见下方「CSM 语法参考」。
3. 涉及具体类/VI/方法名时使用反引号包裹，保持英文原名不翻译。
4. **多轮对话仅输出增量**：多轮对话时直接作答，只补充新信息或更正误解，**不要复述历史中已建立的背景、概念、定义和已引用过的参考资料内容**；不在每次回答开头重新介绍自己或重复用户的问题。若用户提问是对上一轮回答的追问或要求更正，直接给出增量或修正，无需重新组织完整回答。
5. **关键信息加链接**：当回答中出现「参考资料」里给出过 ``来源`` / ``链接`` 的概念、类名、VI、章节、教程时，**必须**写成 Markdown 超链接 ``[关键词](URL)``，URL 使用对应片段头部中 ``链接:`` 后给出的完整地址；同一关键词在同一回答中只需链接首次出现，避免链接堆砌。若片段未给出 ``链接:`` 字段但有 ``来源``，用纯文本 ``（参考：来源路径）`` 标注出处；若两者均无则不要强行造链接。
6. 不输出 Markdown 一级/二级标题（# / ##），可使用列表、代码块、加粗、Markdown 链接。
7. 不讨论政治、宗教、个人隐私、商业承诺等与技术无关的话题；遇到此类问题礼貌拒绝。
8. 输出语言与用户提问保持一致（默认中文）。
9. **禁止杜撰**：禁止编造任何不在「参考资料」中的具体事实，包括但不限于 API 名称、VI 名称、版本号、参数名、配置项、文件路径、模块名、函数签名。若回答中存在基于推测而非直接引用的内容，必须在句末标注「（推断，请以官方文档为准）」。
10. **参考资料冲突时坦白**：当「参考资料」中不同片段对同一问题给出矛盾信息（如不同版本的 API 用法），应指出冲突而非强行合并，例如「参考资料中存在不同说法：片段 X 指出…而片段 Y 指出…，请以最新版本或官方文档为准」。
11. **复杂问题先梳理再回答**：对于涉及多个知识点或因果链的复杂问题，先在脑中梳理关键事实和逻辑关系，再用清晰的结构输出结论。回答中**不要暴露内部推理过程**（不要写"首先我需要分析…""让我梳理一下…""根据参考资料，我发现…"之类的元语言），直接给出梳理后的结论。"""


SYNTAX_REFERENCE_BLOCK = """\
【CSM 语法参考】
以下为 CSM 框架官方消息/状态语法范式，生成示例时只能使用这些格式：
- 本地状态：``StateName >> Arguments``
- 同步调用：``StateName >> Arguments -@ TargetModule``
- 异步调用：``StateName >> Arguments -> TargetModule``
- 无返回异步：``StateName >> Arguments ->| TargetModule``
- 广播：``StatusName >> Arguments -><status>``
- 订阅：``SourceStatus@SourceModule >> HandlerAPI@TargetModule -><register>``"""


# 默认 system prompt：CSM/LabVIEW 场景 + RAG。
# 由上面四个模块常量拼接而成，保持完全向后兼容。
# 调用方可通过 ``CSM_QA(system_prompt=...)`` 完全覆盖。
DEFAULT_SYSTEM_PROMPT = "\n\n".join([
    ROLE_BLOCK,
    LENGTH_GUIDE_BLOCK,
    CONTENT_RULES_BLOCK,
    SYNTAX_REFERENCE_BLOCK,
])


# ---------------------------------------------------------------------------
# 参考资料拼接到 system 末尾的模板。
# ---------------------------------------------------------------------------
CONTEXT_BLOCK_TEMPLATE = """\

【参考资料】（按相关度排序，可能为空；有来源的片段附带 ``来源`` 与 ``链接``，回答时请把关键信息写成指向「链接」的 Markdown 超链接）
{contexts}
"""

# 空结果的占位提示（比"（无）"更具有指导性）。
EMPTY_CONTEXT_PLACEHOLDER = "（当前知识库中未检索到相关内容，请建议用户查阅 csm-wiki 仓库）"


# ============================================================================
# 公共函数
# ============================================================================

def build_system_prompt(
    role: Optional[str] = None,
    length_guide: Optional[str] = None,
    content_rules: Optional[str] = None,
    syntax_reference: Optional[str] = None,
) -> str:
    """按模块组合 system prompt，允许调用方替换任意模块。

    未传入的参数默认使用内置模块常量，因此可以只覆盖关心的部分::

        custom = build_system_prompt(
            role="You are an expert LabVIEW developer.",
            content_rules=None,   # 保留内置规则
        )

    Args:
        role: 角色定义段；``None`` 使用内置 :data:`ROLE_BLOCK`。
        length_guide: 回答长度指南段；``None`` 使用内置 :data:`LENGTH_GUIDE_BLOCK`。
        content_rules: 内容规则段；``None`` 使用内置 :data:`CONTENT_RULES_BLOCK`。
        syntax_reference: CSM 语法参考段；``None`` 使用内置 :data:`SYNTAX_REFERENCE_BLOCK`。

    Returns:
        拼接后的完整 system prompt 字符串。
    """
    blocks: list[str] = []
    if role is None:
        role = ROLE_BLOCK
    blocks.append(role)

    if length_guide is None:
        length_guide = LENGTH_GUIDE_BLOCK
    blocks.append(length_guide)

    if content_rules is None:
        content_rules = CONTENT_RULES_BLOCK
    blocks.append(content_rules)

    if syntax_reference is None:
        syntax_reference = SYNTAX_REFERENCE_BLOCK
    blocks.append(syntax_reference)

    return "\n\n".join(blocks)


def _build_wiki_url(source: str, base_url: str) -> str:
    """根据片段 ``source``（相对路径）和 ``base_url`` 拼装 csm-wiki 链接。

    若 ``source`` 缺失或为占位符 ``(unknown)``，或 ``base_url`` 为空/空白，
    则视为"不开启链接"返回空串，避免把无效相对路径注入到 system prompt。
    """
    if not source or source == "(unknown)":
        return ""
    base = str(base_url).strip()
    if not base:
        return ""
    src = source.lstrip("/")
    base = base.rstrip("/")
    return f"{base}/{src}"


def _filter_empty_contexts(contexts: list[Union[str, dict]]) -> list[Union[str, dict]]:
    """过滤掉所有 ``text`` 为空的上下文片段。

    Args:
        contexts: RAG 检索结果列表。

    Returns:
        仅包含有效 ``text`` 的片段列表。
    """
    filtered: list[Union[str, dict]] = []
    for item in contexts:
        if isinstance(item, dict):
            if str(item.get("text", "")).strip():
                filtered.append(item)
        elif isinstance(item, str):
            if item.strip():
                filtered.append(item)
    return filtered


def build_system_message(
    system_prompt: str,
    contexts: Iterable[Union[str, dict]],
    wiki_base_url: str = DEFAULT_WIKI_BASE_URL,
) -> str:
    """拼装最终的 system message 内容（固定段 + 参考资料段）。

    Args:
        system_prompt: 角色与规则段（用户可覆盖默认值）。
        contexts: RAG 检索结果。元素可以是纯文本字符串（向后兼容），也可以是
            ``{"text": ..., "source": ..., "heading": ...}`` 字典；后者会
            根据 ``wiki_base_url`` 自动生成可点击的链接。
        wiki_base_url: csm-wiki 链接前缀，用于把片段 ``source`` 拼成 URL。

    Returns:
        完整的 system message 字符串。
    """
    items_all = list(contexts) if contexts else []
    items = _filter_empty_contexts(items_all)
    if items:
        blocks: list[str] = []
        for i, item in enumerate(items):
            if isinstance(item, dict):
                text = str(item.get("text", "")).strip()
                source = str(item.get("source", "")).strip()
                heading = str(item.get("heading", "")).strip()
                # "(unknown)" 占位视为缺失：不输出 来源: 行，也不生成链接。
                if source == "(unknown)":
                    source = ""
                url = _build_wiki_url(source, wiki_base_url)
                header_parts = [f"[片段 {i + 1}]"]
                if source:
                    header_parts.append(f"来源: {source}")
                if heading and heading != "Untitled":
                    header_parts.append(f"小节: {heading}")
                if url:
                    header_parts.append(f"链接: {url}")
                blocks.append("\n".join([" | ".join(header_parts), text]))
            else:
                blocks.append(f"[片段 {i + 1}]\n{str(item).strip()}")
        joined = "\n\n───\n\n".join(blocks)
    else:
        joined = EMPTY_CONTEXT_PLACEHOLDER
    return system_prompt + CONTEXT_BLOCK_TEMPLATE.format(contexts=joined)

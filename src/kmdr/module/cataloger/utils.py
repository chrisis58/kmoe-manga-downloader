import re

from kmdr.core import BookInfo


def extract_search_results(html: str) -> tuple[list[BookInfo], int]:
    """
    从搜索结果页面的 HTML 中提取书籍简要信息及分页信息。

    :param html: 搜索结果页面的 HTML 内容。
    :return: (书籍信息列表, 总页数)
    """
    # 提取总页数 (从 disp_divpage 函数调用中提取)
    # disp_divpage( div_id, str_searchtext, num_total, ... )
    page_match = re.search(r'disp_divpage\(\s*"[^"]*",\s*"[^"]*",\s*"(\d+)"', html)
    total_pages = int(page_match.group(1)) if page_match else 1

    pattern = re.compile(
        r"disp_divinfo\(\s*[^,]+,\s*"
        r'"([^"]*)",\s*'  # 1: book_url
        r'"([^"]*)",\s*'  # 2: cover_url
        r'"[^"]*",\s*'  # border_color
        r'"([^"]*)",\s*'  # 3: tag1 (语言/状态等)
        r'"([^"]*)",\s*'  # 4: tag2
        r'"([^"]*)",\s*'  # 5: tag3
        r'"([^"]*)",\s*'  # 6: tag4
        r'"([^"]*)",\s*'  # 7: book_score
        r'"([^"]*)",\s*'  # 8: book_name
        r'"([^"]*)",\s*'  # 9: book_author
        r'"([^"]*)",\s*'  # 10: word_status
        r'"([^"]*)"\s*\);'  # 11: word_update
    )

    # disp_divinfo 中 4 个 tag 参数的名称，与 JS 中的展示逻辑对应
    # 参数值为空字符串时表示展示该 tag，非空时隐藏
    _TAG_NAMES = ("日語", "英文", "完結", "停更")

    results = []
    for match in pattern.finditer(html):
        book_url = match.group(1)
        book_name_raw = match.group(8)
        book_name = re.sub(r"<[^>]+>", "", book_name_raw)  # 移除可能存在的 <b> 标签
        author = match.group(9)
        status_text = f"{match.group(10)} {match.group(11)}".strip()

        # 提取标签：参数值为空 → 展示该 tag
        tags = tuple(
            _TAG_NAMES[i] for i in range(4) if match.group(i + 3) == ""
        )

        # 适应不同类型的 ID (比如纯数字或包含字符)
        id_match = re.search(r"/c/([a-zA-Z0-9]+)\.htm", book_url)
        book_id = id_match.group(1) if id_match else ""

        results.append(
            BookInfo(
                id=book_id,
                name=book_name,
                url=book_url,
                author=author,
                status=status_text,
                last_update=match.group(11),
                tags=tags,
            )
        )

    return results, total_pages

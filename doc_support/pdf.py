"""PDF 文档构建钩子.

设置封面与文档信息，整理图文和表格，并保留合并文档中的链接目标。

核心功能：
  - on_config: 设置 PDF 封面和文档信息
  - on_page_content: 保留链接目标并标记表格与截图的打印样式

使用示例：
  python -m mkdocs build --strict -f mkdocs-pdf.yml
"""

import tomllib
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, Tag
from mkdocs.config.defaults import MkDocsConfig
from mkdocs.plugins import event_priority


@event_priority(100)
def on_config(config: MkDocsConfig) -> MkDocsConfig:
    """使用项目元数据设置 PDF 封面和文档信息."""
    project_file = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with project_file.open("rb") as stream:
        version = tomllib.load(stream)["project"]["version"]

    pdf_config = config.plugins["to-pdf"].config
    pdf_config["cover_title"] = f"{config.site_name} 文档"
    pdf_config["cover_subtitle"] = f"v{version}"
    config.extra["pdf_project_name"] = config.site_name
    config.extra["pdf_description"] = config.site_description
    site_url = urlsplit(config.site_url)
    config.extra["pdf_documentation_url"] = f"{site_url.scheme}://{site_url.netloc}/"
    return config


def on_page_content(html: str, **_kwargs: object) -> str:
    """保留自定义锚点，并为表格与图文设置打印样式."""
    soup = BeautifulSoup(html, "html.parser")

    for anchor in soup.find_all("a", id=True):
        # 旧式 name 属性会覆盖 PDF 转换时重写的 ID。
        anchor.attrs.pop("name", None)

    for paragraph in soup.find_all("p"):
        if paragraph.get_text(strip=True):
            continue

        if paragraph.find("a", id=True) is not None:
            paragraph.unwrap()

    for table in soup.find_all("table"):
        headings = [cell.get_text(strip=True) for cell in table.select("thead th")]
        if headings == ["参数", "类型", "必需", "默认值", "说明"]:
            _add_class(table, "pdf-parameters")
        elif headings == ["环境变量", "类型", "默认值", "说明"]:
            _add_class(table, "pdf-environment")

    for picture in soup.find_all("img", src=True):
        path = urlsplit(str(picture["src"])).path
        if "/assets/images/" not in path or path.endswith("/architecture.png"):
            continue

        _add_class(picture, "pdf-screenshot")
        paragraph = picture.parent
        if not isinstance(paragraph, Tag) or paragraph.name != "p":
            continue
        if paragraph.get_text(strip=True):
            continue

        _add_class(paragraph, "pdf-figure")
        introduction = paragraph.find_previous_sibling()
        if (
            isinstance(paragraph.parent, Tag)
            and paragraph.parent.name == "li"
            and isinstance(introduction, Tag)
            and introduction.name == "p"
        ):
            group = soup.new_tag("div", attrs={"class": "pdf-illustrated-step"})
            introduction.insert_before(group)
            group.append(introduction)
            group.append(paragraph)

    _group_illustrated_sections(soup)
    return str(soup)


def _add_class(tag: Tag, name: str) -> None:
    """保留元素已有的 CSS 类，并添加打印样式类."""
    classes = tag.get_attribute_list("class")
    if name not in classes:
        classes.append(name)
    tag["class"] = classes


def _group_illustrated_sections(soup: BeautifulSoup) -> None:
    """将截图的小节说明、操作标题与首个步骤保持在同页."""
    headings = {"h2", "h3", "h4", "h5", "h6"}
    for figure in soup.select(".pdf-figure"):
        if figure.find_parent("li") is not None:
            continue

        content = [figure]
        previous = figure.find_previous_sibling()
        while isinstance(previous, Tag):
            if previous.find("img") is not None:
                break
            content.insert(0, previous)
            if previous.name in headings:
                if sum(len(node.get_text(strip=True)) for node in content) < 450:
                    group = soup.new_tag("div", attrs={"class": "pdf-illustrated-section"})
                    previous.insert_before(group)
                    for node in content:
                        group.append(node)
                break
            if previous.name not in {"p", "ul"}:
                break
            previous = previous.find_previous_sibling()

    for ordered in soup.find_all("ol"):
        items = ordered.find_all("li", recursive=False)
        if not items or items[0].select_one(".pdf-illustrated-step") is None:
            continue

        titles = []
        previous = ordered.find_previous_sibling()
        while isinstance(previous, Tag) and previous.name in headings:
            titles.insert(0, previous)
            previous = previous.find_previous_sibling()
        if not titles:
            continue

        group = soup.new_tag("div", attrs={"class": "pdf-illustrated-section"})
        titles[0].insert_before(group)
        for title in titles:
            group.append(title)
        group.append(ordered)
        if len(items) > 1:
            remaining = soup.new_tag("ol")
            remaining.attrs = {key: value for key, value in ordered.attrs.items() if key != "id"}
            start = ordered.get("start")
            continued_start = int(start) + 1 if isinstance(start, str) else 2
            remaining["start"] = str(continued_start)
            remaining["style"] = f"counter-reset: list-item {continued_start - 1};"
            for item in items[1:]:
                remaining.append(item)
            group.insert_after(remaining)

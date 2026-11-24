import json
import re
from typing import Dict, Any, List
from src.core.entities import CanvasBlock


def _to_css_prop(key: str) -> str:
    return key.strip().replace("_", "-").lower()


def _sanitize_css_val(val: Any) -> str:
    return str(val).replace(";", "").replace("<", "").replace(">", "").strip()


class QuartoSourceTransformer:
    NON_CSS_KEYS = {"theme", "class", "classes", "variant"}

    def _build_css(self, blocks: List[CanvasBlock], metadata: Dict[str, Any], template: Dict[str, Any]) -> str:
        theme_cfg = template.get("theme") if isinstance(template, dict) else None
        if not isinstance(theme_cfg, dict):
            theme_cfg = {}

        primary = _sanitize_css_val(theme_cfg.get("primary_color", "#4338ca"))
        bg = _sanitize_css_val(theme_cfg.get("background_color", "#f8fafc"))
        text = _sanitize_css_val(theme_cfg.get("text_color", "#1e293b"))
        font = _sanitize_css_val(theme_cfg.get("font_family", "'Georgia', 'Times New Roman', serif"))
        max_width = _sanitize_css_val(theme_cfg.get("max_width", "860px"))

        lines = [
            ":root {",
            f"  --q-primary: {primary};",
            f"  --q-bg: {bg};",
            f"  --q-text: {text};",
            f"  --q-font: {font};",
            f"  --q-max-width: {max_width};",
            "}",
        ]

        for idx, b in enumerate(sorted(blocks, key=lambda x: x.order_index)):
            style_cfg = b.style_config or {}
            if not isinstance(style_cfg, dict) or not style_cfg:
                continue
            decls = []
            for k, v in style_cfg.items():
                if k.lower() in self.NON_CSS_KEYS or v is None:
                    continue
                prop = _to_css_prop(k)
                if re.match(r"^[a-z-]+$", prop):
                    decls.append(f"  {prop}: {_sanitize_css_val(v)};")
            if decls:
                lines.append(f".quarto-block-{idx} {{")
                lines.extend(decls)
                lines.append("}")

        return "\n".join(lines) + "\n"

    def transform(
        self,
        page_id: str,
        slug: str,
        content_type: str,
        blocks: List[CanvasBlock],
        metadata: Dict[str, Any],
        template: Dict[str, Any],
    ) -> Dict[str, str]:
        metadata = metadata or {}
        template = template or {}
        theme_name = metadata.get("theme", "cosmo")
        title = metadata.get("title", slug)

        frontmatter = [
            "---",
            f"title: {json.dumps(title)}",
            "format:",
            "  html:",
            f"    theme: {theme_name}",
            "    css: styles.css",
            f"page-id: {json.dumps(page_id)}",
        ]
        for k, v in metadata.items():
            if k in {"title", "theme"}:
                continue
            frontmatter.append(f"{k}: {json.dumps(v)}")
        frontmatter.append("---\n")

        sorted_blocks = sorted(blocks, key=lambda x: x.order_index)
        body = []
        serialized_blocks = []

        for idx, b in enumerate(sorted_blocks):
            b_type = b.block_type.upper()
            payload = b.content_payload or {}
            if b_type == "HEADING":
                level = payload.get("level", 1)
                body.append(f"{'#' * level} {payload.get('text', '')}\n")
            elif b_type == "PARAGRAPH":
                body.append(f"{payload.get('text', '')}\n")
            elif b_type == "CODE":
                body.append(f"```{payload.get('language', 'python')}\n{payload.get('code', '')}\n```\n")
            elif b_type == "IMAGE":
                body.append(f"![{payload.get('caption', '')}]({payload.get('url', '')})\n")
            elif b_type == "QUOTE":
                quote_line = f"> {payload.get('text', '')}"
                if payload.get("author"):
                    quote_line += f"\n> — *{payload['author']}*"
                body.append(quote_line + "\n")
            elif b_type == "SECTION":
                sec_title = payload.get("title", "")
                sec_body = payload.get("text", "")
                section_md = f"\n---\n### {sec_title}\n"
                if sec_body:
                    section_md += f"\n{sec_body}\n"
                body.append(section_md)

            serialized_blocks.append(
                {
                    "index": idx,
                    "block_id": b.block_id,
                    "block_type": b_type,
                    "order_index": b.order_index,
                    "content_payload": payload,
                    "style_config": b.style_config or {},
                }
            )

        content = "\n".join(frontmatter) + "\n".join(body)
        styles_css = self._build_css(sorted_blocks, metadata, template)
        render_spec = {
            "page_id": page_id,
            "slug": slug,
            "content_type": content_type,
            "metadata": metadata,
            "template": template,
            "blocks": serialized_blocks,
        }

        return {
            "index.qmd": content,
            "_quarto.yml": "project:\n  type: website\n  output-dir: _site\n",
            "styles.css": styles_css,
            "render_spec.json": json.dumps(render_spec, ensure_ascii=False, indent=2),
        }

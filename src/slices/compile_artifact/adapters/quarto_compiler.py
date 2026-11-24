import html
import json
import re
from typing import Any, Dict, List, Optional
from src.core.entities import SourceBundle


THEME_PRESETS: Dict[str, Dict[str, str]] = {
    "cosmo": {
        "bg": "#f8fafc",
        "surface": "#ffffff",
        "text": "#1e293b",
        "muted": "#64748b",
        "primary": "#2780e3",
        "border": "#e2e8f0",
        "font": "'Segoe UI', Roboto, -apple-system, BlinkMacSystemFont, sans-serif",
    },
    "darkly": {
        "bg": "#111827",
        "surface": "#1f2937",
        "text": "#f3f4f6",
        "muted": "#9ca3af",
        "primary": "#38bdf8",
        "border": "#374151",
        "font": "'Segoe UI', Roboto, -apple-system, sans-serif",
    },
    "flatly": {
        "bg": "#f4f6f9",
        "surface": "#ffffff",
        "text": "#2c3e50",
        "muted": "#7b8a8b",
        "primary": "#18bc9c",
        "border": "#dce4ec",
        "font": "'Lato', 'Segoe UI', sans-serif",
    },
    "journal": {
        "bg": "#fffdf9",
        "surface": "#ffffff",
        "text": "#222222",
        "muted": "#666666",
        "primary": "#eb6864",
        "border": "#e5e5e5",
        "font": "'Georgia', 'Times New Roman', serif",
    },
    "litera": {
        "bg": "#ffffff",
        "surface": "#ffffff",
        "text": "#212529",
        "muted": "#6c757d",
        "primary": "#4582ec",
        "border": "#dee2e6",
        "font": "'Georgia', serif",
    },
    "solar": {
        "bg": "#fdf6e3",
        "surface": "#eee8d5",
        "text": "#073642",
        "muted": "#586e75",
        "primary": "#b58900",
        "border": "#d6ceb5",
        "font": "'Georgia', serif",
    },
}

NON_CSS_KEYS = {"theme", "class", "classes", "variant"}


def _slugify_anchor(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return slug or "section"


def _build_inline_style(style_config: Optional[Dict[str, Any]]) -> str:
    if not isinstance(style_config, dict) or not style_config:
        return ""
    parts = []
    for k, v in style_config.items():
        if k.lower() in NON_CSS_KEYS or v is None:
            continue
        prop = k.strip().replace("_", "-").lower()
        if re.match(r"^[a-z-]+$", prop):
            clean_val = str(v).replace(";", "").replace('"', "'").replace("<", "").replace(">", "").strip()
            parts.append(f"{prop}: {clean_val}")
    return "; ".join(parts)


class QuartoCompilerAdapter:
    def _read_bundle_files(self, bundle: SourceBundle) -> Dict[str, str]:
        contents: Dict[str, str] = {}
        for f in bundle.files:
            try:
                with open(f, "r", encoding="utf-8") as sf:
                    text = sf.read()
                if f.endswith("render_spec.json"):
                    contents["render_spec.json"] = text
                elif f.endswith("styles.css"):
                    contents["styles.css"] = text
                elif f.endswith("index.qmd"):
                    contents["index.qmd"] = text
            except Exception:
                pass
        return contents

    def _resolve_theme(self, metadata: Dict[str, Any], template: Dict[str, Any]) -> Dict[str, str]:
        preset_name = str(metadata.get("theme", "cosmo")).lower()
        base = dict(THEME_PRESETS.get(preset_name, THEME_PRESETS["cosmo"]))

        theme_cfg = template.get("theme") if isinstance(template, dict) else None
        if isinstance(theme_cfg, dict):
            if theme_cfg.get("primary_color"):
                base["primary"] = str(theme_cfg["primary_color"])
            if theme_cfg.get("background_color"):
                base["bg"] = str(theme_cfg["background_color"])
            if theme_cfg.get("card_background"):
                base["surface"] = str(theme_cfg["card_background"])
            if theme_cfg.get("text_color"):
                base["text"] = str(theme_cfg["text_color"])
            if theme_cfg.get("font_family"):
                base["font"] = str(theme_cfg["font_family"])
            if theme_cfg.get("max_width"):
                base["max_width"] = str(theme_cfg["max_width"])

        base.setdefault("max_width", "860px")
        base["name"] = preset_name
        return base

    def _render_blocks(self, blocks: List[Dict[str, Any]]) -> tuple[str, List[tuple[int, str, str]]]:
        rendered: List[str] = []
        toc_entries: List[tuple[int, str, str]] = []

        for idx, block in enumerate(blocks):
            b_type = str(block.get("block_type", "PARAGRAPH")).upper()
            payload = block.get("content_payload") or {}
            style_cfg = block.get("style_config") or {}
            inline_style = _build_inline_style(style_cfg)
            style_attr = f' style="{html.escape(inline_style)}"' if inline_style else ""
            cls = f"quarto-block quarto-block-{idx}"

            if b_type == "HEADING":
                level = payload.get("level", 1)
                try:
                    level = max(1, min(6, int(level)))
                except (TypeError, ValueError):
                    level = 1
                text = str(payload.get("text", ""))
                anchor = _slugify_anchor(text)
                toc_entries.append((level, text, anchor))
                rendered.append(
                    f'<h{level} id="{html.escape(anchor)}" class="{cls}"{style_attr}>{html.escape(text)}</h{level}>'
                )

            elif b_type == "PARAGRAPH":
                text = str(payload.get("text", ""))
                rendered.append(f'<p class="{cls}"{style_attr}>{html.escape(text)}</p>')

            elif b_type == "CODE":
                lang = str(payload.get("language", "text"))
                code = str(payload.get("code", ""))
                code_theme = str(style_cfg.get("theme", "dark")).lower()
                is_light = code_theme in {"light", "github", "solarized-light"}
                theme_cls = "code-light" if is_light else "code-dark"
                rendered.append(
                    f'<div class="code-card {theme_cls} {cls}"{style_attr}>'
                    f'<div class="code-header"><span class="code-lang">{html.escape(lang)}</span></div>'
                    f'<pre><code class="language-{html.escape(lang)}">{html.escape(code)}</code></pre>'
                    f"</div>"
                )

            elif b_type == "IMAGE":
                url = str(payload.get("url", ""))
                caption = str(payload.get("caption", "Imagen"))
                rendered.append(
                    f'<figure class="q-figure {cls}"{style_attr}>'
                    f'<img src="{html.escape(url)}" alt="{html.escape(caption)}" />'
                    f'<figcaption>{html.escape(caption)}</figcaption>'
                    f"</figure>"
                )

            elif b_type == "QUOTE":
                text = str(payload.get("text", ""))
                author = payload.get("author")
                author_html = f"<footer>— {html.escape(str(author))}</footer>" if author else ""
                rendered.append(
                    f'<blockquote class="q-quote {cls}"{style_attr}>'
                    f"<p>{html.escape(text)}</p>{author_html}"
                    f"</blockquote>"
                )

            elif b_type == "SECTION":
                sec_title = str(payload.get("title", ""))
                sec_text = str(payload.get("text", ""))
                anchor = _slugify_anchor(sec_title) if sec_title else f"section-{idx}"
                if sec_title:
                    toc_entries.append((2, sec_title, anchor))
                inner = f'<h3 id="{html.escape(anchor)}">{html.escape(sec_title)}</h3>' if sec_title else ""
                if sec_text:
                    inner += f"<p>{html.escape(sec_text)}</p>"
                rendered.append(f'<section class="q-section {cls}"{style_attr}>{inner}</section>')

        return "\n        ".join(rendered), toc_entries

    def compile(self, bundle: SourceBundle) -> bytes:
        files = self._read_bundle_files(bundle)
        qmd_source = files.get("index.qmd", "")
        custom_css = files.get("styles.css", "")

        spec: Dict[str, Any] = {}
        if "render_spec.json" in files:
            try:
                spec = json.loads(files["render_spec.json"])
            except Exception:
                spec = {}

        if not spec:
            html_fallback = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Quarto Doc - {html.escape(bundle.page_id)}</title>
    <style>
        body {{ font-family: 'Georgia', serif; line-height: 1.8; max-width: 820px; margin: 40px auto; padding: 0 20px; color: #1a202c; }}
        .header {{ border-bottom: 1px solid #cbd5e1; margin-bottom: 2rem; }}
        .badge {{ background-color: #4338ca; color: white; padding: 2px 6px; border-radius: 4px; font-family: sans-serif; font-size: 0.8rem; }}
    </style>
</head>
<body>
    <div class="header">
        <span class="badge">Quarto Scientific/Technical</span>
        <h2>{html.escape(bundle.page_id)}</h2>
    </div>
    <div>
        <pre>{html.escape(qmd_source)}</pre>
    </div>
</body>
</html>
"""
            return html_fallback.encode("utf-8")

        metadata = spec.get("metadata") or {}
        template = spec.get("template") or {}
        blocks = spec.get("blocks") or []
        slug = str(spec.get("slug") or bundle.page_id)
        title = str(metadata.get("title") or slug)

        theme = self._resolve_theme(metadata, template)
        blocks_html, toc_entries = self._render_blocks(blocks)

        regions = (template.get("layout_structure") or {}).get("regions", []) if isinstance(template, dict) else []
        show_toc = bool(metadata.get("toc")) or ("toc" in regions)
        toc_html = ""
        if show_toc and toc_entries:
            items = "\n".join(
                f'<li class="toc-level-{lvl}"><a href="#{html.escape(anchor)}">{html.escape(txt)}</a></li>'
                for lvl, txt, anchor in toc_entries
            )
            toc_html = f"""
            <nav class="toc-card" aria-label="Tabla de contenidos">
                <div class="toc-title">Contenido</div>
                <ul>{items}</ul>
            </nav>"""

        meta_pills = [f'<span class="meta-pill">Motor: Quarto ({html.escape(theme["name"])})</span>']
        if metadata.get("author"):
            meta_pills.append(f'<span class="meta-pill">Autor: {html.escape(str(metadata["author"]))}</span>')
        meta_pills.append(f'<span class="meta-pill">ID: {html.escape(bundle.page_id)}</span>')
        meta_html = "\n            ".join(meta_pills)

        compiled_html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title)} · Quarto</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            padding: 32px 16px 64px;
            background-color: {theme["bg"]};
            color: {theme["text"]};
            font-family: {theme["font"]};
            line-height: 1.75;
        }}
        .page-shell {{
            max-width: {theme["max_width"]};
            margin: 0 auto;
            background-color: {theme["surface"]};
            border: 1px solid {theme["border"]};
            border-radius: 14px;
            padding: 40px 44px;
            box-shadow: 0 12px 30px rgba(15, 23, 42, 0.08);
        }}
        .doc-header {{
            border-bottom: 2px solid {theme["border"]};
            padding-bottom: 20px;
            margin-bottom: 28px;
        }}
        .badge {{
            display: inline-block;
            background-color: {theme["primary"]};
            color: #ffffff;
            padding: 4px 10px;
            border-radius: 999px;
            font-family: system-ui, -apple-system, sans-serif;
            font-size: 0.78rem;
            font-weight: 600;
            letter-spacing: 0.02em;
            margin-bottom: 12px;
        }}
        .doc-subtitle {{
            margin: 0 0 14px;
            font-size: 0.95rem;
            color: {theme["muted"]};
            font-family: system-ui, -apple-system, sans-serif;
        }}
        .meta-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }}
        .meta-pill {{
            background: rgba(99, 102, 241, 0.08);
            border: 1px solid {theme["border"]};
            color: {theme["muted"]};
            padding: 3px 10px;
            border-radius: 6px;
            font-family: system-ui, -apple-system, sans-serif;
            font-size: 0.8rem;
        }}
        .toc-card {{
            background: rgba(99, 102, 241, 0.05);
            border: 1px solid {theme["border"]};
            border-left: 4px solid {theme["primary"]};
            border-radius: 8px;
            padding: 14px 18px;
            margin-bottom: 28px;
            font-family: system-ui, -apple-system, sans-serif;
        }}
        .toc-title {{
            font-weight: 700;
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: {theme["primary"]};
            margin-bottom: 8px;
        }}
        .toc-card ul {{
            margin: 0;
            padding-left: 18px;
        }}
        .toc-card li {{
            margin: 4px 0;
        }}
        .toc-card a {{
            color: {theme["text"]};
            text-decoration: none;
        }}
        .toc-card a:hover {{
            color: {theme["primary"]};
            text-decoration: underline;
        }}
        .toc-level-2 {{ margin-left: 12px; }}
        .toc-level-3 {{ margin-left: 24px; }}
        .quarto-block {{
            margin-bottom: 1.25rem;
        }}
        .code-card {{
            border-radius: 10px;
            overflow: hidden;
            border: 1px solid {theme["border"]};
            margin: 1.5rem 0;
        }}
        .code-dark {{
            background: #0f172a;
            color: #e2e8f0;
        }}
        .code-light {{
            background: #f8fafc;
            color: #1e293b;
        }}
        .code-header {{
            padding: 8px 14px;
            font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            background: rgba(148, 163, 184, 0.14);
            border-bottom: 1px solid rgba(148, 163, 184, 0.2);
        }}
        .code-card pre {{
            margin: 0;
            padding: 16px;
            overflow-x: auto;
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
            font-size: 0.92rem;
            line-height: 1.55;
        }}
        .q-quote {{
            margin: 1.5rem 0;
            padding: 12px 18px;
            border-left: 4px solid {theme["primary"]};
            background: rgba(99, 102, 241, 0.05);
            border-radius: 0 8px 8px 0;
        }}
        .q-quote p {{ margin: 0; }}
        .q-quote footer {{
            margin-top: 8px;
            font-size: 0.9rem;
            color: {theme["muted"]};
        }}
        .q-figure {{
            margin: 1.5rem 0;
            text-align: center;
        }}
        .q-figure img {{
            max-width: 100%;
            border-radius: 8px;
            border: 1px solid {theme["border"]};
        }}
        .q-figure figcaption {{
            margin-top: 8px;
            font-size: 0.88rem;
            color: {theme["muted"]};
        }}
        .q-section {{
            padding-top: 12px;
            border-top: 1px solid {theme["border"]};
        }}
        .doc-footer {{
            margin-top: 40px;
            padding-top: 18px;
            border-top: 1px solid {theme["border"]};
            font-family: system-ui, -apple-system, sans-serif;
            font-size: 0.82rem;
            color: {theme["muted"]};
        }}
        details.qmd-source {{
            margin-top: 12px;
        }}
        details.qmd-source summary {{
            cursor: pointer;
            color: {theme["primary"]};
            font-weight: 600;
        }}
        details.qmd-source pre {{
            margin-top: 10px;
            padding: 14px;
            background: #0f172a;
            color: #cbd5e1;
            border-radius: 8px;
            overflow-x: auto;
            font-size: 0.82rem;
        }}
        {custom_css}
    </style>
</head>
<body>
    <article class="page-shell">
        <header class="doc-header">
            <span class="badge">Quarto Scientific/Technical</span>
            <p class="doc-subtitle">{html.escape(slug)}</p>
            <div class="meta-row">
                {meta_html}
            </div>
        </header>
        {toc_html}
        <main>
            {blocks_html}
        </main>
        <footer class="doc-footer">
            <div>Compilado por <strong>static_pages_generator</strong> · Motor Quarto</div>
            <details class="qmd-source">
                <summary>Ver fuente index.qmd generado</summary>
                <pre>{html.escape(qmd_source)}</pre>
            </details>
        </footer>
    </article>
</body>
</html>
"""
        return compiled_html.encode("utf-8")

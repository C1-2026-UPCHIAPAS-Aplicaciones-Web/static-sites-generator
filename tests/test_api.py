import os
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

from src.main import app
from src.config import STORAGE_DIR, SQLITE_DB_PATH
from src.shared.database import init_db

class TestStaticPagesGeneratorApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db(SQLITE_DB_PATH)
        cls.client = TestClient(app)

    def test_01_health_check(self):
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"status": "ok", "service": "static_pages_generator"})

    def test_02_create_page_sync_astro(self):
        payload = {
            "page_id": "test-astro-landing",
            "document_id": "0192a3b5-1122-7334-8445-556677889900",
            "slug": "landing-bienvenida",
            "content_type": "LANDING_GENERIC",
            "engine_hint": "astro",
            "frozen_template": {
                "layout_structure": {"regions": ["header", "main_canvas", "footer"]},
                "engine": "astro"
            },
            "metadata_values": {
                "title": "Página de Inicio",
                "author": "Equipo CMS"
            },
            "canvas_blocks": [
                {
                    "block_id": "blk-1",
                    "block_type": "HEADING",
                    "order_index": 1,
                    "content_payload": {"level": 1, "text": "Bienvenido al CMS"}
                },
                {
                    "block_id": "blk-2",
                    "block_type": "PARAGRAPH",
                    "order_index": 2,
                    "content_payload": {"text": "Este es un artefacto estático compilado con arquitectura hexagonal."}
                },
                {
                    "block_id": "blk-3",
                    "block_type": "CODE",
                    "order_index": 3,
                    "content_payload": {"language": "python", "code": "def hello():\n    return 'world'"}
                }
            ],
            "async_mode": False
        }

        res = self.client.post("/api/v1/pages", json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["page_id"], "test-astro-landing")
        self.assertEqual(data["status"], "COMPLETED")
        self.assertEqual(data["engine"], "astro")
        self.assertIsNotNone(data["checksum_sha256"])
        self.assertEqual(len(data["checksum_sha256"]), 64)

        # Verify content endpoint
        content_res = self.client.get("/api/v1/pages/test-astro-landing/content")
        self.assertEqual(content_res.status_code, 200)
        self.assertIn("text/html", content_res.headers["content-type"])
        html_text = content_res.text
        self.assertIn("Astro Page - test-astro-landing", html_text)
        self.assertIn("Bienvenido al CMS", html_text)

    def test_03_create_page_hugo_and_quarto(self):
        for eng in ["hugo", "quarto"]:
            payload = {
                "document_id": f"doc-{eng}",
                "slug": f"doc-post-{eng}",
                "content_type": "DEV_BLOG",
                "engine_hint": eng,
                "canvas_blocks": [
                    {
                        "block_type": "HEADING",
                        "order_index": 1,
                        "content_payload": {"level": 2, "text": f"Título {eng}"}
                    }
                ]
            }
            res = self.client.post("/api/v1/pages", json=payload)
            self.assertEqual(res.status_code, 201)
            data = res.json()
            self.assertEqual(data["engine"], eng)
            self.assertEqual(len(data["checksum_sha256"]), 64)

            # Check build info
            build_res = self.client.get(f"/api/v1/builds/{data['build_id']}")
            self.assertEqual(build_res.status_code, 200)
            self.assertEqual(build_res.json()["status"], "COMPLETED")

    def test_04_integrity_check_and_auto_rebuild_on_loss(self):
        page_id = "test-rebuild-page"
        payload = {
            "page_id": page_id,
            "document_id": "doc-rebuild-123",
            "slug": "pagina-resiliente",
            "content_type": "DEV_BLOG",
            "engine_hint": "astro",
            "canvas_blocks": [
                {
                    "block_type": "HEADING",
                    "order_index": 1,
                    "content_payload": {"level": 1, "text": "Página Resiliente a Pérdidas"}
                }
            ]
        }
        create_res = self.client.post("/api/v1/pages", json=payload)
        self.assertEqual(create_res.status_code, 201)
        original_sha = create_res.json()["checksum_sha256"]

        # 1. Verify integrity is initially HEALTHY
        verify_res = self.client.get(f"/api/v1/pages/{page_id}/verify?auto_repair=false")
        self.assertEqual(verify_res.status_code, 200)
        self.assertEqual(verify_res.json()["status"], "HEALTHY")
        self.assertEqual(verify_res.json()["checksum_sha256"], original_sha)

        # 2. SIMULATE ARTIFACT LOSS: Delete physical HTML file from dist/
        artifact_file = STORAGE_DIR / page_id / "index.html"
        self.assertTrue(artifact_file.is_file())
        artifact_file.unlink()
        self.assertFalse(artifact_file.is_file())

        # 3. Verify that the system detects loss and AUTO-REBUILDS from stored snapshot
        repair_res = self.client.get(f"/api/v1/pages/{page_id}/verify?auto_repair=true")
        self.assertEqual(repair_res.status_code, 200)
        repair_data = repair_res.json()
        self.assertEqual(repair_data["status"], "HEALTHY")
        self.assertTrue(repair_data["auto_repaired"])
        self.assertIn("Physical file was missing from storage; auto-rebuild succeeded.", repair_data["message"])

        # 4. Check that file is back on disk and readable via /content
        self.assertTrue(artifact_file.is_file())
        content_res = self.client.get(f"/api/v1/pages/{page_id}/content")
        self.assertEqual(content_res.status_code, 200)
        self.assertIn("Página Resiliente a Pérdidas", content_res.text)

    def test_05_quarto_renders_styled_html(self):
        page_id = "test-quarto-styled"
        payload = {
            "page_id": page_id,
            "document_id": "doc-quarto-styled-1",
            "slug": "quarto-estilizado-test",
            "content_type": "DEV_DOC",
            "engine_hint": "quarto",
            "metadata_values": {
                "title": "Guía Quarto Estilizada",
                "author": "Equipo CMS",
                "theme": "cosmo",
                "toc": True
            },
            "frozen_template": {
                "theme": {
                    "primary_color": "#4338ca",
                    "background_color": "#f8fafc"
                },
                "layout_structure": {"regions": ["header", "toc", "main_canvas", "footer"]}
            },
            "canvas_blocks": [
                {
                    "block_type": "HEADING",
                    "order_index": 1,
                    "content_payload": {"level": 1, "text": "Título Principal"},
                    "style_config": {"color": "#312e81", "text_align": "center"}
                },
                {
                    "block_type": "PARAGRAPH",
                    "order_index": 2,
                    "content_payload": {"text": "Párrafo con fondo personalizado."},
                    "style_config": {"background_color": "#eef2ff", "padding": "16px"}
                },
                {
                    "block_type": "CODE",
                    "order_index": 3,
                    "content_payload": {"language": "python", "code": "print('hola quarto')"},
                    "style_config": {"theme": "dark", "border_radius": "8px"}
                },
                {
                    "block_type": "QUOTE",
                    "order_index": 4,
                    "content_payload": {"text": "Cita destacada", "author": "Autor"},
                    "style_config": {"border_left": "4px solid #4338ca"}
                }
            ]
        }

        res = self.client.post("/api/v1/pages", json=payload)
        self.assertEqual(res.status_code, 201)
        content_res = self.client.get(f"/api/v1/pages/{page_id}/content")
        self.assertEqual(content_res.status_code, 200)
        html_text = content_res.text

        self.assertIn("<h1", html_text)
        self.assertIn("Título Principal", html_text)
        self.assertIn("color: #312e81", html_text)
        self.assertIn("background-color: #eef2ff", html_text)
        self.assertIn("language-python", html_text)
        self.assertIn("<blockquote", html_text)
        self.assertIn("toc-card", html_text)

if __name__ == "__main__":
    unittest.main()

"""Shared pytest fixtures: creates minimal fixture files used across tests."""

import os
import pytest


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _make_fixture_pdf(path: str) -> None:
    """Create a minimal, valid PDF at *path* using reportlab."""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(path, pagesize=letter)
    c.setFont("Helvetica", 12)
    c.drawString(72, 720, "CIS Security Requirements Fixture")
    c.drawString(72, 700, "1. All data at rest must be encrypted using AES-256.")
    c.drawString(72, 680, "2. Users must authenticate using multi-factor authentication.")
    c.drawString(72, 660, "3. All access to sensitive data must be logged.")
    c.drawString(72, 640, "4. Network traffic must be restricted using firewall rules.")
    c.drawString(72, 620, "5. Privileged access must be controlled via role-based access.")
    c.save()


@pytest.fixture(scope="session", autouse=True)
def fixture_files():
    """Ensure tests/fixtures/ directory and all fixture files exist."""
    os.makedirs(FIXTURES_DIR, exist_ok=True)

    pdf_path = os.path.join(FIXTURES_DIR, "sample.pdf")
    if not os.path.isfile(pdf_path):
        _make_fixture_pdf(pdf_path)

    yield  # tests run here

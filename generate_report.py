"""Generate a project overview PDF for the meeting."""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY


def build_pdf(output_path: str):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=1 * inch,
        rightMargin=1 * inch,
        topMargin=1 * inch,
        bottomMargin=1 * inch,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "Title", parent=styles["Title"],
        fontSize=20, textColor=colors.HexColor("#1a3a5c"),
        spaceAfter=6, alignment=TA_CENTER,
    )
    subtitle_style = ParagraphStyle(
        "Subtitle", parent=styles["Normal"],
        fontSize=11, textColor=colors.HexColor("#444444"),
        spaceAfter=4, alignment=TA_CENTER,
    )
    h1_style = ParagraphStyle(
        "H1", parent=styles["Heading1"],
        fontSize=14, textColor=colors.HexColor("#1a3a5c"),
        spaceBefore=16, spaceAfter=6,
        borderPad=4,
    )
    h2_style = ParagraphStyle(
        "H2", parent=styles["Heading2"],
        fontSize=12, textColor=colors.HexColor("#2c5f8a"),
        spaceBefore=10, spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "Body", parent=styles["Normal"],
        fontSize=10, leading=15, spaceAfter=6,
        alignment=TA_JUSTIFY,
    )
    bullet_style = ParagraphStyle(
        "Bullet", parent=styles["Normal"],
        fontSize=10, leading=14, spaceAfter=3,
        leftIndent=16, bulletIndent=0,
    )
    code_style = ParagraphStyle(
        "Code", parent=styles["Code"],
        fontSize=8.5, leading=13,
        backColor=colors.HexColor("#f4f4f4"),
        borderColor=colors.HexColor("#cccccc"),
        borderWidth=0.5, borderPad=6,
        spaceAfter=8,
    )
    caption_style = ParagraphStyle(
        "Caption", parent=styles["Normal"],
        fontSize=9, textColor=colors.HexColor("#666666"),
        alignment=TA_CENTER, spaceAfter=8,
    )

    story = []

    # ── Title block ──────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph("Security Requirements Change Detector", title_style))
    story.append(Paragraph("COMP 5700/6700 — Project Report", subtitle_style))
    story.append(Paragraph("Ayush Patel &nbsp;&nbsp;|&nbsp;&nbsp; Ryan Lunsford", subtitle_style))
    story.append(Paragraph("Auburn University &nbsp;&nbsp;|&nbsp;&nbsp; April 2026", subtitle_style))
    story.append(Spacer(1, 0.1 * inch))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1a3a5c")))
    story.append(Spacer(1, 0.15 * inch))

    # ── 1. Project Overview ───────────────────────────────────────────────────
    story.append(Paragraph("1. Project Overview", h1_style))
    story.append(Paragraph(
        "This project automatically detects changes between two CIS security requirements "
        "documents (PDF format) and triggers a static analysis scan using Kubescape. "
        "The system extracts Key Data Elements (KDEs) from each document using an LLM, "
        "compares the extracted elements, maps differences to Kubescape security controls, "
        "and produces a compliance scan report as a CSV file.",
        body_style
    ))

    # ── 2. Architecture ───────────────────────────────────────────────────────
    story.append(Paragraph("2. System Architecture", h1_style))
    story.append(Paragraph(
        "The project is organized into four components (tasks), each implemented as a "
        "Python module with a clean function-level interface:",
        body_style
    ))

    arch_data = [
        ["Module", "File", "Responsibility"],
        ["Task-1: Extractor", "src/extractor.py",
         "Load PDFs, build prompts, run Gemma-3-1B, output YAML + LLM log"],
        ["Task-2: Comparator", "src/comparator.py",
         "Diff two YAML files by element names and requirements"],
        ["Task-3: Executor", "src/executor.py",
         "Map diffs to Kubescape controls, run scanner, save CSV"],
        ["Utilities", "src/utils.py",
         "Shared file I/O, YAML load/save, validation helpers"],
        ["Entry Point", "main.py",
         "CLI interface + PyInstaller binary target"],
    ]
    arch_table = Table(arch_data, colWidths=[1.4*inch, 1.6*inch, 3.5*inch])
    arch_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3a5c")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#eef3f8"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(arch_table)
    story.append(Spacer(1, 0.1 * inch))

    # Data flow
    story.append(Paragraph("Data Flow", h2_style))
    story.append(Paragraph(
        "<font name='Courier' size='8.5'>"
        "cis-r1.pdf  ──►  extractor  ──►  cis-r1-kdes.yaml  ──►  comparator  ──►  differing_elements.txt<br/>"
        "cis-r2.pdf  ──►  extractor  ──►  cis-r2-kdes.yaml  ──┘                    differing_requirements.txt<br/>"
        "                                                                                    │<br/>"
        "                                                             executor  ◄────────────┘<br/>"
        "                                                                 │<br/>"
        "                                                         kubescape scan<br/>"
        "                                                                 │<br/>"
        "                                                     kubescape_results.csv"
        "</font>",
        ParagraphStyle("flow", parent=styles["Normal"], fontSize=8.5,
                       fontName="Courier", leading=13, spaceAfter=10,
                       backColor=colors.HexColor("#f4f4f4"), borderPad=8)
    ))

    # ── 3. Task-1 Extractor ───────────────────────────────────────────────────
    story.append(Paragraph("3. Task-1: Extractor", h1_style))

    story.append(Paragraph("LLM Used", h2_style))
    story.append(Paragraph(
        "The project uses <b>google/gemma-3-1b-it</b> (1 billion parameters, instruction-tuned) "
        "loaded via the HuggingFace <i>transformers</i> library. The model runs locally with "
        "GPU acceleration when available (CUDA), falling back to CPU.",
        body_style
    ))

    story.append(Paragraph("Key Data Elements (KDEs)", h2_style))
    story.append(Paragraph(
        "The extractor identifies the following 10 KDEs in each document:",
        body_style
    ))
    kde_items = [
        "access_control", "authentication", "authorization",
        "data_protection", "encryption", "logging_and_monitoring",
        "network_security", "patch_management", "privileged_access",
        "vulnerability_management",
    ]
    for k in kde_items:
        story.append(Paragraph(f"• {k}", bullet_style))

    story.append(Spacer(1, 0.05 * inch))
    story.append(Paragraph("Three Prompt Strategies", h2_style))

    prompts_data = [
        ["Strategy", "Description"],
        ["Zero-Shot",
         "No examples. Instructs the model to list requirements for a given KDE "
         "directly from the document excerpt."],
        ["Few-Shot",
         "3 in-context examples (encryption, authentication, logging) anchor the "
         "model to the expected numbered-list format."],
        ["Chain-of-Thought",
         "5 explicit reasoning steps guide the model: read → identify → classify "
         "→ list → handle empty case. Reduces hallucination on short excerpts."],
    ]
    p_table = Table(prompts_data, colWidths=[1.4*inch, 5.1*inch])
    p_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c5f8a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#eef3f8"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(p_table)

    story.append(Paragraph("Output Format (YAML)", h2_style))
    story.append(Paragraph(
        "<font name='Courier' size='8.5'>"
        "encryption:<br/>"
        "&nbsp;&nbsp;name: encryption<br/>"
        "&nbsp;&nbsp;requirements:<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;- All data at rest must be encrypted using AES-256.<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;- Data in transit must use TLS 1.2 or higher.<br/>"
        "authentication:<br/>"
        "&nbsp;&nbsp;name: authentication<br/>"
        "&nbsp;&nbsp;requirements:<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;- Users must authenticate using multi-factor authentication."
        "</font>",
        ParagraphStyle("yaml", parent=styles["Normal"], fontSize=8.5,
                       fontName="Courier", leading=13, spaceAfter=8,
                       backColor=colors.HexColor("#f4f4f4"), borderPad=8)
    ))

    # ── 4. Task-2 Comparator ─────────────────────────────────────────────────
    story.append(Paragraph("4. Task-2: Comparator", h1_style))
    story.append(Paragraph(
        "The comparator loads the two YAML files from Task-1 and produces two TEXT files:",
        body_style
    ))

    comp_data = [
        ["Output File", "Content", "No-Diff Sentinel"],
        ["differing_elements.txt",
         "Element names present in one YAML but not the other (one per line)",
         "NO DIFFERENCES IN REGARDS TO ELEMENT NAMES"],
        ["differing_requirements.txt",
         "Requirements that differ across shared elements, formatted as NAME,REQU",
         "NO DIFFERENCES IN REGARDS TO ELEMENT REQUIREMENTS"],
    ]
    c_table = Table(comp_data, colWidths=[1.8*inch, 2.4*inch, 2.3*inch])
    c_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c5f8a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#eef3f8"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(c_table)

    # ── 5. Task-3 Executor ───────────────────────────────────────────────────
    story.append(Paragraph("5. Task-3: Executor", h1_style))
    story.append(Paragraph(
        "The executor reads the Task-2 TEXT files, maps differing elements to Kubescape "
        "control IDs using a built-in lookup table, runs Kubescape from the command line "
        "on <i>project-yamls.zip</i>, and saves results as a CSV.",
        body_style
    ))

    story.append(Paragraph("Kubescape Control Mapping (sample)", h2_style))
    ctrl_data = [
        ["KDE Element", "Kubescape Control IDs"],
        ["access_control", "C-0036, C-0056, C-0058"],
        ["authentication", "C-0036, C-0057, C-0221"],
        ["encryption", "C-0034, C-0087, C-0096"],
        ["network_security", "C-0044, C-0065, C-0260"],
        ["logging_and_monitoring", "C-0009, C-0015, C-0048"],
        ["privileged_access", "C-0036, C-0042, C-0055"],
    ]
    ctrl_table = Table(ctrl_data, colWidths=[2.2*inch, 4.3*inch])
    ctrl_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c5f8a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#eef3f8"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(ctrl_table)

    story.append(Paragraph("CSV Output Headers", h2_style))
    csv_data = [
        ["FilePath", "Severity", "Control name", "Failed resources", "All Resources", "Compliance score"],
        ["manifests/deploy.yaml", "High", "RBAC least privileges", "2", "5", "60.0"],
        ["manifests/svc.yaml", "Medium", "Network policies", "1", "3", "66.7"],
    ]
    csv_table = Table(csv_data, colWidths=[1.4*inch, 0.7*inch, 1.5*inch, 0.9*inch, 0.9*inch, 1.1*inch])
    csv_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c5f8a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#eef3f8"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(csv_table)

    # ── 6. Test Suite ────────────────────────────────────────────────────────
    story.append(Paragraph("6. Test Suite", h1_style))
    story.append(Paragraph(
        "All 31 unit tests pass. The LLM pipeline and Kubescape subprocess are mocked "
        "so tests run fast without GPU or network access:",
        body_style
    ))

    test_data = [
        ["Test File", "Tests", "Coverage"],
        ["tests/test_extractor.py", "8 tests", "load_pdf, 3 prompts, extract_kdes, collect_llm_output, run_extraction"],
        ["tests/test_comparator.py", "11 tests", "load_validate, diff_names, diff_reqs, write functions, run_comparison"],
        ["tests/test_executor.py", "10 tests", "readers, map_to_controls, kubescape install/run, parse, save_csv, run_executor"],
        ["tests/conftest.py", "session fixture", "Auto-generates sample.pdf using reportlab before tests run"],
    ]
    t_table = Table(test_data, colWidths=[1.7*inch, 0.75*inch, 4.05*inch])
    t_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3a5c")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#eef3f8"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t_table)

    # ── 7. Input Combinations ────────────────────────────────────────────────
    story.append(Paragraph("7. Nine Required Input Combinations", h1_style))
    inputs_data = [
        ["#", "PDF 1", "PDF 2", "CLI Command"],
        ["1", "cis-r1.pdf", "cis-r1.pdf", "python main.py cis-r1.pdf cis-r1.pdf"],
        ["2", "cis-r1.pdf", "cis-r2.pdf", "python main.py cis-r1.pdf cis-r2.pdf"],
        ["3", "cis-r1.pdf", "cis-r3.pdf", "python main.py cis-r1.pdf cis-r3.pdf"],
        ["4", "cis-r1.pdf", "cis-r4.pdf", "python main.py cis-r1.pdf cis-r4.pdf"],
        ["5", "cis-r2.pdf", "cis-r2.pdf", "python main.py cis-r2.pdf cis-r2.pdf"],
        ["6", "cis-r2.pdf", "cis-r3.pdf", "python main.py cis-r2.pdf cis-r3.pdf"],
        ["7", "cis-r2.pdf", "cis-r4.pdf", "python main.py cis-r2.pdf cis-r4.pdf"],
        ["8", "cis-r3.pdf", "cis-r3.pdf", "python main.py cis-r3.pdf cis-r3.pdf"],
        ["9", "cis-r3.pdf", "cis-r4.pdf", "python main.py cis-r3.pdf cis-r4.pdf"],
    ]
    in_table = Table(inputs_data, colWidths=[0.3*inch, 0.9*inch, 0.9*inch, 4.4*inch])
    in_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3a5c")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("FONTNAME", (3, 1), (3, -1), "Courier"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#eef3f8"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(in_table)

    # ── 8. How to Run ────────────────────────────────────────────────────────
    story.append(Paragraph("8. How to Run", h1_style))
    story.append(Paragraph("Setup (one time)", h2_style))
    story.append(Paragraph(
        "<font name='Courier' size='8.5'>"
        "python3 -m venv comp5700-venv<br/>"
        "comp5700-venv\\Scripts\\activate&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
        "# Windows<br/>"
        "pip install -r requirements.txt<br/>"
        "huggingface-cli login&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
        "# requires HuggingFace token (Gemma is gated)"
        "</font>",
        ParagraphStyle("setup", parent=styles["Normal"], fontSize=8.5,
                       fontName="Courier", leading=14, spaceAfter=8,
                       backColor=colors.HexColor("#f4f4f4"), borderPad=8)
    ))

    story.append(Paragraph("Run a comparison", h2_style))
    story.append(Paragraph(
        "<font name='Courier' size='8.5'>"
        "python main.py cis-r1.pdf cis-r2.pdf<br/>"
        "python main.py cis-r1.pdf cis-r2.pdf --prompt-strategy few_shot<br/>"
        "python main.py cis-r1.pdf cis-r2.pdf --prompt-strategy chain_of_thought"
        "</font>",
        ParagraphStyle("run", parent=styles["Normal"], fontSize=8.5,
                       fontName="Courier", leading=14, spaceAfter=8,
                       backColor=colors.HexColor("#f4f4f4"), borderPad=8)
    ))

    story.append(Paragraph("Run tests", h2_style))
    story.append(Paragraph(
        "<font name='Courier' size='8.5'>"
        "pytest tests/ -v"
        "</font>",
        ParagraphStyle("tests", parent=styles["Normal"], fontSize=8.5,
                       fontName="Courier", leading=14, spaceAfter=8,
                       backColor=colors.HexColor("#f4f4f4"), borderPad=8)
    ))

    # ── 9. Remaining Steps ───────────────────────────────────────────────────
    story.append(Paragraph("9. Remaining Steps Before Submission", h1_style))
    remaining = [
        ("HuggingFace login",
         "Accept Gemma license at huggingface.co/google/gemma-3-1b-it, "
         "generate a Read token, run: huggingface-cli login"),
        ("End-to-end test run",
         "Run all 9 input combinations once to verify YAML + CSV outputs"),
        ("Push to GitHub",
         "Push to a public repo — GitHub Actions CI will run all 31 tests automatically"),
        ("Build binary",
         "pyinstaller --onefile --name project6700 main.py"),
        ("Submission",
         "Submit via https://forms.office.com/r/fMQeqiUbK3 by April 24, 2026 11:59 PM CST"),
    ]
    for title, desc in remaining:
        story.append(Paragraph(
            f"<b>{title}:</b> {desc}", bullet_style
        ))
        story.append(Spacer(1, 0.04*inch))

    # ── Footer ───────────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.2 * inch))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cccccc")))
    story.append(Spacer(1, 0.06 * inch))
    story.append(Paragraph(
        "Ayush Patel (ayp0006@auburn.edu) &nbsp;·&nbsp; "
        "Ryan Lunsford (rtl0019@auburn.edu) &nbsp;·&nbsp; Auburn University · COMP 5700/6700",
        caption_style
    ))

    doc.build(story)
    print(f"PDF saved: {output_path}")


if __name__ == "__main__":
    build_pdf("project_overview.pdf")

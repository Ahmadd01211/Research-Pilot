"""Original synthetic PDFs: independent layouts, no user papers or external downloads."""

from io import BytesIO

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject

CASES = [
    "prose",
    "two-columns",
    "crop",
    "rotation-90",
    "rotation-180",
    "rotation-270",
    "definition-table",
    "model-table",
    "two-model-table",
    "grouped-table",
    "ambiguous-grouped-table",
    "vector-figure",
    "image-figure",
    "uncaptioned-image",
    "equation-baselines",
    "front-matter",
    "front-matter-unanchored",
    "section-heading",
    "decimal-prose",
    "summary-table",
    "sectioned-numeric",
    "ambiguous-sectioned-numeric",
]


def corpus_pdf(case):
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    resources = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    page[NameObject("/Resources")] = resources
    ops = []

    def text(value, x, y, size=10):
        safe = value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        ops.append(f"BT /F1 {size} Tf {x} {y} Td ({safe}) Tj ET")

    def rect(x, y, w, h):
        ops.append(f"q .92 g {x} {y} {w} {h} re f Q")

    if case in {"front-matter", "front-matter-unanchored"}:
        text("Received: 1 January 2026", 55, 760, 8)
        text("DOI: 10.0000/synthetic", 55, 745, 8)
        text("Evidence in academic systems", 55, 710, 20)
        text("Alice Example | Ben Researcher", 55, 670, 12)
        text("University of Synthetic Studies", 55, 620, 8)
        text("Department of Evidence", 55, 608, 8)
        text("Correspondence", 55, 570, 8)
        text("Email: author@example.com", 55, 558, 8)
        text("Funding information", 55, 520, 8)
        text("Synthetic foundation", 55, 508, 8)
        text("Abstract", 220, 615, 10)
        text("We measured adoption using survey evidence.", 220, 595, 10)
        text("The findings preserve their original source.", 220, 575, 10)
        if case == "front-matter":
            text("1 | INTRODUCTION", 55, 450, 12)
            text("The main research body remains eligible for evidence retrieval.", 55, 428, 10)
    elif case in {"section-heading", "decimal-prose"}:
        text("The preceding discussion concludes with a different finding.", 55, 695)
        text(
            "3.3 | Early use and adoption"
            if case == "section-heading"
            else "3.3 percent of firms reported this result",
            55,
            670,
            14 if case == "section-heading" else 10,
        )
        text("The next paragraph explains this section with traceable source evidence.", 55, 648)
    elif case == "summary-table":
        text("The preceding paragraph must remain separate from the table.", 50, 635)
        text("TABLE 1 Summary by sample.", 50, 615)
        rect(50, 550, 510, 50)
        for y in [470, 410, 350]:
            rect(50, y, 360, 30)
        rect(50, 349, 510, 1)
        for n, x in enumerate([210, 280, 350, 420, 490], 1):
            text(f"({n})", x, 585)
            text("Sample", x, 570)
            text(f"Group{n}", x, 557)
        for n, y in enumerate([525, 485, 455, 425, 395, 365], 1):
            text("Employment" if n == 1 else f"Measure {n}", 55, y)
            if n == 1:
                text("(unweighted)", 55, y - 13)
            for col, x in enumerate([210, 280, 350, 420, 490], 1):
                text(f"{n}.{col}", x, y)
        text("Notes: These source notes are outside the numeric table.", 50, 330)
    elif case in {"sectioned-numeric", "ambiguous-sectioned-numeric"}:
        text("TABLE 1 Unnumbered comparison.", 50, 720)
        rect(50, 650, 510, 50)
        text("Full sample", 55, 655)
        text("Usage rate (%)", 300, 683)
        text("6.0", 300, 670)
        for label, x in [("Yes", 300), ("No", 400), ("Difference", 490)]:
            text(label, x, 655)
        text("A. Owner characteristics", 55, 625)
        for n, y in enumerate([605, 585, 565], 1):
            text(f"Characteristic {n}", 55, y)
            text(
                "12345678901234567890123456789"
                if case == "ambiguous-sectioned-numeric" and n == 1
                else "8.4",
                300,
                y,
            )
            text("5.3", 400, y)
            text("3.1", 490, y)
        text("B. Startup conditions", 55, 540)
        for n, y in enumerate([520, 500, 480], 1):
            text(f"Condition {n}", 55, y)
            text("6.4", 300, y)
            text("5.8", 400, y)
            text("0.6", 490, y)
        text("Notes: Verify this table against its original source.", 55, 440)
    elif case in {"grouped-table", "ambiguous-grouped-table"}:
        rect(50, 650, 510, 50)
        for y in [570, 490]:
            rect(50, y, 510, 40)
        rect(50, 450, 510, 1)
        text("TABLE 1 Grouped measures.", 50, 720)
        text("Location", 55, 653)
        for n, x, label in [(1, 220, "Firm-weighted"), (2, 400, "Employment-weighted")]:
            text(f"({n})", x, 685)
            text(label, x, 670)
            text("Share", x, 653)
            text("Rank", x + 60, 653)
        for row, y in enumerate([625, 585, 545, 505, 465], 1):
            text(f"City {row}", 55, y)
            text(
                "12345678901234567890"
                if case == "ambiguous-grouped-table" and row == 1
                else f"{row}.4",
                220,
                y,
            )
            if row != 2:
                text(str(row + 10), 280, y)
            text(f"{row}.8", 400, y)
            text(str(row + 20), 460, y)
    elif case in {"definition-table", "model-table", "two-model-table"}:
        rect(50, 650, 510, 50)
        for y in [570, 490]:
            rect(50, y, 510, 40)
        rect(50, 450, 510, 1)
        if case in {"model-table", "two-model-table"}:
            text("TABLE 1 Synthetic model comparison.", 50, 720)
            text("Description", 55, 665)
            for n, x in enumerate([220, 440] if case == "two-model-table" else [220, 330, 440], 1):
                text(f"({n})", x, 685)
                text("Revenue", x, 665)
            for row, y in enumerate([625, 585, 545, 505, 465], 1):
                text(f"Factor {row}", 55, y)
                text(f"0.{row}2 (0.03)", 220, y)
                text(f"0.{row}4 (0.05)", 440, y)
        else:
            for row, y in enumerate([675, 625, 585, 545, 505, 465], 1):
                text(f"Technology {row}", 55, y)
                text(f"Measured definition {row}", 330, y)
    elif case in {"vector-figure", "image-figure", "uncaptioned-image"}:
        if case == "vector-figure":
            rect(100, 550, 50, 100)
            rect(180, 550, 50, 140)
            text("99%", 110, 660)
        else:
            image = DecodedStreamObject()
            image.set_data(bytes([30, 80, 140]))
            image.update(
                {
                    NameObject("/Type"): NameObject("/XObject"),
                    NameObject("/Subtype"): NameObject("/Image"),
                    NameObject("/Width"): NumberObject(1),
                    NameObject("/Height"): NumberObject(1),
                    NameObject("/ColorSpace"): NameObject("/DeviceRGB"),
                    NameObject("/BitsPerComponent"): NumberObject(8),
                }
            )
            resources[NameObject("/XObject")] = DictionaryObject(
                {NameObject("/Im1"): writer._add_object(image)}
            )
            ops.append("q 300 0 0 150 100 550 cm /Im1 Do Q")
        if case != "uncaptioned-image":
            text("FIGURE 1 Synthetic measured results.", 100, 520)
        text("Figure 1 is discussed by the authors in this source paragraph.", 55, 450)
    elif case == "equation-baselines":
        text("Average growth is defined by the following displayed equation:", 55, 720)
        text("g =", 210, 660)
        text("1", 245, 668, 8)
        text("3", 245, 652, 8)
        text("ln", 275, 660)
        text("r", 295, 668, 8)
        text("t", 300, 664, 6)
        text("r", 295, 652, 8)
        text("t-1", 300, 648, 6)
        text("(1)", 550, 660)
        text("The following paragraph explains the estimator and assumptions.", 55, 600)
    else:
        text("Alpha evidence supports the first independently measured result.", 55, 720)
        text(
            "Beta evidence describes a separate result with source attribution.",
            55 if case != "two-columns" else 330,
            680 if case != "two-columns" else 720,
            8 if case == "two-columns" else 10,
        )
    stream = DecodedStreamObject()
    stream.set_data("\n".join(ops).encode("ascii"))
    page[NameObject("/Contents")] = writer._add_object(stream)
    if case == "crop":
        page.cropbox.lower_left = (40, 40)
        page.cropbox.upper_right = (580, 760)
    if case.startswith("rotation-"):
        page.rotate(int(case.split("-")[1]))
    target = BytesIO()
    writer.write(target)
    return target.getvalue()

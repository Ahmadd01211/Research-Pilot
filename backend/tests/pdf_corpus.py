"""Original synthetic PDFs: independent layouts, no user papers or external downloads."""

from io import BytesIO

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject

CASES = [
    "numbered-section-numeric",
    "continued-numeric-table",
    "continued-categorical-table",
    "regression-multiheader-table",
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
    "back-matter",
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

    if case == "numbered-section-numeric":
        text("TABLE 5 Comparison by status.", 50, 720)
        rect(50, 650, 510, 40)
        for n, (label, x) in enumerate(
            [("Full sample", 280), ("Use AI", 350), ("Do not use AI", 420), ("Difference", 510)], 1
        ):
            text(f"({n})", x, 675, 8)
            text(label, x, 658, 8)
        text("A. Owner characteristics", 55, 630)
        for n, y in enumerate([610, 590, 570, 530, 510, 490], 1):
            if n == 4:
                text("B. Startup financing", 55, 550)
            text(f"Characteristic {n}", 55, y)
            for col, x in enumerate([280, 350, 420, 510], 1):
                text(f"{n}.{col}", x, y, 8)
        text("Notes: Source notes remain outside the table.", 50, 465)
    elif case == "continued-numeric-table":
        text("TABLE 5 (Continued)", 50, 740)
        rect(50, 699, 510, 25)
        for n, (label, x) in enumerate(
            [("Full sample", 270), ("Use AI", 350), ("Do not use AI", 420), ("Difference", 510)], 1
        ):
            text(f"({n})", x, 721, 8)
            text(label, x, 704, 8)
        text("In medium-sized CBSA (<1,000,000)", 50, 690)
        for x, value in zip([270, 350, 420, 510], ["17.8", "17.1", "17.8", "-0.7"], strict=True):
            text(value, x, 690, 8)
        text("In large-sized CBSA (1,000,000+)", 50, 673)
        for x, value in zip([270, 350, 420, 510], ["50.3", "55.1", "49.9", "5.2"], strict=True):
            text(value, x, 673, 8)
        text("Notes: Continuation notes remain outside the two data rows.", 50, 640)
    elif case == "continued-categorical-table":
        text("TABLE 7 (Continued)", 50, 740)
        xs = [215, 265, 315, 365, 415, 465, 515]
        for n, x in enumerate(xs, 1):
            text(f"({n})", x, 721, 8)
            text("Use AI", x, 704, 8)
        text("Description", 50, 704, 8)
        text("State-by-industry controls", 50, 680)
        for x in xs:
            text("Yes", x, 680, 8)
        text("Observations (rounded)", 50, 658)
        for x, value in zip(xs, ["75,000"] * 6 + ["209,000"], strict=True):
            text(value, x, 658, 8)
        text("Notes: These notes are not a table row.", 50, 630)
    elif case == "regression-multiheader-table":
        text("TABLE 9 Adoption outcomes across owner groups.", 50, 750)
        rect(50, 674, 510, 55)
        starts = [230, 320, 410, 500]
        for n, x in enumerate(starts, 1):
            text(f"({n})", x, 715, 8)
        for label, x in zip(["All", "AI", "NonAI", "Difference"], starts, strict=True):
            text(label, x, 700, 8)
        for label, x in zip(["firms", "users", "users", "overall"], starts[:3] + [520], strict=True):
            text(label, x, 685, 8)
        text("Outcome", 55, 685, 8)
        data = [
            ("Revenue growth", ["0.11***", "0.08**", "0.02", "0.09***"], ["(0.02)", "(0.03)", "(0.02)", "(0.02)"]),
            ("Advanced degree (1/0)", ["0.04***", "", "0.01", "0.02*"], ["(0.01)", "", "(0.01)", "(0.01)"]),
            ("Owner age", ["", "0.03", "0.01", "-0.01"], ["", "(0.02)", "(0.02)", "(0.01)"]),
            ("Product innovation", ["0.05**", "0.07***", "0.03*", "0.06***"], ["(0.02)", "(0.02)", "(0.02)", "(0.02)"]),
        ]
        y = 655
        # Simulate publisher running matter whose extracted y-coordinate
        # overlaps a real row but lies outside the page's text content box.
        text("publisher", 580, y, 6)
        for label, coefficients, errors in data:
            text(label, 55, y)
            for x, value in zip(starts, coefficients, strict=True):
                if value:
                    text(value, x, y, 8)
            y -= 14
            for x, error in zip(starts, errors, strict=True):
                if error:
                    text(error, x, y, 8)
            y -= 38
        text("(Continues)", 500, y)
        text("Notes: Standard errors are in parentheses.", 50, y - 22)
    elif case in {"front-matter", "front-matter-unanchored"}:
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
    elif case == "back-matter":
        text("The conclusion reports a source-based result.", 55, 740)
        text("ACKNOWLEDGMENTS", 55, 705, 12)
        text("Colleagues offered comments and assistance.", 55, 683)
        text("DATA AVAILABILITY STATEMENT", 55, 648, 12)
        text("Approved researchers can access confidential survey data.", 55, 626)
        text("ORCID", 55, 591, 12)
        text("Alice Example https://orcid.org/0000-0000-0000-0000", 55, 569)
        text("ENDNOTES", 55, 534, 12)
        text("1", 55, 510, 7)
        text("The first note describes the survey response rate.", 67, 508)
        text("2", 55, 480, 7)
        text("The second note qualifies the source population.", 67, 478)
        text("REFERENCES", 55, 440, 12)
        text("Example A. Source publication title.", 55, 418)
        text("APPENDIX A: ADDITIONAL RESULTS", 55, 375, 12)
        text("The appendix reports another measured result.", 55, 353)
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

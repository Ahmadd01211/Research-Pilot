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
    "vector-figure",
    "image-figure",
    "uncaptioned-image",
    "equation-baselines",
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

    if case in {"definition-table", "model-table", "two-model-table"}:
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

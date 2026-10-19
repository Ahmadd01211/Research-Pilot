from io import BytesIO

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def pdf_bytes(texts=None, encrypted=False):
    texts = (
        texts
        if texts is not None
        else [
            "This academic paper contains a traceable source statement for evidence extraction and testing.",
            "The second page reports a different finding and preserves the physical PDF page number.",
        ]
    )
    writer = PdfWriter()
    for text in texts:
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
        )
        stream = DecodedStreamObject()
        safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream.set_data(("BT /F1 12 Tf 72 720 Td (" + safe + ") Tj ET").encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(stream)
    if encrypted:
        writer.encrypt("synthetic-password")
    target = BytesIO()
    writer.write(target)
    return target.getvalue()

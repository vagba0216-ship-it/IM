import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors


class PDFGenerator:
    @staticmethod
    def generate_receipt(file_path, sale_id, customer, date_str, items, total):
        vatable_sales = total / 1.12
        vat_amount = total - vatable_sales

        doc = SimpleDocTemplate(file_path, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
        story = []
        styles = getSampleStyleSheet()

        header_data = [
            [
                Paragraph("<b>Auto Parts Supply Inc.</b><br/>123 Mechanic St., Manila, Philippines<br/>VAT Reg. TIN: 000-123-456-0000", styles["Normal"]),
                Paragraph("<font size=20 color='#4a285d'><b>OFFICIAL RECEIPT</b></font>", styles["Normal"])
            ]
        ]
        header_table = Table(header_data, colWidths=[300, 240])
        header_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('ALIGN', (1, 0), (1, 0), 'RIGHT')]))
        story.append(header_table)
        story.append(Spacer(1, 20))

        info_data = [
            [
                Paragraph(f"<b>Billed To:</b><br/>{customer}", styles["Normal"]),
                Paragraph(f"<b>Receipt #:</b> {sale_id:06d}<br/><b>Date:</b> {date_str}", styles["Normal"])
            ]
        ]
        info_table = Table(info_data, colWidths=[300, 240])
        info_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('ALIGN', (1, 0), (1, 0), 'RIGHT')]))
        story.append(info_table)
        story.append(Spacer(1, 20))

        table_data = [["QTY", "Particulars & Description", "Unit Cost", "Amount"]]
        for item in items:
            desc_str = f"{item['particulars']} - {item['description']}" if item.get('description') else item['particulars']
            table_data.append([
                str(item["qty"]),
                desc_str,
                f"PHP {item['unit_cost']:,.2f}",
                f"PHP {item['subtotal']:,.2f}"
            ])

        item_table = Table(table_data, colWidths=[50, 270, 110, 110])
        item_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6b3e75')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0'))
        ]))
        story.append(item_table)
        story.append(Spacer(1, 15))

        totals_data = [
            ["Vatable Sales:", f"PHP {vatable_sales:,.2f}"],
            ["12% VAT Amount:", f"PHP {vat_amount:,.2f}"],
            ["TOTAL AMOUNT DUE:", f"PHP {total:,.2f}"]
        ]
        totals_table = Table(totals_data, colWidths=[380, 160])
        totals_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold'),
            ('LINEABOVE', (0, 2), (-1, 2), 1, colors.HexColor('#6b3e75'))
        ]))
        story.append(totals_table)
        story.append(Spacer(1, 30))

        notes = Paragraph(
            "<b>Notes:</b><br/>Prices are inclusive of 12% VAT. Thank you for your purchase! Please retain this receipt for warranty or exchange purposes within 30 days.",
            styles["Normal"]
        )
        story.append(notes)

        doc.build(story)

    @staticmethod
    def generate_job_quote(file_path, estimate_id, customer, vehicle, date_str, parts_items, m_cost, l_cost, total):
        doc = SimpleDocTemplate(file_path, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
        story = []
        styles = getSampleStyleSheet()

        header_data = [
            [
                Paragraph("<b>Auto Parts Supply Inc.</b><br/>123 Mechanic St., Manila, Philippines<br/>Service & Estimation Dept.", styles["Normal"]),
                Paragraph("<font size=20 color='#1f6aa5'><b>JOB ESTIMATE QUOTE</b></font>", styles["Normal"])
            ]
        ]
        header_table = Table(header_data, colWidths=[300, 240])
        header_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('ALIGN', (1, 0), (1, 0), 'RIGHT')]))
        story.append(header_table)
        story.append(Spacer(1, 15))

        info_data = [
            [
                Paragraph(f"<b>Client:</b> {customer}<br/><b>Vehicle:</b> {vehicle}", styles["Normal"]),
                Paragraph(f"<b>Quote #:</b> EST-{estimate_id:04d}<br/><b>Date:</b> {date_str}", styles["Normal"])
            ]
        ]
        info_table = Table(info_data, colWidths=[300, 240])
        info_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('ALIGN', (1, 0), (1, 0), 'RIGHT')]))
        story.append(info_table)
        story.append(Spacer(1, 15))

        # Itemized Parts Table
        table_data = [["QTY", "Required Part / Description", "Unit Cost", "Subtotal"]]
        for item in parts_items:
            desc_str = f"{item['particulars']} - {item['description']}" if item.get('description') else item['particulars']
            table_data.append([
                str(item["qty"]),
                desc_str,
                f"PHP {item['unit_cost']:,.2f}",
                f"PHP {item['subtotal']:,.2f}"
            ])

        parts_table = Table(table_data, colWidths=[50, 270, 110, 110])
        parts_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f6aa5')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0'))
        ]))
        story.append(parts_table)
        story.append(Spacer(1, 15))

        parts_total = sum(i["subtotal"] for i in parts_items)
        summary_data = [
            ["Total Inventory Parts Cost:", f"PHP {parts_total:,.2f}"],
            ["Miscellaneous Materials Cost:", f"PHP {m_cost:,.2f}"],
            ["Service Labor Cost:", f"PHP {l_cost:,.2f}"],
            ["ESTIMATED TOTAL DUE:", f"PHP {total:,.2f}"]
        ]
        summary_table = Table(summary_data, colWidths=[380, 160])
        summary_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 3), (-1, 3), 'Helvetica-Bold'),
            ('LINEABOVE', (0, 3), (-1, 3), 1, colors.HexColor('#1f6aa5'))
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 25))

        notes = Paragraph(
            "<b>Note:</b> This quote is valid for 15 days from issuance. Actual costs may vary slightly depending on additional repairs identified during disassembly.",
            styles["Normal"]
        )
        story.append(notes)
        doc.build(story)
"""Envio por e-mail dos relatórios de pesquisa por produto."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from pathlib import Path

from .config import Config


def send_report(
    report_path: Path,
    product: str,
    responsible_name: str,
    responsible_email: str,
    config: Config,
) -> None:
    """Envia o relatório de um produto ao respectivo responsável."""
    message = EmailMessage()
    message["Subject"] = f"Apuração mensal de marcas - {product}"
    message["From"] = config.email_sender
    message["To"] = responsible_email
    message["Cc"] = config.email_cc
    message.set_content(
        f"""Prezados,

Segue a apuração mensal de marcas sob responsabilidade de {responsible_name},
referente ao período analisado.

Solicitamos que avalie se alguma das notícias identificadas tem relevância para
seu negócio.

Atenciosamente,
Fábio Belotto

"""
    )
    message.add_attachment(
        report_path.read_bytes(),
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=report_path.name,
    )

    recipients = [responsible_email, config.email_cc]
    with smtplib.SMTP(host=config.smtp_host, port=config.smtp_port) as smtp:
        smtp.send_message(message, from_addr=config.email_sender, to_addrs=recipients)

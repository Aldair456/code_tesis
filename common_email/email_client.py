import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
from io import BytesIO


class EmailClient:
    """Cliente para enviar correos electrónicos con soporte para adjuntos"""

    def __init__(self, smtp_server, smtp_port, email, password):
        """
        Inicializa el cliente de email

        Args:
            smtp_server: Servidor SMTP (ej: smtp.gmail.com)
            smtp_port: Puerto SMTP (587 para TLS, 465 para SSL)
            email: Tu dirección de correo
            password: Tu contraseña o app password
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.email = email
        self.password = password

    def send_email(self, to, subject, body, html=False, attachments=None,
                   byte_attachments=None, cc=None, bcc=None):
        """
        Envía un correo electrónico

        Args:
            to: Email del destinatario (str o lista de strings)
            subject: Asunto del correo
            body: Cuerpo del mensaje
            html: Si True, el mensaje se envía como HTML
            attachments: Lista de rutas de archivos para adjuntar
            byte_attachments: Lista de tuplas (bytes, filename, mime_type) para adjuntar desde memoria
            cc: Copia (str o lista)
            bcc: Copia oculta (str o lista)

        Returns:
            True si se envió correctamente, False en caso contrario
        """
        try:
            # Crear mensaje
            msg = MIMEMultipart()
            msg['From'] = self.email
            msg['To'] = to if isinstance(to, str) else ', '.join(to)
            msg['Subject'] = subject

            # Agregar CC y BCC si existen
            if cc:
                msg['Cc'] = cc if isinstance(cc, str) else ', '.join(cc)
            if bcc:
                msg['Bcc'] = bcc if isinstance(bcc, str) else ', '.join(bcc)

            # Agregar cuerpo del mensaje
            message_type = 'html' if html else 'plain'
            msg.attach(MIMEText(body, message_type))

            # Agregar archivos adjuntos desde rutas
            if attachments:
                for attachment in attachments:
                    self.attach_file(msg, attachment)

            # Agregar archivos adjuntos desde bytes
            if byte_attachments:
                for byte_data in byte_attachments:
                    if len(byte_data) == 2:
                        # Formato: (bytes, filename)
                        file_bytes, filename = byte_data
                        self.attach_file_from_bytes(msg, file_bytes, filename)
                    elif len(byte_data) == 3:
                        # Formato: (bytes, filename, mime_type)
                        file_bytes, filename, mime_type = byte_data
                        self.attach_file_from_bytes(msg, file_bytes, filename, mime_type)

            # Obtener todos los destinatarios
            all_recipients = []
            if isinstance(to, list):
                all_recipients.extend(to)
            else:
                all_recipients.append(to)

            if cc:
                all_recipients.extend(cc if isinstance(cc, list) else [cc])
            if bcc:
                all_recipients.extend(bcc if isinstance(bcc, list) else [bcc])

            # Conectar al servidor y enviar
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email, self.password)
                server.sendmail(self.email, all_recipients, msg.as_string())

            print(f"✓ Email enviado correctamente a {to}")
            return True

        except Exception as e:
            print(f"✗ Error al enviar email: {str(e)}")
            return False

    def attach_file(self, msg, file_path):
        """
        Adjunta un archivo al mensaje de email desde una ruta

        Args:
            msg: Objeto MIMEMultipart al que se adjuntará el archivo
            file_path: Ruta del archivo a adjuntar

        Returns:
            True si se adjuntó correctamente, False en caso contrario
        """
        try:
            # Verificar que el archivo existe
            if not os.path.exists(file_path):
                print(f"⚠ Archivo no encontrado: {file_path}")
                return False

            # Leer el archivo en modo binario
            with open(file_path, 'rb') as file:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(file.read())

            # Codificar en base64
            encoders.encode_base64(part)

            # Agregar encabezado con el nombre del archivo
            filename = os.path.basename(file_path)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {filename}'
            )

            # Adjuntar al mensaje
            msg.attach(part)
            print(f"✓ Archivo adjuntado: {filename}")
            return True

        except Exception as e:
            print(f"⚠ No se pudo adjuntar {file_path}: {str(e)}")
            return False

    def attach_file_from_bytes(self, msg, file_bytes, filename, mime_type=None):
        """
        Adjunta un archivo al mensaje de email desde bytes en memoria

        Args:
            msg: Objeto MIMEMultipart al que se adjuntará el archivo
            file_bytes: Bytes del archivo (bytes object)
            filename: Nombre que tendrá el archivo adjunto
            mime_type: Tipo MIME del archivo (opcional). Ej: 'application/pdf', 'image/png'
                      Si no se especifica, se usa 'application/octet-stream'

        Returns:
            True si se adjuntó correctamente, False en caso contrario
        """
        try:
            # Validar que file_bytes sea de tipo bytes
            if not isinstance(file_bytes, (bytes, bytearray)):
                print(f"⚠ Los datos deben ser de tipo bytes, recibido: {type(file_bytes)}")
                return False

            # Determinar el tipo MIME
            if mime_type:
                main_type, sub_type = mime_type.split('/')
                part = MIMEBase(main_type, sub_type)
            else:
                part = MIMEBase('application', 'octet-stream')

            # Establecer el payload con los bytes
            part.set_payload(file_bytes)

            # Codificar en base64
            encoders.encode_base64(part)

            # Agregar encabezado con el nombre del archivo
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {filename}'
            )

            # Adjuntar al mensaje
            msg.attach(part)
            print(f"✓ Archivo adjuntado desde bytes: {filename} ({len(file_bytes)} bytes)")
            return True

        except Exception as e:
            print(f"⚠ No se pudo adjuntar el archivo desde bytes: {str(e)}")
            return False

    def send_email_with_bytes(self, to, subject, body, byte_attachments, html=False):
        """
        Método conveniente para enviar email con adjuntos desde bytes

        Args:
            to: Destinatario(s)
            subject: Asunto
            body: Cuerpo del mensaje
            byte_attachments: Lista de tuplas (bytes, filename) o (bytes, filename, mime_type)
            html: Si el cuerpo es HTML

        Returns:
            True si se envió correctamente
        """
        return self.send_email(
            to=to,
            subject=subject,
            body=body,
            html=html,
            byte_attachments=byte_attachments
        )

    def test_connection(self):
        """
        Prueba la conexión con el servidor SMTP

        Returns:
            True si la conexión es exitosa, False en caso contrario
        """
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email, self.password)
            print("✓ Conexión exitosa con el servidor SMTP")
            return True
        except Exception as e:
            print(f"✗ Error de conexión: {str(e)}")
            return False


# ==================== EJEMPLOS DE USO ====================

if __name__ == "__main__":

    # CONFIGURACIÓN DEL CLIENTE
    client = EmailClient(
        smtp_server='smtp.gmail.com',
        smtp_port=587,
        email=os.environ['SMTP_EMAIL'],
        password=os.environ['SMTP_PASSWORD'],
    )






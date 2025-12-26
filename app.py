from flask import Flask, request, render_template, jsonify
import base64
import zipfile
import io
import os
import logging
from lxml import etree

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory storage for received requests
received_requests = []

def get_local_text(node, name, default=""):
    """Finds a child node by local name and returns its text."""
    if node is None:
        return default
    # Use xpath to find the node by local name
    results = node.xpath(f".//*[local-name()='{name}']")
    if results:
        return results[0].text or default
    return default

def find_local_node(node, name):
    """Finds a node by local name."""
    if node is None:
        return None
    results = node.xpath(f".//*[local-name()='{name}']")
    return results[0] if results else None

def parse_ses_xml(xml_content):
    """Parses the inner SES XML (PV or RH) into a structured dict."""
    try:
        parser = etree.XMLParser(recover=True, remove_blank_text=True)
        root = etree.fromstring(xml_content.encode('utf-8'), parser=parser)
        
        data = {
            "tipo": "Desconocido",
            "referencia": "N/A",
            "fechas": {},
            "personas": []
        }
        
        # Detect type and extract header info
        contrato = find_local_node(root, "contrato")
        reserva = find_local_node(root, "reserva")
        
        if contrato is not None:
            data["tipo"] = "Parte de Viajero (PV)"
            data["referencia"] = get_local_text(contrato, "referencia", "N/A")
            data["fechas"] = {
                "Entrada": get_local_text(contrato, "fechaEntrada"),
                "Salida": get_local_text(contrato, "fechaSalida")
            }
        elif reserva is not None:
            data["tipo"] = "Reserva de Hospedaje (RH)"
            data["referencia"] = get_local_text(reserva, "referencia", "N/A")
            data["fechas"] = {
                "Reserva": get_local_text(reserva, "fechaReserva"),
                "Entrada": get_local_text(reserva, "fechaEntrada"),
                "Salida": get_local_text(reserva, "fechaSalida")
            }
            
        # Extract persons
        for persona in root.xpath("//*[local-name()='persona']"):
            nombre = get_local_text(persona, "nombre")
            ap1 = get_local_text(persona, "apellido1")
            ap2 = get_local_text(persona, "apellido2")
            tipo_doc = get_local_text(persona, "tipoDocumento")
            num_doc = get_local_text(persona, "numeroDocumento")
            
            p_data = {
                "nombre": f"{nombre} {ap1} {ap2}".strip(),
                "documento": f"{tipo_doc}: {num_doc}",
                "soporte": get_local_text(persona, "soporteDocumento", "N/A"),
                "nacimiento": get_local_text(persona, "fechaNacimiento"),
                "nacionalidad": get_local_text(persona, "nacionalidad"),
                "sexo": get_local_text(persona, "sexo")
            }
            data["personas"].append(p_data)
            
        return data
    except Exception as e:
        logger.error(f"Error parsing inner XML: {e}")
        return None

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", requests=received_requests)

@app.route("/hospedajes-web/ws/v1/comunicacion", methods=["POST"])
def mock_ses():
    try:
        data = request.data
        logger.info(f"Received request: {len(data)} bytes")
        
        # Parse SOAP
        parser = etree.XMLParser(recover=True)
        root = etree.fromstring(data, parser=parser)
        
        # Extract base64 payload
        solicitud_node = find_local_node(root, "solicitud")
        if solicitud_node is None:
            return "Missing solicitud node", 400
            
        b64_data = solicitud_node.text
        zip_data = base64.b64decode(b64_data)
        
        # Extract ZIP
        zip_buffer = io.BytesIO(zip_data)
        xml_content = ""
        with zipfile.ZipFile(zip_buffer, "r") as zip_file:
            for name in zip_file.namelist():
                if name.endswith(".xml"):
                    xml_content = zip_file.read(name).decode("utf-8")
                    break
        
        # Extract header info from SOAP
        cabecera = find_local_node(root, "cabecera")
        header_info = {
            "arrendador": get_local_text(cabecera, "codigoArrendador", "N/A"),
            "aplicacion": get_local_text(cabecera, "aplicacion", "N/A"),
            "tipoOperacion": get_local_text(cabecera, "tipoOperacion", "N/A"),
            "tipoComunicacion": get_local_text(cabecera, "tipoComunicacion", "N/A")
        }
        
        # Parse inner XML for structured view
        structured_data = parse_ses_xml(xml_content)
        
        # Store request
        import datetime
        request_entry = {
            "id": len(received_requests) + 1,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "header": header_info,
            "xml": xml_content,
            "structured": structured_data
        }
        received_requests.insert(0, request_entry)
        
        # Return success response
        response_xml = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
   <soapenv:Body>
      <com:comunicacionResponse xmlns:com="http://www.soap.servicios.hospedajes.mir.es/comunicacion">
         <resultado>
            <codigo>0</codigo>
            <descripcion>Exito (Mock)</descripcion>
            <lote>MOCK-{len(received_requests)}</lote>
         </resultado>
      </com:comunicacionResponse>
   </soapenv:Body>
</soapenv:Envelope>"""
        
        return response_xml, 200, {"Content-Type": "text/xml"}
        
    except Exception as e:
        logger.exception("Error processing mock request")
        return str(e), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

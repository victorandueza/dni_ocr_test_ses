from flask import Flask, request, render_template, jsonify
import base64
import zipfile
import io
import os
import logging
from lxml import etree
import json

# GCS Imports
try:
    from google.cloud import storage
    GCS_AVAILABLE = True
except ImportError:
    GCS_AVAILABLE = False

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
DATA_FILE = "requests.json"
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", "ses-mock-server-data-52284878557")

# In-memory storage for received requests
received_requests = []

def get_gcs_bucket():
    """Returns the GCS bucket object if available."""
    if not GCS_AVAILABLE:
        return None
    try:
        client = storage.Client()
        return client.bucket(GCS_BUCKET_NAME)
    except Exception as e:
        logger.error(f"Error getting GCS bucket: {e}")
        return None

def load_data():
    """Loads requests from GCS or local JSON file."""
    global received_requests
    
    # Try GCS first
    if GCS_AVAILABLE:
        bucket = get_gcs_bucket()
        if bucket:
            try:
                blob = bucket.blob(DATA_FILE)
                if blob.exists():
                    data = blob.download_as_text()
                    received_requests = json.loads(data)
                    logger.info(f"Loaded {len(received_requests)} requests from GCS bucket {GCS_BUCKET_NAME}")
                    return
            except Exception as e:
                logger.error(f"Error loading from GCS: {e}")

    # Fallback to local file
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                received_requests = json.load(f)
            logger.info(f"Loaded {len(received_requests)} requests from local file {DATA_FILE}")
        except Exception as e:
            logger.error(f"Error loading local data: {e}")
            received_requests = []

def save_data():
    """Saves requests to GCS and local JSON file."""
    # Save locally first
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(received_requests, f, indent=4)
        logger.info(f"Saved {len(received_requests)} requests to local file {DATA_FILE}")
    except Exception as e:
        logger.error(f"Error saving local data: {e}")

    # Save to GCS
    if GCS_AVAILABLE:
        bucket = get_gcs_bucket()
        if bucket:
            try:
                blob = bucket.blob(DATA_FILE)
                blob.upload_from_string(json.dumps(received_requests, indent=4), content_type='application/json')
                logger.info(f"Saved {len(received_requests)} requests to GCS bucket {GCS_BUCKET_NAME}")
            except Exception as e:
                logger.error(f"Error saving to GCS: {e}")

# Load data on startup
load_data()

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
    """Parses the inner SES XML (PV or RH) or Oracle BI Publisher XML into a structured list of contracts."""
    try:
        parser = etree.XMLParser(recover=True, remove_blank_text=True)
        root = etree.fromstring(xml_content.encode('utf-8'), parser=parser)
        
        contracts = []
        
        # Check if it's the Oracle BI Publisher format (DATA_DS)
        if root.tag == 'DATA_DS' or root.xpath(".//*[local-name()='DATA_DS']"):
            g1_nodes = root.xpath(".//*[local-name()='G_1']")
            for g1 in g1_nodes:
                data = {
                    "tipo": "Reserva de Hospedaje (RH)", # Assuming these are always reservations based on file name
                    "referencia": get_local_text(g1, "CONFIRMATION_NO", "N/A"),
                    "fechas": {
                        "Reserva": get_local_text(g1, "INSERT_DATE"),
                        "Entrada": get_local_text(g1, "BEGIN_DATE"),
                        "Salida": get_local_text(g1, "END_DATE"),
                        "Pago": get_local_text(g1, "PAYMENT_METHOD")
                    },
                    "personas": []
                }
                
                # Extract persons (G_2)
                g2_nodes = g1.xpath(".//*[local-name()='G_2']")
                for g2 in g2_nodes:
                    nombre = get_local_text(g2, "FIRST")
                    # Sometimes name is split or just FIRST? XML shows FIRST.
                    
                    p_data = {
                        "nombre": nombre,
                        "documento": "N/A", # Not present in the snippet
                        "soporte": "N/A",
                        "nacimiento": "N/A",
                        "nacionalidad": get_local_text(g2, "NACIONALIDAD"),
                        "sexo": get_local_text(g2, "SEXO"),
                        "direccion": f"{get_local_text(g2, 'PAIS')}",
                        "contacto": f"Tel: {get_local_text(g2, 'TELEFONO')} / Email: {get_local_text(g2, 'CORREO')}"
                    }
                    data["personas"].append(p_data)
                
                contracts.append(data)
            return {
                "tipo": "Reserva de Hospedaje (RH)",
                "contracts": contracts,
                "raw_xml": xml_content
            }

        # Standard SES XML parsing
        
        # Iterate over each 'comunicacion' block
        # Note: In some XMLs, 'comunicacion' is a direct child of 'solicitud' (which is root here)
        # We look for any 'comunicacion' descendant to be safe, or direct children.
        # Using .// to find them anywhere or just iterating children if root is 'solicitud'
        
        comunicacion_nodes = root.xpath(".//*[local-name()='comunicacion']")
        
        if not comunicacion_nodes:
            # Fallback for old single-structure or if structure is different
            comunicacion_nodes = [root] 

        for com_node in comunicacion_nodes:
            data = {
                "tipo": "Desconocido",
                "referencia": "N/A",
                "fechas": {},
                "personas": []
            }
            
            contrato = find_local_node(com_node, "contrato")
            reserva = find_local_node(com_node, "reserva")
            
            if contrato is not None:
                data["tipo"] = "Parte de Viajero (PV)"
                data["referencia"] = get_local_text(contrato, "referencia", "N/A")
                
                pago = find_local_node(contrato, "pago")
                tipo_pago = get_local_text(pago, "tipoPago", "N/A") if pago is not None else "N/A"
                
                data["fechas"] = {
                    "Entrada": get_local_text(contrato, "fechaEntrada"),
                    "Salida": get_local_text(contrato, "fechaSalida"),
                    "Pago": tipo_pago
                }
            elif reserva is not None:
                data["tipo"] = "Reserva de Hospedaje (RH)"
                data["referencia"] = get_local_text(reserva, "referencia", "N/A")
                
                pago = find_local_node(reserva, "pago")
                tipo_pago = get_local_text(pago, "tipoPago", "N/A") if pago is not None else "N/A"
                
                data["fechas"] = {
                    "Reserva": get_local_text(reserva, "fechaReserva"),
                    "Entrada": get_local_text(reserva, "fechaEntrada"),
                    "Salida": get_local_text(reserva, "fechaSalida"),
                    "Pago": tipo_pago
                }
            else:
                # If no contract/reserva found in this node, skip it (might be just a wrapper or empty)
                continue

            # Extract persons for THIS communication block
            for persona in com_node.xpath(".//*[local-name()='persona']"):
                nombre = get_local_text(persona, "nombre")
                ap1 = get_local_text(persona, "apellido1")
                ap2 = get_local_text(persona, "apellido2")
                tipo_doc = get_local_text(persona, "tipoDocumento")
                num_doc = get_local_text(persona, "numeroDocumento")
                
                # Address
                direccion_node = find_local_node(persona, "direccion")
                if direccion_node is not None:
                    dir_texto = get_local_text(direccion_node, "direccion")
                    cp = get_local_text(direccion_node, "codigoPostal")
                    pais = get_local_text(direccion_node, "pais")
                    full_address = f"{dir_texto}, {cp}, {pais}"
                else:
                    full_address = "N/A"
                    
                # Contact
                tel = get_local_text(persona, "telefono")
                email = get_local_text(persona, "correo")
                contact_info = []
                if tel: contact_info.append(f"Tel: {tel}")
                if email: contact_info.append(f"Email: {email}")
                full_contact = " / ".join(contact_info) if contact_info else "N/A"
                
                p_data = {
                    "nombre": f"{nombre} {ap1} {ap2}".strip(),
                    "documento": f"{tipo_doc}: {num_doc}",
                    "soporte": get_local_text(persona, "soporteDocumento", "N/A"),
                    "nacimiento": get_local_text(persona, "fechaNacimiento"),
                    "nacionalidad": get_local_text(persona, "nacionalidad"),
                    "sexo": get_local_text(persona, "sexo"),
                    "direccion": full_address,
                    "contacto": full_contact
                }
                data["personas"].append(p_data)
            
            contracts.append(data)
            
        # Determine overall type based on what we found
        # If we found at least one "Parte de Viajero", we call it PV.
        # If we found "Reserva", we call it RH.
        # This logic might need to be more robust if mixed types are possible, 
        # but usually a file is one or the other.
        
        overall_type = "Desconocido"
        # Check raw string for type as requested for robustness
        if "<tipoComunicacion>RH</tipoComunicacion>" in xml_content:
            overall_type = "Reserva de Hospedaje (RH)"
        elif "<tipoComunicacion>PV</tipoComunicacion>" in xml_content:
            overall_type = "Parte de Viajero (PV)"
        else:
            # Fallback to inferring from parsed content
            if contracts:
                first_type = contracts[0].get("tipo", "")
                if "Parte" in first_type:
                    overall_type = "Parte de Viajero (PV)"
                elif "Reserva" in first_type:
                    overall_type = "Reserva de Hospedaje (RH)"

        return {
            "tipo": overall_type,
            "contracts": contracts,
            "raw_xml": xml_content
        }
    except Exception as e:
        logger.error(f"Error parsing inner XML: {e}")
        return {
            "tipo": "Error",
            "contracts": [],
            "raw_xml": xml_content,
            "error": str(e)
        }

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", requests=received_requests, json_requests=json.dumps(received_requests))

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
        
        # Save data
        save_data()
        
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

@app.route("/delete/<int:request_id>", methods=["DELETE"])
def delete_request(request_id):
    global received_requests
    try:
        # Filter out the request with the given ID
        received_requests = [req for req in received_requests if req["id"] != request_id]
        
        # Save changes
        save_data()
        
        return jsonify({"success": True, "message": f"Request {request_id} deleted"}), 200
    except Exception as e:
        logger.error(f"Error deleting request {request_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/delete-all", methods=["DELETE"])
def delete_all_requests():
    global received_requests
    try:
        received_requests = []
        
        # Save changes
        save_data()
        
        return jsonify({"success": True, "message": "All requests deleted"}), 200
    except Exception as e:
        logger.error(f"Error deleting all requests: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

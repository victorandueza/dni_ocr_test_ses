import requests
import base64
import zipfile
import io
import time

# Mock Server URL
URL = "http://localhost:8080/hospedajes-web/ws/v1/comunicacion"

def create_soap_payload(xml_content):
    # Create a ZIP containing the XML
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("test.xml", xml_content)
    
    zip_b64 = base64.b64encode(zip_buffer.getvalue()).decode("utf-8")
    
    soap_envelope = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:com="http://www.soap.servicios.hospedajes.mir.es/comunicacion">
   <soapenv:Header/>
   <soapenv:Body>
      <com:comunicacion>
         <cabecera>
            <codigoArrendador>TEST001</codigoArrendador>
            <aplicacion>TESTAPP</aplicacion>
            <tipoOperacion>1</tipoOperacion>
            <tipoComunicacion>1</tipoComunicacion>
         </cabecera>
         <solicitud>{zip_b64}</solicitud>
      </com:comunicacion>
   </soapenv:Body>
</soapenv:Envelope>"""
    return soap_envelope

def send_request(xml_content):
    payload = create_soap_payload(xml_content)
    try:
        response = requests.post(URL, data=payload, headers={"Content-Type": "text/xml"})
        print(f"Status: {response.status_code}")
    except Exception as e:
        print(f"Error: {e}")

# 1. Reserva de Hospedaje (RH) - John Doe
xml_rh_1 = """<?xml version="1.0" encoding="UTF-8"?>
<solicitud>
    <comunicacion>
        <reserva>
            <referencia>RES-001</referencia>
            <fechaReserva>20250101</fechaReserva>
            <fechaEntrada>20250201</fechaEntrada>
            <fechaSalida>20250205</fechaSalida>
            <pago>
                <tipoPago>Efectivo</tipoPago>
            </pago>
        </reserva>
        <persona>
            <nombre>John</nombre>
            <apellido1>Doe</apellido1>
            <tipoDocumento>P</tipoDocumento>
            <numeroDocumento>A12345678</numeroDocumento>
            <fechaNacimiento>19800101</fechaNacimiento>
            <nacionalidad>USA</nacionalidad>
            <sexo>M</sexo>
        </persona>
    </comunicacion>
</solicitud>"""

# 2. Parte de Viajero (PV) - Alice Smith
xml_pv_1 = """<?xml version="1.0" encoding="UTF-8"?>
<solicitud>
    <comunicacion>
        <contrato>
            <referencia>CON-001</referencia>
            <fechaEntrada>20250310</fechaEntrada>
            <fechaSalida>20250315</fechaSalida>
            <pago>
                <tipoPago>Tarjeta</tipoPago>
            </pago>
        </contrato>
        <persona>
            <nombre>Alice</nombre>
            <apellido1>Smith</apellido1>
            <tipoDocumento>D</tipoDocumento>
            <numeroDocumento>12345678Z</numeroDocumento>
            <fechaNacimiento>19900505</fechaNacimiento>
            <nacionalidad>ESP</nacionalidad>
            <sexo>F</sexo>
        </persona>
    </comunicacion>
</solicitud>"""

# 3. Reserva de Hospedaje (RH) - Bob Jones (Older date)
xml_rh_2 = """<?xml version="1.0" encoding="UTF-8"?>
<solicitud>
    <comunicacion>
        <reserva>
            <referencia>RES-002</referencia>
            <fechaReserva>20241201</fechaReserva>
            <fechaEntrada>20241220</fechaEntrada>
            <fechaSalida>20241225</fechaSalida>
        </reserva>
        <persona>
            <nombre>Bob</nombre>
            <apellido1>Jones</apellido1>
            <tipoDocumento>P</tipoDocumento>
            <numeroDocumento>B98765432</numeroDocumento>
        </persona>
    </comunicacion>
</solicitud>"""

print("Sending RH 1...")
send_request(xml_rh_1)
time.sleep(1)

print("Sending PV 1...")
send_request(xml_pv_1)
time.sleep(1)

print("Sending RH 2...")
send_request(xml_rh_2)

print("Done.")

from lxml import etree
import random

SOURCE_FILE = "/home/victor/Descargas/ESP-Viajeros_viajeros (3).xml"
OUTPUT_FILE = "/home/victor/Descargas/ESP-Viajeros_viajeros (4).xml"

# Realistic data lists
NAMES = ["Antonio", "Manuel", "Jose", "Francisco", "David", "Juan", "Javier", "Daniel", "Maria", "Carmen", "Ana", "Isabel", "Laura", "Elena", "Cristina", "Marta"]
SURNAMES = ["Garcia", "Rodriguez", "Gonzalez", "Fernandez", "Lopez", "Martinez", "Sanchez", "Perez", "Gomez", "Martin", "Jimenez", "Ruiz", "Hernandez", "Diaz", "Moreno"]
CITIES = [
    ("Calle Mayor 1", "28001", "Madrid"),
    ("Av. Diagonal 123", "08018", "Barcelona"),
    ("Calle Betis 45", "41010", "Sevilla"),
    ("Gran Via 32", "28013", "Madrid"),
    ("Calle Colon 10", "46004", "Valencia"),
    ("Paseo de la Castellana 200", "28046", "Madrid"),
    ("Calle Larios 5", "29005", "Malaga"),
    ("Av. de la Constitucion 12", "41001", "Sevilla")
]
DOMAINS = ["gmail.com", "hotmail.com", "yahoo.es", "outlook.com"]

def generate_fake_person(index):
    person = etree.Element("persona")
    
    rol = etree.SubElement(person, "rol")
    rol.text = "VI"
    
    nombre_text = random.choice(NAMES)
    nombre = etree.SubElement(person, "nombre")
    nombre.text = nombre_text
    
    ap1_text = random.choice(SURNAMES)
    ap1 = etree.SubElement(person, "apellido1")
    ap1.text = ap1_text
    
    ap2_text = random.choice(SURNAMES)
    ap2 = etree.SubElement(person, "apellido2")
    ap2.text = ap2_text
    
    tipo_doc = etree.SubElement(person, "tipoDocumento")
    tipo_doc.text = "DNI"
    
    # Generate realistic-looking DNI
    dni_num = random.randint(10000000, 99999999)
    dni_letters = "TRWAGMYFPDXBNJZSQVHLCKE"
    dni_letter = dni_letters[dni_num % 23]
    num_doc = etree.SubElement(person, "numeroDocumento")
    num_doc.text = f"{dni_num}{dni_letter}"
    
    soporte = etree.SubElement(person, "soporteDocumento")
    soporte.text = ""
    
    # Random realistic birth date (18-80 years old)
    year = random.randint(1945, 2005)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    nac = etree.SubElement(person, "fechaNacimiento")
    nac.text = f"{year}-{month:02d}-{day:02d}"
    
    sexo = etree.SubElement(person, "sexo")
    sexo.text = random.choice(["H", "M"])
    
    addr, cp_val, city_val = random.choice(CITIES)
    
    direccion = etree.SubElement(person, "direccion")
    d1 = etree.SubElement(direccion, "direccion")
    d1.text = addr
    d2 = etree.SubElement(direccion, "direccionComplementaria")
    d2.text = ""
    cp = etree.SubElement(direccion, "codigoPostal")
    cp.text = cp_val
    pais = etree.SubElement(direccion, "pais")
    pais.text = "ESP"
    
    tel = etree.SubElement(person, "telefono")
    # Generate realistic mobile number
    tel.text = f"6{random.randint(0,9)}{random.randint(0,9)}{random.randint(0,9)}{random.randint(0,9)}{random.randint(0,9)}{random.randint(0,9)}{random.randint(0,9)}{random.randint(0,9)}"
    
    tel2 = etree.SubElement(person, "telefono2")
    tel2.text = ""
    
    email = etree.SubElement(person, "correo")
    email.text = f"{nombre_text.lower()}.{ap1_text.lower()}{random.randint(1,99)}@{random.choice(DOMAINS)}"
    
    parentesco = etree.SubElement(person, "parentesco")
    parentesco.text = ""
    
    return person

def main():
    try:
        parser = etree.XMLParser(remove_blank_text=True)
        tree = etree.parse(SOURCE_FILE, parser)
        root = tree.getroot()
        
        # Find all comunicacion blocks
        # lxml handles namespaces differently. We can use local-name() in xpath
        comunicacion_nodes = root.xpath(".//*[local-name()='comunicacion']")
        
        print(f"Found {len(comunicacion_nodes)} comunicacion nodes.")
        
        total_added = 0
        
        for com in comunicacion_nodes:
            # Find contrato and numPersonas
            contrato = None
            for child in com:
                if 'contrato' in child.tag:
                    contrato = child
                    break
            
            if contrato is None:
                continue
                
            num_personas_node = None
            for child in contrato:
                if 'numPersonas' in child.tag:
                    num_personas_node = child
                    break
            
            if num_personas_node is None or not num_personas_node.text:
                continue
                
            try:
                target_count = int(num_personas_node.text)
            except ValueError:
                continue
                
            # Count existing persons
            persons = [child for child in com if 'persona' in child.tag]
            current_count = len(persons)
            
            needed = target_count - current_count
            
            if needed > 0:
                print(f"Adding {needed} persons to contract (Target: {target_count}, Current: {current_count})")
                for i in range(needed):
                    new_person = generate_fake_person(total_added + i + 1)
                    com.append(new_person)
                total_added += needed

        tree.write(OUTPUT_FILE, encoding="UTF-8", xml_declaration=True, pretty_print=True)
        print(f"Successfully created {OUTPUT_FILE} with {total_added} new travelers.")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()

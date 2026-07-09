"""
fix_docx_template.py
Repara tags Jinja2/docxtpl fragmentados en archivos .docx
Uso: python fix_docx_template.py <ruta_template.docx>
"""
import zipfile
import re
import shutil
import os
import sys


def fix_fragmented_jinja_tags(xml: str) -> str:
    """
    Word a veces fragmenta {%tr ... %} en múltiples runs XML.
    Este paso une los fragmentos para que docxtpl pueda procesarlos.
    
    Ejemplo de XML roto que se repara:
      <w:r><w:t>{%</w:t></w:r><w:r><w:t>tr for x in y %}</w:t></w:r>
    Resultado:
      <w:r><w:t>{%tr for x in y %}</w:t></w:r>
    """
    
    # Paso 1: Eliminar marcas de corrección ortográfica que interrumpen tags
    # Word inserta <w:proofErr> entre fragmentos de texto
    xml = re.sub(r'<w:proofErr[^/]*/>', '', xml)
    xml = re.sub(r'<w:proofErr[^>]*>.*?</w:proofErr>', '', xml, flags=re.DOTALL)
    
    # Paso 2: Unir runs consecutivos que pertenecen al mismo tag Jinja2
    # Patrón: </w:t></w:r> seguido de XML de formato y luego <w:r...><w:t...>
    # cuando el texto contiene partes de un tag {%...%} o {{...}}
    
    def merge_runs(xml_content):
        # Encontrar todos los <w:r>...</w:r> y unir los que tienen fragmentos de tags
        # Estrategia: buscar el patrón de cierre+apertura de run dentro de un tag
        
        # Regex para detectar </w:t> seguido de XML y luego <w:t> dentro del contexto de un tag
        pattern = r'(<w:t[^>]*>)((?:[^<]|<(?!/?w:t))*?)\{([%{])(</w:t>(?:(?!</w:r>).)*?</w:r>\s*(?:<[^>]+>\s*)*<w:r[^>]*>(?:(?!</w:t>).)*?<w:t[^>]*>)([^}]*[%}]\})'
        
        merged = re.sub(pattern, 
                       lambda m: m.group(1) + m.group(2) + '{' + m.group(3) + m.group(5),
                       xml_content, flags=re.DOTALL)
        return merged
    
    # Aplicar múltiples pasadas por si hay fragmentación en cadena
    for _ in range(5):
        prev = xml
        xml = merge_runs(xml)
        if xml == prev:
            break
    
    # Paso 3: Método más agresivo - reconstruir el texto completo de cada párrafo
    # y detectar tags rotos
    xml = repair_split_tags_aggressive(xml)
    
    return xml


def repair_split_tags_aggressive(xml: str) -> str:
    """
    Método agresivo: busca runs consecutivos cuyo texto combinado forma un tag Jinja2.
    Fusiona esos runs en uno solo.
    """
    # Patrón de un run de Word con su texto
    run_pattern = re.compile(
        r'(<w:r(?:\s[^>]*)?>(?:(?!</w:r>).)*?<w:t(?:\s[^>]*)?>)(.*?)(</w:t>(?:(?!</w:r>).)*?</w:r>)',
        re.DOTALL
    )
    
    # Encontrar todos los runs y sus textos
    runs = [(m.start(), m.end(), m.group(1), m.group(2), m.group(3)) 
            for m in run_pattern.finditer(xml)]
    
    if not runs:
        return xml
    
    replacements = []  # (start, end, new_text)
    i = 0
    
    while i < len(runs):
        start_i, end_i, open_tag_i, text_i, close_tag_i = runs[i]
        
        # ¿Este run contiene el inicio de un tag Jinja2 incompleto?
        combined_text = text_i
        
        # Verificar si hay un tag abierto sin cerrar
        open_braces = combined_text.count('{%') + combined_text.count('{{')
        close_braces = combined_text.count('%}') + combined_text.count('}}')
        
        if open_braces > close_braces and i + 1 < len(runs):
            # Hay un tag abierto - intentar fusionar con runs siguientes
            j = i + 1
            merge_end = end_i
            first_open = open_tag_i
            first_close = close_tag_i
            
            while j < len(runs) and open_braces > close_braces:
                start_j, end_j, open_tag_j, text_j, close_tag_j = runs[j]
                
                # Solo fusionar si los runs son adyacentes (con XML de formato en medio)
                between = xml[merge_end:start_j]
                # Verificar que solo hay XML de formato (no contenido significativo)
                between_stripped = re.sub(r'<[^>]+>', '', between).strip()
                
                if between_stripped:  # Hay texto entre los runs → no fusionar
                    break
                
                combined_text += text_j
                merge_end = end_j
                first_close = close_tag_j
                
                open_braces = combined_text.count('{%') + combined_text.count('{{')
                close_braces = combined_text.count('%}') + combined_text.count('}}')
                j += 1
            
            if merge_end > end_i:
                # Fusionar: usar el primer open_tag y el último close_tag con el texto combinado
                new_run = first_open + combined_text + first_close
                replacements.append((start_i, merge_end, new_run))
                i = j
                continue
        
        i += 1
    
    # Aplicar reemplazos de atrás hacia adelante para no desplazar índices
    for start, end, new_text in reversed(replacements):
        xml = xml[:start] + new_text + xml[end:]
    
    return xml


def analyze_template(xml: str) -> None:
    """Muestra información de diagnóstico sobre los tags encontrados."""
    print("\n=== DIAGNÓSTICO DEL TEMPLATE ===")
    
    # Buscar todos los tags Jinja2 en el XML (ya ensamblados o rotos)
    all_tags = re.findall(r'\{[%{][^}]*[%}]\}', xml)
    print(f"\nTags Jinja2 encontrados ({len(all_tags)}):")
    for tag in all_tags:
        tag_clean = re.sub(r'\s+', ' ', tag).strip()
        print(f"  {tag_clean}")
    
    # Buscar posibles fragmentos rotos ('{%' sin cerrar en el mismo run)
    broken = re.findall(r'\{[%{](?:(?!\})[^<])*$', xml, re.MULTILINE)
    if broken:
        print(f"\n⚠️  Posibles fragmentos rotos ({len(broken)}):")
        for b in broken[:10]:
            print(f"  {repr(b)}")
    else:
        print("\n✓ No se detectaron fragmentos rotos visibles")
    
    # Buscar específicamente tags {%tr
    tr_tags = re.findall(r'\{%\s*tr\b[^%]*%\}', xml)
    print(f"\nTags {{%tr}} encontrados ({len(tr_tags)}):")
    for tag in tr_tags:
        print(f"  {tag}")
    
    if not tr_tags:
        print("  ⚠️  NINGÚN tag {%tr} fue encontrado - pueden estar fragmentados en el XML")


def fix_template(input_path: str, output_path: str = None) -> str:
    """
    Repara el template docx y guarda la versión corregida.
    Returns: ruta del archivo de salida
    """
    if output_path is None:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_fixed{ext}"
    
    print(f"Procesando: {input_path}")
    print(f"Salida: {output_path}")
    
    # Leer el archivo
    with zipfile.ZipFile(input_path, 'r') as z:
        file_list = z.namelist()
        original_xml = z.read('word/document.xml').decode('utf-8')
    
    print(f"\nArchivos en el docx: {file_list}")
    print(f"\nTamaño XML original: {len(original_xml)} chars")
    
    # Analizar ANTES
    print("\n--- ANTES DE REPARAR ---")
    analyze_template(original_xml)
    
    # Reparar
    fixed_xml = fix_fragmented_jinja_tags(original_xml)
    
    print(f"\nTamaño XML reparado: {len(fixed_xml)} chars")
    
    # Analizar DESPUÉS  
    print("\n--- DESPUÉS DE REPARAR ---")
    analyze_template(fixed_xml)
    
    # Guardar
    shutil.copy(input_path, output_path)
    
    tmp_path = output_path + ".tmp"
    with zipfile.ZipFile(output_path, 'r') as zin:
        with zipfile.ZipFile(tmp_path, 'w', zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                if item.filename == 'word/document.xml':
                    zout.writestr(item, fixed_xml.encode('utf-8'))
                else:
                    zout.writestr(item, zin.read(item.filename))
    
    os.replace(tmp_path, output_path)
    print(f"\n✅ Template reparado guardado en: {output_path}")
    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python fix_docx_template.py <ruta_template.docx> [ruta_salida.docx]")
        print("Ejemplo: python fix_docx_template.py credit-proposal-template.docx")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not os.path.exists(input_file):
        print(f"❌ Archivo no encontrado: {input_file}")
        sys.exit(1)
    
    fix_template(input_file, output_file)

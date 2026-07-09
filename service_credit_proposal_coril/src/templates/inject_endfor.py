"""
inject_endfor.py
Inyecta {%tr endfor %} faltante en el template ya reparado.
Uso: python inject_endfor.py credit-proposal-template_fixed.docx
"""
import zipfile, re, shutil, os, sys


def fix(xml: str) -> str:
    # 1. Eliminar proofErr residuales
    xml = re.sub(r'<w:proofErr\b[^>]*/>', '', xml)

    # 2. Dentro de la fila que tiene {%tr for ... %}, buscar el último {{...}}
    #    y pegarle {%tr endfor %} inmediatamente después.
    def patch_tr_row(m):
        row = m.group(0)

        # ¿Ya tiene endfor? → no tocar
        if re.search(r'\{%\s*tr\s+endfor', row):
            return row

        # ¿Tiene el {%tr for?
        if not re.search(r'\{%tr\s+for\b', row):
            return row

        # Buscar el último }} en el row y pegarle {%tr endfor %} después
        # Patrón: última ocurrencia de }} dentro de un <w:t>
        last = None
        for mm in re.finditer(r'(\}\})(</w:t>)', row):
            last = mm

        if last:
            insert_pos = last.end(1)  # después de }}
            row = row[:insert_pos] + '{%tr endfor %}' + row[insert_pos:]
            print("  ✅ {%tr endfor %} inyectado después de:", last.group(0))
        else:
            print("  ⚠️  No se encontró }} para anclar el endfor en esta fila")

        return row

    xml = re.sub(r'<w:tr\b.*?</w:tr>', patch_tr_row, xml, flags=re.DOTALL)
    return xml


def process(input_path, output_path=None):
    if output_path is None:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_v2{ext}"

    print(f"Leyendo: {input_path}")
    with zipfile.ZipFile(input_path, 'r') as z:
        original_xml = z.read('word/document.xml').decode('utf-8')

    print("Aplicando parche...")
    fixed_xml = fix(original_xml)

    # Verificar resultado
    tr_tags = re.findall(r'\{%tr[^%]*%\}', fixed_xml)
    print(f"\nTags {{%tr}} después del parche ({len(tr_tags)}):")
    for t in tr_tags:
        print(f"  {t.strip()}")

    if len(tr_tags) >= 2:
        print("\n✅ Ambos tags presentes ({%tr for %} y {%tr endfor %})")
    else:
        print("\n⚠️  Faltan tags - revisa manualmente")

    # Guardar
    shutil.copy(input_path, output_path)
    tmp = output_path + ".tmp"
    with zipfile.ZipFile(output_path, 'r') as zin:
        with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                if item.filename == 'word/document.xml':
                    zout.writestr(item, fixed_xml.encode('utf-8'))
                else:
                    zout.writestr(item, zin.read(item.filename))
    os.replace(tmp, output_path)
    print(f"\n✅ Guardado en: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python inject_endfor.py <archivo_fixed.docx>")
        sys.exit(1)
    f = sys.argv[1]
    if not os.path.exists(f):
        print(f"❌ No existe: {f}")
        sys.exit(1)
    process(f, sys.argv[2] if len(sys.argv) > 2 else None)
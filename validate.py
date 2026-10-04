#!/usr/bin/env python3
"""Valida os geofeeds (RFC 8805) conforme requisitos do Registro.br.
Uso: python3 validate.py   (na raiz do repositório)
Nome do arquivo define o bloco: geofeeds_138-59-96_22.csv -> 138.59.96.0/22
                                geofeeds_2804-da4_32.csv  -> 2804:da4::/32
"""
import csv, ipaddress, pathlib, re, sys

def block_from_name(name):
    m = re.fullmatch(r"geofeeds_(.+)_(\d+)\.csv", name)
    if not m:
        raise ValueError("nome fora do padrão geofeeds_<bloco>_<mascara>.csv")
    addr, plen = m.group(1), m.group(2)
    groups = addr.split("-")
    is_v4 = all(g.isdigit() and len(g) <= 3 and int(g) <= 255 for g in groups) and len(groups) <= 4
    if is_v4:
        groups += ["0"] * (4 - len(groups))
        return ipaddress.ip_network(f"{'.'.join(groups)}/{plen}", strict=True)
    return ipaddress.ip_network(f"{':'.join(groups)}::/{plen}", strict=True)

def check(path):
    errs = []
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return ["arquivo não está em UTF-8"], None
    if text.startswith("\ufeff"):
        errs.append("BOM presente (remover)")
    if "\r" in text:
        errs.append("CRLF detectado (usar LF)")
    try:
        block = block_from_name(path.name)
    except ValueError as e:
        return [str(e)], None

    nets = []
    for n, row in enumerate(csv.reader(text.splitlines()), 1):
        if not row or row[0].startswith("#"):
            continue
        if len(row) != 5:
            errs.append(f"L{n}: {len(row)} campos (esperado 5, com vírgula final)"); continue
        pfx, cc, region, city, postal = row
        if pfx.lower().startswith("ip_prefix"):
            errs.append(f"L{n}: cabeçalho presente (remover)"); continue
        try:
            net = ipaddress.ip_network(pfx, strict=True)
        except ValueError as e:
            errs.append(f"L{n}: prefixo inválido ({e})"); continue
        if net.version != block.version or not net.subnet_of(block):
            errs.append(f"L{n}: {net} fora do bloco {block}")
        for other in nets:
            if net.version == other.version and net.overlaps(other):
                errs.append(f"L{n}: {net} sobrepõe {other}")
        nets.append(net)
        if cc != "BR":
            errs.append(f"L{n}: país '{cc}' (esperado BR)")
        if not re.fullmatch(r"BR-[A-Z]{2}", region):
            errs.append(f"L{n}: região '{region}' fora de ISO 3166-2 (ex.: BR-RJ)")
        if not city.strip():
            errs.append(f"L{n}: cidade vazia")
        if postal != "":
            errs.append(f"L{n}: postal_code deve ficar vazio")
    if not nets:
        errs.append("nenhuma linha de dados")
    return errs, block

def main():
    files = sorted(pathlib.Path(".").glob("geofeeds_*.csv"))
    if not files:
        print("Nenhum geofeeds_*.csv encontrado."); sys.exit(1)
    failed = False
    for f in files:
        errs, block = check(f)
        print(f"{'ERRO' if errs else 'OK  '} {f.name}" + (f"  ({block})" if block else ""))
        for e in errs:
            print(f"     - {e}")
        failed |= bool(errs)
    sys.exit(1 if failed else 0)

if __name__ == "__main__":
    main()

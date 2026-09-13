# -*- coding: utf-8 -*-

SPECIALS = {
    'á': 'a', 'Á': 'A',
    'é': 'e', 'É': 'E',
    'í': 'i', 'Í': 'I',
    'ó': 'o', 'Ó': 'O',
    'ú': 'u', 'Ú': 'U',
    'ñ': 'n', 'Ñ': 'N',
}

CURRENCY_CODES = {
    'DOP': '214',
    'USD': '840',
    'EUR': '978',
}

BPD_BANK_CODES = {
    'DOP': {
        'BANCO DE RESERVAS': ('10101010', '6'),
        'BANCO DEL PROGRESO': ('10101110', '0'),
        'BANCO SCOTIABANK': ('10101030', '0'),
        'CITIBANK': ('10101060', '1'),
        'BANCO POPULAR': ('10101070', '8'),
        'BANCO BHD': ('10101230', '8'),
        'BANCO SANTA CRUZ': ('10101340', '4'),
        'BANCO CARIBE': ('10101350', '1'),
        'BANCO BDI': ('10101360', '8'),
        'BANCO VIMENCA': ('10101380', '2'),
        'BANCO LOPEZ DE HARO': ('10101390', '9'),
        'BANCO PROMERICA': ('44405900', '2'),
        'ASOC POPULAR DE AHORROS Y PRE.': ('47940900', '9'),
        'ASOCIACION CIBAO DE A/P': ('48991200', '7'),
        'BANCO BANESCO': ('11102328', '0'),
        'BANCO MULTIPLE ADEMI S A': ('10101300', '6'),
        'ASOC LA NACIONAL': ('10231034', '2'),
        'BANCO MULTIPLE LAFISE': ('11121214', '3'),
        'BANCO ATLANTICO': ('11101012', '5'),
        'BANCO UNION': ('30232423', '5'),
        'BANCO AHORRO Y CREDITO FONDESA': ('43491100', '8'),
        'QIK BANCO DIGITAL DOMINICANO': ('13249841', '2'),
        'BANCO AGRICOLA DE LA REPUBLICA': ('40100766', ' '),
    },
    'USD': {
        'BANCO DE RESERVAS': ('80101010', '5'),
        'BANCO DEL PROGRESO': ('80101110', '0'),
        'BANCO SCOTIABANK': ('80101030', '9'),
        'CITIBANK': ('80101060', '0'),
        'BANCO POPULAR': ('80101070', '7'),
        'BANCO BHD': ('80101230', '7'),
        'BANCO SANTA CRUZ': ('80101340', '3'),
        'BANCO CARIBE': ('80101350', '0'),
        'BANCO BDI': ('80101360', '7'),
        'BANCO VIMENCA': ('80101380', '1'),
        'BANCO LOPEZ DE HARO': ('80101390', '8'),
        'BANCO PROMERICA': ('84405900', '0'),
        'ASOC POPULAR DE AHORROS Y PRE.': ('87940900', '7'),
        'ASOCIACION CIBAO DE A/P': ('88991200', '5'),
        'BANCO BANESCO': ('81102328', '9'),
        'BANCO MULTIPLE ADEMI S A': ('80101300', '5'),
        'ASOC LA NACIONAL': ('80231034', '1'),
        'BANCO MULTIPLE LAFISE': ('81121214', '2'),
        'BANCO ATLANTICO': ('81101012', '4'),
        'BANCO UNION': ('80232423', '0'),
        'BANCO AHORRO Y CREDITO FONDESA': ('83491100', '7'),
        'QIK BANCO DIGITAL DOMINICANO': ('83249841', '2'),
    },
}

BPD_BANK_ALIASES = [
    ('BANCO DE RESERVAS', 'BANCO DE RESERVAS'),
    ('BANRESERVAS', 'BANCO DE RESERVAS'),
    ('BANCO DEL PROGRESO', 'BANCO DEL PROGRESO'),
    ('PROGRESO', 'BANCO DEL PROGRESO'),
    ('SCOTIABANK', 'BANCO SCOTIABANK'),
    ('CITIBANK', 'CITIBANK'),
    ('POPULAR', 'BANCO POPULAR'),
    ('BHD', 'BANCO BHD'),
    ('SANTA CRUZ', 'BANCO SANTA CRUZ'),
    ('CARIBE', 'BANCO CARIBE'),
    ('BDI', 'BANCO BDI'),
    ('VIMENCA', 'BANCO VIMENCA'),
    ('LOPEZ DE HARO', 'BANCO LOPEZ DE HARO'),
    ('PROMERICA', 'BANCO PROMERICA'),
    ('ASOC POPULAR DE AHORROS Y PRE', 'ASOC POPULAR DE AHORROS Y PRE.'),
    ('ASOCIACION CIBAO DE A/P', 'ASOCIACION CIBAO DE A/P'),
    ('CIBAO', 'ASOCIACION CIBAO DE A/P'),
    ('BANESCO', 'BANCO BANESCO'),
    ('ADEMI', 'BANCO MULTIPLE ADEMI S A'),
    ('LA NACIONAL', 'ASOC LA NACIONAL'),
    ('LAFISE', 'BANCO MULTIPLE LAFISE'),
    ('ATLANTICO', 'BANCO ATLANTICO'),
    ('UNION', 'BANCO UNION'),
    ('FONDESA', 'BANCO AHORRO Y CREDITO FONDESA'),
    ('QIK', 'QIK BANCO DIGITAL DOMINICANO'),
    ('BANCO AGRICOLA', 'BANCO AGRICOLA DE LA REPUBLICA'),
]


def remove_accent(word):
    word = word or ''
    for letter, replacement in SPECIALS.items():
        word = word.replace(letter, replacement)
    return word


def normalize_bank_name(name):
    return remove_accent(name).upper().strip()


def resolve_bpd_bank_key(bank_name):
    normalized_name = normalize_bank_name(bank_name)
    for alias, canonical_name in BPD_BANK_ALIASES:
        if alias in normalized_name:
            return canonical_name
    return False


def get_bpd_bank_code_and_digit(bank_name, currency_name):
    bank_key = resolve_bpd_bank_key(bank_name)
    if not bank_key:
        return False, False
    bank_data = BPD_BANK_CODES.get(currency_name, {}).get(bank_key)
    if not bank_data:
        return False, False
    return bank_data


def get_bpd_bank_catalog():
    catalog = []
    canonical_names = sorted(set(BPD_BANK_CODES.get('DOP', {}).keys()) | set(BPD_BANK_CODES.get('USD', {}).keys()))
    for canonical_name in canonical_names:
        aliases = [canonical_name]
        aliases.extend(alias for alias, mapped_name in BPD_BANK_ALIASES if mapped_name == canonical_name)
        dop_code, dop_digit = BPD_BANK_CODES.get('DOP', {}).get(canonical_name, (False, False))
        usd_code, usd_digit = BPD_BANK_CODES.get('USD', {}).get(canonical_name, (False, False))
        catalog.append({
            'name': canonical_name,
            'aliases': aliases,
            'dop_code': dop_code,
            'dop_digit': dop_digit,
            'usd_code': usd_code,
            'usd_digit': usd_digit,
        })
    return catalog
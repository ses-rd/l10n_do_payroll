# -*- coding: utf-8 -*-

from odoo import _
from odoo.exceptions import UserError

from .bpd import generate_bpd_txt


GENERATORS = {
    'BPD': generate_bpd_txt,
}


def generate_data_for_bank(code, obj):
    generator = GENERATORS.get(code)
    if not generator:
        raise UserError(_('No TXT generator is available for bank type %s.') % code)
    return generator(obj)
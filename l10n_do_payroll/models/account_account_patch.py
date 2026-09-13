# -*- coding: utf-8 -*-

from odoo import models, fields


class AccountAccount(models.Model):
    _inherit = 'account.account'

    # Campo legado para compatibilidad con dominios que filtran cuentas "no deprecadas".
    # En Odoo 19 el campo estándar es `active`. Este boolean evita errores de dominio.
    deprecated = fields.Boolean(default=False)

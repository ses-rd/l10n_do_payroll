# -*- coding: utf-8 -*-

from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    payroll_bank_type = fields.Selection([
        ('BPD', 'Banco Popular'),
    ], string='Banco origen formato TXT')
    payroll_email = fields.Char(string='Correo de notificacion nomina')
    payroll_company_bank_code = fields.Char(
        string='Codigo de compania banco origen',
        help='Codigo de 5 posiciones asignado por el banco al archivo de nomina de la cuenta origen.',
    )
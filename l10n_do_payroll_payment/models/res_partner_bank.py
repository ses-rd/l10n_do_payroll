# -*- coding: utf-8 -*-

from odoo import api, fields, models

from odoo.addons.l10n_do_payroll_payment.utils.bank_generators.bpd_catalog import get_bpd_bank_code_and_digit


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    account_type = fields.Selection([
        ('CC', 'Cuenta Corriente'),
        ('CA', 'Cuenta de Ahorro'),
    ], string='Tipo de cuenta', default='CA')
    electronic_payroll_destination_bank_code = fields.Char(
        string='Código ACH banco destino',
        compute='_compute_electronic_payroll_destination_data',
        readonly=True,
    )
    electronic_payroll_destination_bank_digit = fields.Char(
        string='Dígito verificador destino',
        compute='_compute_electronic_payroll_destination_data',
        readonly=True,
    )

    @api.depends(
        'bank_id.electronic_payroll_dop_bank_code',
        'bank_id.electronic_payroll_dop_bank_digit',
        'bank_id.electronic_payroll_usd_bank_code',
        'bank_id.electronic_payroll_usd_bank_digit',
        'currency_id.name',
    )
    def _compute_electronic_payroll_destination_data(self):
        for bank_account in self:
            if not bank_account.bank_id or not bank_account.currency_id:
                bank_account.electronic_payroll_destination_bank_code = False
                bank_account.electronic_payroll_destination_bank_digit = False
                continue

            bank_code, bank_digit = bank_account.bank_id.get_electronic_payroll_bank_code_and_digit(bank_account.currency_id.name)
            if not bank_code:
                bank_code, bank_digit = get_bpd_bank_code_and_digit(
                    bank_account.bank_id.name,
                    bank_account.currency_id.name,
                )
            bank_account.electronic_payroll_destination_bank_code = bank_code or False
            bank_account.electronic_payroll_destination_bank_digit = bank_digit or False

# -*- coding: utf-8 -*-

from odoo import api, fields, models

from odoo.addons.l10n_do_payroll_payment.utils.bank_generators.bpd_catalog import get_bpd_bank_catalog, normalize_bank_name


class ResBank(models.Model):
    _inherit = 'res.bank'

    electronic_payroll_dop_bank_code = fields.Char(string='Codigo ACH DOP')
    electronic_payroll_dop_bank_digit = fields.Char(string='Digito ACH DOP')
    electronic_payroll_usd_bank_code = fields.Char(string='Codigo ACH USD')
    electronic_payroll_usd_bank_digit = fields.Char(string='Digito ACH USD')

    def get_electronic_payroll_bank_code_and_digit(self, currency_name):
        self.ensure_one()
        if currency_name == 'USD':
            return self.electronic_payroll_usd_bank_code or False, self.electronic_payroll_usd_bank_digit or False
        if currency_name == 'DOP':
            return self.electronic_payroll_dop_bank_code or False, self.electronic_payroll_dop_bank_digit or False
        return False, False

    @api.model
    def _load_payroll_bank_catalog(self):
        banks = self.sudo().search([])
        normalized_banks = {normalize_bank_name(bank.name): bank for bank in banks if bank.name}

        for bank_data in get_bpd_bank_catalog():
            bank = None
            for alias in bank_data['aliases']:
                bank = normalized_banks.get(normalize_bank_name(alias))
                if bank:
                    break

            values = {
                'name': bank_data['name'],
                'electronic_payroll_dop_bank_code': bank_data.get('dop_code'),
                'electronic_payroll_dop_bank_digit': bank_data.get('dop_digit'),
                'electronic_payroll_usd_bank_code': bank_data.get('usd_code'),
                'electronic_payroll_usd_bank_digit': bank_data.get('usd_digit'),
            }
            if bank:
                bank.write(values)
                normalized_banks[normalize_bank_name(bank.name)] = bank
            else:
                created_bank = self.sudo().create(values)
                normalized_banks[normalize_bank_name(created_bank.name)] = created_bank
        return True
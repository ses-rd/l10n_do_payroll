# -*- coding: utf-8 -*-

from types import SimpleNamespace

from odoo import _, fields, models
from odoo.exceptions import UserError

from odoo.addons.l10n_do_payroll_payment.utils import generate_data_for_bank
from odoo.addons.l10n_do_payroll_payment.utils.bank_generators.bpd_catalog import resolve_bpd_bank_key


class AccountBatchPayment(models.Model):
    _inherit = 'account.batch.payment'

    payroll_payslip_run_id = fields.Many2one(
        'hr.payslip.run',
        string='Payroll Run',
        readonly=True,
        copy=False,
    )
    payroll_effective_date = fields.Date(
        string='Payroll Effective Date',
        copy=False,
    )
    payroll_description = fields.Char(
        string='Payroll Description',
        copy=False,
    )
    payroll_sequence = fields.Char(
        string='Secuencia TXT mismo banco',
        copy=False,
        readonly=True,
    )
    payroll_other_bank_sequence = fields.Char(
        string='Secuencia TXT otros bancos',
        copy=False,
        readonly=True,
    )
    payroll_bank_type = fields.Selection(
        related='journal_id.payroll_bank_type',
        string='Banco origen formato TXT',
    )
    payroll_origin_email = fields.Char(
        related='journal_id.payroll_email',
        string='Correo de notificacion nomina',
    )
    payroll_origin_company_bank_code = fields.Char(
        related='journal_id.payroll_company_bank_code',
        string='Codigo de compania banco origen',
    )
    payroll_txt_file = fields.Binary(
        string='TXT mismo banco',
        readonly=True,
        copy=False,
    )
    payroll_txt_filename = fields.Char(
        string='Nombre TXT mismo banco',
        readonly=True,
        copy=False,
    )
    payroll_other_bank_txt_file = fields.Binary(
        string='TXT otros bancos',
        readonly=True,
        copy=False,
    )
    payroll_other_bank_txt_filename = fields.Char(
        string='Nombre TXT otros bancos',
        readonly=True,
        copy=False,
    )

    def _get_payroll_payslip_by_payment(self, payment):
        return self.env['hr.payslip'].search([
            ('payroll_payment_ids', 'in', payment.id),
        ], limit=1)

    @staticmethod
    def _get_employee_bank_account(employee, payment=False):
        if payment and payment.partner_bank_id:
            return payment.partner_bank_id
        if not employee:
            return False
        if hasattr(employee, 'primary_bank_account_id') and employee.primary_bank_account_id:
            return employee.primary_bank_account_id
        bank_accounts = employee.bank_account_ids.filtered(lambda bank: bank.allow_out_payment)
        if bank_accounts:
            return bank_accounts.sorted('sequence')[:1]
        return employee.bank_account_ids.sorted('sequence')[:1]

    @staticmethod
    def _get_partner_bank_account(partner, payment=False):
        if payment and payment.partner_bank_id:
            return payment.partner_bank_id
        if not partner:
            return False
        bank_accounts = partner.bank_ids.filtered(lambda bank: getattr(bank, 'allow_out_payment', True))
        if bank_accounts:
            return bank_accounts.sorted('sequence')[:1]
        return partner.bank_ids.sorted('sequence')[:1]

    def _sync_payroll_metadata_from_payments(self):
        self.ensure_one()
        payslips = self.env['hr.payslip']
        for payment in self.payment_ids:
            payslip = self._get_payroll_payslip_by_payment(payment)
            if payslip:
                payslips |= payslip

        if not payslips:
            return self.env['hr.payslip.run']

        payruns = payslips.mapped('payslip_run_id').filtered(lambda run: run)
        if len(payruns) > 1:
            raise UserError(_('This batch payment contains payments from multiple payroll runs.'))

        payrun = payruns[:1]
        values = {}
        if payrun and not self.payroll_payslip_run_id:
            values['payroll_payslip_run_id'] = payrun.id
        if payrun and not self.payroll_effective_date:
            values['payroll_effective_date'] = payrun.date_end
        if payrun and not self.payroll_description:
            values['payroll_description'] = payrun.name
        if values:
            self.write(values)
        return payrun

    def _get_employee_from_payment(self, payment, payslip=False):
        self.ensure_one()
        if payslip:
            return payslip.employee_id
        if not payment.partner_id:
            return self.env['hr.employee']

        employee_model = self.env['hr.employee']
        partner_fields = [
            field_name
            for field_name in ('work_contact_id', 'address_home_id', 'user_partner_id')
            if field_name in employee_model._fields
        ]
        for field_name in partner_fields:
            employee = employee_model.search([(field_name, '=', payment.partner_id.id)], limit=1)
            if employee:
                return employee
        return employee_model

    def _get_payroll_export_lines(self):
        self.ensure_one()
        export_lines = []
        for payment in self.payment_ids.sorted('id'):
            payslip = self._get_payroll_payslip_by_payment(payment)
            employee = self._get_employee_from_payment(payment, payslip=payslip)
            partner = payment.partner_id
            bank_account = self._get_employee_bank_account(employee, payment) or self._get_partner_bank_account(partner, payment)
            export_lines.append(SimpleNamespace(
                employee_id=employee,
                partner_id=partner,
                payment_id=payment,
                amount=abs(payment.amount),
                no_file=False,
                bank_account_id=bank_account,
            ))
        return export_lines

    def _get_effective_payroll_bank_type(self):
        self.ensure_one()
        if self.payroll_bank_type:
            return self.payroll_bank_type

        journal_bank = self.journal_id.bank_account_id.bank_id
        if not journal_bank:
            return False

        if resolve_bpd_bank_key(journal_bank.name) == 'BANCO POPULAR':
            return 'BPD'
        return False

    def _split_payroll_export_lines(self, bank_type, export_lines):
        self.ensure_one()
        if bank_type != 'BPD':
            return export_lines, []

        origin_bank = self.journal_id.bank_account_id.bank_id
        origin_bank_key = resolve_bpd_bank_key(origin_bank.name) if origin_bank else False
        same_bank_lines = []
        other_bank_lines = []

        for line in export_lines:
            bank_account = line.bank_account_id
            destination_bank = bank_account.bank_id if bank_account else False
            destination_bank_key = resolve_bpd_bank_key(destination_bank.name) if destination_bank else False
            if origin_bank_key and destination_bank_key == origin_bank_key:
                same_bank_lines.append(line)
            else:
                other_bank_lines.append(line)

        return same_bank_lines, other_bank_lines

    def _build_payroll_txt_adapter(self, export_lines, sequence):
        self.ensure_one()
        return SimpleNamespace(
            env=self.env,
            company_id=self.company_id,
            journal_id=self.journal_id,
            effective_date=self.payroll_effective_date or self.date or fields.Date.context_today(self),
            create_date=fields.Datetime.now(),
            sequence=sequence,
            line_ids=export_lines,
            description=self.payroll_description or self.payroll_payslip_run_id.name or self.name,
            payslip_run_id=self.payroll_payslip_run_id,
            name=self.name,
        )

    def _validate_payroll_txt_configuration(self):
        self.ensure_one()
        self.payroll_payslip_run_id or self._sync_payroll_metadata_from_payments()
        bank_type = self._get_effective_payroll_bank_type()
        if not self.payment_ids:
            raise UserError(_('The batch payment has no payments to export.'))
        return bank_type or 'BPD'

    def action_generate_payroll_bank_txt(self):
        self.ensure_one()
        bank_type = self._validate_payroll_txt_configuration()

        export_lines = self._get_payroll_export_lines()
        if not export_lines:
            raise UserError(_('No payroll payments linked to payslips were found to export.'))

        same_bank_lines, other_bank_lines = self._split_payroll_export_lines(bank_type, export_lines)
        effective_date = self.payroll_effective_date or self.date or fields.Date.context_today(self)
        description = self.payroll_description or self.payroll_payslip_run_id.name or self.name
        values = {
            'payroll_effective_date': effective_date,
            'payroll_description': description,
            'payroll_txt_file': False,
            'payroll_txt_filename': False,
            'payroll_other_bank_txt_file': False,
            'payroll_other_bank_txt_filename': False,
        }

        if same_bank_lines:
            same_bank_adapter = self._build_payroll_txt_adapter(same_bank_lines, self.payroll_sequence)
            same_bank_txt_file, same_bank_filename = generate_data_for_bank(bank_type, same_bank_adapter)
            values.update({
                'payroll_sequence': same_bank_adapter.sequence,
                'payroll_txt_file': same_bank_txt_file,
                'payroll_txt_filename': same_bank_filename,
            })
        else:
            values['payroll_sequence'] = False

        if other_bank_lines:
            other_bank_adapter = self._build_payroll_txt_adapter(other_bank_lines, self.payroll_other_bank_sequence)
            other_bank_txt_file, other_bank_filename = generate_data_for_bank(bank_type, other_bank_adapter)
            values.update({
                'payroll_other_bank_sequence': other_bank_adapter.sequence,
                'payroll_other_bank_txt_file': other_bank_txt_file,
                'payroll_other_bank_txt_filename': other_bank_filename,
            })
        else:
            values['payroll_other_bank_sequence'] = False

        self.write(values)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.batch.payment',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
        }

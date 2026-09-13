# -*- coding: utf-8 -*-

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_is_zero


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    payroll_payment_ids = fields.Many2many(
        'account.payment',
        'hr_payslip_account_payment_rel',
        'payslip_id',
        'payment_id',
        string='Payroll Payments',
        copy=False,
        readonly=True,
    )

    def _get_payroll_vendor_partner(self):
        self.ensure_one()
        return self.employee_id.work_contact_id or self.employee_id.address_home_id

    def _get_payroll_net_move_lines(self):
        self.ensure_one()
        valid_account_types = ('liability_payable', 'liability_current')
        partner = self._get_payroll_vendor_partner()
        net_amount = abs(self._get_salary_line_total('NET'))
        rounding = self.company_id.currency_id.rounding
        return self.move_id.line_ids.filtered(
            lambda line: (
                line.account_id.account_type in valid_account_types
                and line.account_id.reconcile
                and not line.reconciled
                and line.balance < 0
                and float_is_zero(abs(abs(line.balance) - net_amount), precision_rounding=rounding)
                and (
                    not partner
                    or not line.partner_id
                    or line.partner_id == partner
                )
            )
        )

    def _validate_payroll_payable_setup(self):
        for slip in self:
            partner = slip._get_payroll_vendor_partner()
            if not partner:
                raise UserError(_('The employee %s must have a vendor partner to register payroll payments.') % slip.employee_id.name)
            net_lines = slip._get_payroll_net_move_lines()
            if not net_lines:
                raise UserError(_('The payslip %s has no payable NET line ready to reconcile.') % slip.display_name)

    def _prepare_line_values(self, line, account, date, debit, credit):
        line_values_list = super()._prepare_line_values(line, account, date, debit, credit)
        if account.account_type not in ('liability_payable', 'liability_current') or line.code != 'NET':
            return line_values_list

        partner = self._get_payroll_vendor_partner()
        if not partner:
            return line_values_list

        for line_values in line_values_list:
            if not line_values.get('partner_id'):
                line_values['partner_id'] = partner.id
        return line_values_list

    def _get_single_payroll_run_for_payment(self):
        self.ensure_one()
        payslip_runs = self.payslip_run_id
        if not payslip_runs:
            raise UserError(_('The selected payslip is not linked to a pay run.'))
        return payslip_runs

    def action_register_payroll_payment_from_list(self):
        payslip_runs = self.mapped('payslip_run_id')
        if not payslip_runs:
            raise UserError(_('Select payslips linked to a pay run.'))
        if len(payslip_runs) != 1:
            raise UserError(_('All selected payslips must belong to the same pay run.'))
        return payslip_runs.action_register_payroll_payment()

    def action_open_payroll_batch_payment_from_list(self):
        payslip_runs = self.mapped('payslip_run_id')
        if not payslip_runs:
            raise UserError(_('Select payslips linked to a pay run.'))
        if len(payslip_runs) != 1:
            raise UserError(_('All selected payslips must belong to the same pay run.'))
        return payslip_runs.action_open_payroll_batch_payment()

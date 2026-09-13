# -*- coding: utf-8 -*-

from odoo import Command, _, models
from odoo.exceptions import UserError


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    @staticmethod
    def _get_payroll_partner_from_line(line):
        payslip = line.move_id.payslip_ids[:1]
        if not payslip:
            return line.partner_id
        return payslip.employee_id.work_contact_id or payslip.employee_id.address_home_id or line.partner_id

    def _get_line_batch_key(self, line):
        result = super()._get_line_batch_key(line)
        if self.env.context.get('hr_payroll_payment_register_batch') and not result.get('partner_id'):
            payroll_partner = self._get_payroll_partner_from_line(line)
            if payroll_partner:
                result['partner_id'] = payroll_partner.id
        return result

    def _create_payment_vals_from_batch(self, batch):
        result = super()._create_payment_vals_from_batch(batch)
        if self.env.context.get('hr_payroll_payment_register_batch') and not result.get('partner_id'):
            payroll_partner = self._get_payroll_partner_from_line(batch['lines'][:1])
            if payroll_partner:
                result['partner_id'] = payroll_partner.id
        return result

    def _reconcile_payments(self, to_process, edit_mode=False):
        result = super()._reconcile_payments(to_process, edit_mode=edit_mode)

        payrun_id = self.env.context.get('hr_payroll_payment_register_batch')
        if not payrun_id:
            return result

        payrun = self.env['hr.payslip.run'].browse(payrun_id)
        payments = self.env['account.payment']
        for values in to_process:
            payment = values['payment']
            payslips = values['to_reconcile'].move_id.payslip_ids
            if payslips:
                payslips.write({'payroll_payment_ids': [Command.link(payment.id)]})
            payments |= payment

        if not payments:
            raise UserError(_('No payments were created from this payroll batch.'))

        batch_payment = self.env['account.batch.payment'].create({
            'journal_id': payments[0].journal_id.id,
            'payment_ids': [(4, payment.id, 0) for payment in payments],
            'payment_method_id': payments[0].payment_method_id.id,
            'batch_type': payments[0].payment_type,
            'name': _('%s - Payroll Payments') % payrun.name,
            'payroll_payslip_run_id': payrun.id,
            'payroll_effective_date': payrun.date_end,
            'payroll_description': payrun.name,
        })
        payments.filtered(lambda payment: not payment.is_sent).mark_as_sent()
        payrun.payroll_batch_payment_id = batch_payment.id
        payrun.message_post(body=_('Payroll batch payment created: %s') % batch_payment._get_html_link(title=batch_payment.name))
        return result

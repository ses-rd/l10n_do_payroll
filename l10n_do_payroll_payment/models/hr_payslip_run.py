# -*- coding: utf-8 -*-

from odoo import _, fields, models
from odoo.exceptions import UserError


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    payroll_batch_payment_id = fields.Many2one(
        'account.batch.payment',
        string='Payroll Batch Payment',
        readonly=True,
        copy=False,
    )
    payroll_batch_payment_state = fields.Selection(
        related='payroll_batch_payment_id.state',
        string='Batch Payment State',
    )

    def _get_payroll_payment_lines(self):
        self.ensure_one()
        lines = self.env['account.move.line']
        for slip in self.slip_ids.filtered(lambda slip: slip.state == 'validated'):
            slip._validate_payroll_payable_setup()
            lines |= slip._get_payroll_net_move_lines()
        return lines

    def action_register_payroll_payment(self):
        self.ensure_one()
        if self.payroll_batch_payment_id:
            return self.action_open_payroll_batch_payment()
        if not self.slip_ids:
            raise UserError(_('The pay run has no payslips.'))
        if self.company_id.batch_payroll_move_lines:
            raise UserError(_('Disable Batch Payroll Move Lines to reconcile one payroll payment per employee.'))
        slips = self.slip_ids.filtered(lambda slip: slip.state != 'cancel')
        if not slips:
            raise UserError(_('There are no payslips available to pay in this pay run.'))
        if any(slip.state != 'validated' for slip in slips):
            raise UserError(_('All payslips must be confirmed before registering payroll payments.'))
        if any(not slip.move_id for slip in slips):
            raise UserError(_('All payslips must have an accounting entry before registering payroll payments.'))
        if any(move.state != 'posted' for move in slips.move_id):
            raise UserError(_('All accounting entries must be posted before registering payroll payments.'))

        payment_lines = self._get_payroll_payment_lines()
        if not payment_lines:
            raise UserError(_('No payable payroll lines were found to reconcile.'))

        action = payment_lines.action_register_payment()
        action_context = dict(action.get('context', {}))
        action_context.update({
            'hr_payroll_payment_register': True,
            'hr_payroll_payment_register_batch': self.id,
            'default_group_payment': False,
        })
        action['context'] = action_context
        return action

    def action_open_payroll_batch_payment(self):
        self.ensure_one()
        if not self.payroll_batch_payment_id:
            raise UserError(_('No payment batch is linked to this pay run yet.'))
        return {
            'name': _('Payroll Batch Payment'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.batch.payment',
            'view_mode': 'form',
            'res_id': self.payroll_batch_payment_id.id,
            'context': {'create': False},
        }

# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class HrPayslipWorkedDays(models.Model):
    _inherit = 'hr.payslip.worked_days'

    last_payslip_vacation = fields.Boolean(string="Nomina de Ultima Vacaciones")

    def _l10n_do_should_recompute_from_days(self):
        self.ensure_one()
        payslip = self.payslip_id
        return bool(
            payslip
            and payslip.country_code == 'DO'
            and payslip.struct_id
            and payslip.struct_id.use_worked_day_lines
            and payslip.wage_type != 'hourly'
            and self.code != 'OUT'
            and not self.work_entry_type_id.is_extra_hours
        )

    def _l10n_do_sync_hours_from_days(self):
        precision = 0.0001
        for line in self:
            if not line._l10n_do_should_recompute_from_days():
                continue
            hours_per_day = line.payslip_id._get_worked_day_lines_hours_per_day()
            if not hours_per_day:
                continue
            synced_hours = line.number_of_days * hours_per_day
            if abs((line.number_of_hours or 0.0) - synced_hours) <= precision:
                continue
            super(HrPayslipWorkedDays, line).write({'number_of_hours': synced_hours})

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._l10n_do_sync_hours_from_days()
        records.mapped('payslip_id')._sync_partial_worked_days_from_lines()
        return records

    def write(self, vals):
        result = super().write(vals)
        if {'number_of_days', 'number_of_hours', 'work_entry_type_id'} & set(vals) and not self.env.context.get('l10n_do_skip_manual_attendance_flag'):
            self.mapped('payslip_id').write({'l10n_do_manual_attendance_override': True})
        if 'number_of_days' in vals and 'number_of_hours' not in vals:
            self._l10n_do_sync_hours_from_days()
        if {'number_of_days', 'number_of_hours', 'work_entry_type_id'} & set(vals):
            self.mapped('payslip_id')._sync_partial_worked_days_from_lines()
        return result

    @api.depends(
        'is_paid', 'number_of_days', 'number_of_hours', 'payslip_id', 'payslip_id.struct_id',
        'version_id.wage', 'version_id.hourly_wage', 'version_id.contract_wage', 'payslip_id.sum_worked_hours',
        'work_entry_type_id.amount_rate', 'work_entry_type_id.is_extra_hours'
    )
    def _compute_amount(self):
        super()._compute_amount()
        for worked_days in self:
            if not worked_days._l10n_do_should_recompute_from_days():
                continue
            if worked_days.payslip_id.edited or worked_days.payslip_id.state != 'draft':
                continue
            if not worked_days.version_id or not worked_days.is_paid:
                worked_days.amount = 0
                continue
            hours_per_day = worked_days.payslip_id._get_worked_day_lines_hours_per_day()
            expected_days = worked_days.payslip_id._get_l10n_do_expected_paid_days()
            expected_hours = expected_days * hours_per_day if hours_per_day else 0.0
            if not expected_hours:
                continue
            worked_hours = worked_days.number_of_days * hours_per_day if hours_per_day else worked_days.number_of_hours
            contract_wage = worked_days.version_id.contract_wage or worked_days.version_id.wage
            worked_days.amount = (contract_wage / expected_hours) * worked_hours * worked_days.work_entry_type_id.amount_rate

    @api.onchange('number_of_days')
    def _onchange_number_of_days_sync_hours(self):
        if not self.payslip_id:
            return
        self.payslip_id.l10n_do_manual_attendance_override = True
        if self.payslip_id.wage_type != 'hourly' and not self.work_entry_type_id.is_extra_hours:
            hours_per_day = self.payslip_id._get_worked_day_lines_hours_per_day()
            if hours_per_day:
                self.number_of_hours = self.number_of_days * hours_per_day
        self.payslip_id._sync_partial_worked_days_from_lines()

    @api.onchange('number_of_hours')
    def _onchange_number_of_hours_sync_partial_flag(self):
        if self.payslip_id:
            self.payslip_id.l10n_do_manual_attendance_override = True
            self.payslip_id._sync_partial_worked_days_from_lines()
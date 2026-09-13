# -*- coding: utf-8 -*-

from odoo import models, fields, api


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    income_type = fields.Selection([('1', 'Normal'),
                                    ('2', 'Trabajador ocasional (no fijo)'),
                                    ('3', 'Asalariado por hora o labora tiempo parcial'),
                                    ('4', 'No laboró mes completo por razones varias'),
                                    ('5', 'Salario prorrateado semanal/bisemanal'),
                                    ('6', 'Pensionado antes de la Ley 87-01'),
                                    ('7', 'Exento por Ley de pago al SDSS'),
                                    ], string='Tipo de remuneración')
    loan_ids = fields.One2many(comodel_name='hr.employee.loan', inverse_name='employee_id',
                               string=u"Préstamos")
    names = fields.Char(string="Nombres")
    employee_code = fields.Char(string="Código")
    first_lastname = fields.Char(string="1er. Apellido")
    second_lastname = fields.Char(string="2do. Apellido")

    # Campos del contrato (version) reflejados en empleado para la nueva vista
    codependants = fields.Selection(related='version_id.codependants', inherited=True, readonly=False)
    assurance_amount = fields.Float(related='version_id.assurance_amount', inherited=True, readonly=False)
    deduction_plan = fields.Boolean(related='version_id.deduction_plan', inherited=True, readonly=False)
    deduction_quarter = fields.Selection(related='version_id.deduction_quarter', inherited=True, readonly=False)
    comission_rate = fields.Integer(related='version_id.comission_rate', inherited=True, readonly=False)
    wage_extra_hour = fields.Monetary(related='version_id.wage_extra_hour', inherited=True, readonly=False)
    wage_holidays_hour = fields.Monetary(related='version_id.wage_holidays_hour', inherited=True, readonly=False)
    fixed_loan = fields.Monetary(related='version_id.fixed_loan', inherited=True, readonly=False)
    amount_saved = fields.Monetary(related='version_id.amount_saved', inherited=True, readonly=False)
    deduction_calc_mode = fields.Selection(
        related='version_id.deduction_calc_mode',
        inherited=True,
        readonly=False,
    )
    deduction_calc_period = fields.Selection(
        related='version_id.deduction_calc_period',
        inherited=True,
        readonly=False,
    )

    def get_approved_loans(self):
        # Considerar préstamos en 'approved' y 'to_disburse' para que
        # la deducción FINAN se vea en la nómina donde se desembolsa.
        return self.loan_ids.filtered(lambda loan: loan.state in ('approved', 'to_disburse'))

    @api.model
    def name_search(self, name='', domain=None, operator='ilike', limit=100):
        domain = domain or []
        if not name:
            return super(HrEmployee, self).name_search(name=name, domain=domain, operator=operator, limit=limit)

        search_domain = ['|', ('name', operator, name), ('employee_code', operator, name)] + domain
        recs = self.search(search_domain, limit=limit)
        return [(rec.id, rec.display_name) for rec in recs]

    @api.model
    def convert_to_date(self, dstr):
        return fields.date.fromisoformat(dstr)

# -*- coding: utf-8 -*-

from odoo import models, fields


class HrVersion(models.Model):
    _inherit = 'hr.version'

    codependants = fields.Selection([
        ('none', 'Ninguno'),
        ('1', 'Uno'),
        ('2', 'Dos'),
        ('3', 'Tres')
    ], default='none', string="Dependientes")

    assurance_amount = fields.Float(string="Monto seguro complementario", default=0.0)

    deduction_plan = fields.Boolean(string="Descuento mensual?")

    deduction_quarter = fields.Selection([
        ('first', 'Primera quincena'),
        ('second', 'Segunda quincena')
    ], string="Quincena del descuento")

    comission_rate = fields.Integer(
        string="% de comisión",
        help="Este porcentaje se calculará en base a todas las facturas pagadas en las que el empleado es vendedor.")

    wage_extra_hour = fields.Monetary(string="Pago horas extras")
    wage_holidays_hour = fields.Monetary(string="Pago horas Días Feriados")
    fixed_loan = fields.Monetary(string="Cuota fija quincenal de préstamo")
    amount_saved = fields.Monetary(string="Cuota de ahorro quincenal")

    deduction_calc_mode = fields.Selection([
        ('payment_recurrence', 'Por recurrencia de pago'),
        ('period', 'Por periodo'),
    ], string='Tipo de calculo retencion y deducciones', default='payment_recurrence')

    deduction_calc_period = fields.Selection([
        ('weekly', 'Semanal'),
        ('bi-weekly', 'Quincenal'),
        ('monthly', 'Mensual'),
    ], string='Periodo de deducciones')

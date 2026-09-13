from odoo import models, fields, api


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_do_ars_salary_cap = fields.Monetary(
        string='Tope salarial ARS',
        currency_field='currency_id',
        default=232230.00,
    )
    l10n_do_afp_salary_cap = fields.Monetary(
        string='Tope salarial AFP',
        currency_field='currency_id',
        default=464460.00,
    )
    l10n_do_srl_salary_cap = fields.Monetary(
        string='Tope salarial SRL',
        currency_field='currency_id',
        default=92892.00,
    )

    l10n_do_srl_category = fields.Selection([
        ('1', 'Categoría 1'),
        ('2', 'Categoría 2'),
        ('3', 'Categoría 3'),
        ('4', 'Categoría 4'),
    ], string='Categoría de Riesgo Laboral', default='1')

    l10n_do_srl_rate_cat1 = fields.Float(string='Porcentaje Riesgo Laboral Categoría 1', default=1.10)
    l10n_do_srl_rate_cat2 = fields.Float(string='Porcentaje Riesgo Laboral Categoría 2', default=1.15)
    l10n_do_srl_rate_cat3 = fields.Float(string='Porcentaje Riesgo Laboral Categoría 3', default=1.20)
    l10n_do_srl_rate_cat4 = fields.Float(string='Porcentaje Riesgo Laboral Categoría 4', default=1.30)

    l10n_do_srl_rate = fields.Float(string='Porcentaje SRL aplicado', compute='_compute_l10n_do_srl_rate', store=True)

    @api.depends('l10n_do_srl_category', 'l10n_do_srl_rate_cat1', 'l10n_do_srl_rate_cat2', 'l10n_do_srl_rate_cat3', 'l10n_do_srl_rate_cat4')
    def _compute_l10n_do_srl_rate(self):
        for company in self:
            rate_map = {
                '1': company.l10n_do_srl_rate_cat1,
                '2': company.l10n_do_srl_rate_cat2,
                '3': company.l10n_do_srl_rate_cat3,
                '4': company.l10n_do_srl_rate_cat4,
            }
            company.l10n_do_srl_rate = rate_map.get(company.l10n_do_srl_category or '1', company.l10n_do_srl_rate_cat1)

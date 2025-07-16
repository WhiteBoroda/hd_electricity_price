# -*- coding: utf-8 -*-
# Модель для відображення країн Odoo на домени ENTSO-E API

from odoo import fields, models, api

class ElectricityEntsoeDomain(models.Model):
    _name = 'electricity.entsoe.domain'
    _description = 'ENTSO-E Bidding Zone Domain Mapping'
    _order = 'name asc'

    name = fields.Char(string='Назва домену', required=True, help="Назва торговельної зони або домену ENTSO-E")
    domain_code = fields.Char(string='Код домену ENTSO-E', required=True, help="Унікальний код домену, що використовується в API ENTSO-E (наприклад, 10YCZ-CEPS--N)")
    country_id = fields.Many2one('res.country', string='Країна Odoo', required=True, help="Відповідна країна в системі Odoo")

    _sql_constraints = [
        ('domain_code_unique', 'unique(domain_code)', 'Код домену ENTSO-E повинен бути унікальним!'),
        ('country_domain_unique', 'unique(country_id)', 'Кожна країна Odoo може бути пов’язана лише з одним доменом ENTSO-E!'),
    ]

    @api.depends('name', 'domain_code')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.name} ({record.domain_code})"

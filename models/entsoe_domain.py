# -*- coding: utf-8 -*-
from odoo import fields, models, api

class ElectricityEntsoeDomain(models.Model):
    _name = 'electricity.entsoe.domain'
    _description = 'ENTSO-E Bidding Zone Domain Mapping'
    _order = 'name asc'

    name = fields.Char(
        string='Назва домену',
        required=True,
        help="Назва торговельної зони або домену ENTSO-E"
    )
    domain_code = fields.Char(
        string='Код домену ENTSO-E',
        required=True,
        help="Унікальний код домену, що використовується в API ENTSO-E (наприклад, 10YCZ-CEPS--N)"
    )
    country_id = fields.Many2one(
        'res.country',
        string='Країна Odoo',
        required=True,
        help="Відповідна країна в системі Odoo"
    )

    _sql_constraints = [
        ('domain_code_unique', 'unique(domain_code)', 'Код домену ENTSO-E повинен бути унікальним!'),
        ('country_domain_unique', 'unique(country_id)', 'Кожна країна Odoo може бути пов\'язана лише з одним доменом ENTSO-E!'),
    ]

    def name_get(self):
        result = []
        for record in self:
            result.append((record.id, f"{record.name} ({record.domain_code})"))
        return result
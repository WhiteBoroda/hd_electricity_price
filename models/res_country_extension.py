# -*- coding: utf-8 -*-
from odoo import fields, models

class ResCountry(models.Model):
    _inherit = 'res.country'

    entsoe_domain_id = fields.Many2one(
        'electricity.entsoe.domain',
        string='Домен ENTSO-E',
        help="Домен ENTSO-E, пов'язаний з цією країною для запитів цін на електроенергію."
    )
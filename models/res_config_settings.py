# -*- coding: utf-8 -*-
# Налаштування модуля

from odoo import fields, models, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    entsoe_api_base_url = fields.Char(
        string="Базовий URL API ENTSO-E",
        config_parameter='odoo_electricity_price.entsoe_api_base_url',
        default='https://transparency.entsoe.eu/api',
        help="Базовий URL для запитів до ENTSO-E Transparency Platform API."
    )
    entsoe_api_token = fields.Char(
        string="Токен безпеки API ENTSO-E",
        config_parameter='odoo_electricity_price.entsoe_api_token',
        help="Ваш персональний токен безпеки для доступу до API ENTSO-E. Отримайте його на сайті ENTSO-E."
    )

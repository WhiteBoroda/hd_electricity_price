# -*- coding: utf-8 -*-
# Модель для зберігання цін на електроенергію та логіка API-інтеграції

from odoo import fields, models, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import requests
import xml.etree.ElementTree as ET
import logging

_logger = logging.getLogger(__name__)

class ElectricityPriceRdn(models.Model):
    _name = 'electricity.price.rdn'
    _description = 'Ціна Електроенергії РДН'
    _order = 'price_date desc, hour asc'

    country_id = fields.Many2one('res.country', string='Країна', required=True, help="Країна, для якої завантажено ціну")
    
    # Змінено з related на обчислюване поле (computed field)
    entsoe_domain_id = fields.Many2one(
        'electricity.entsoe.domain',
        string='Домен ENTSO-E',
        compute='_compute_entsoe_domain_id', # Вказуємо метод для обчислення
        store=True, # Зберігати обчислене значення в базі даних
        readonly=True, # Поле буде тільки для читання
        help="Домен ENTSO-E, що обчислюється на основі обраної країни."
    )
    
    price_date = fields.Date(string='Дата', required=True, help="Дата, до якої відноситься ціна")
    hour = fields.Integer(string='Година', required=True, help="Година (0-23) за місцевим часом домену")
    price = fields.Float(string='Ціна (EUR/MWh)', required=True, digits=(10, 4), help="Ціна електроенергії за мегават-годину")
    api_response_raw = fields.Text(string='Сира відповідь API', readonly=True, help="Сира XML-відповідь від API для перевірки")

    _sql_constraints = [
        ('unique_price_per_hour', 'unique(country_id, price_date, hour)', 'Ціна для цієї країни, дати та години вже існує!'),
    ]

    # Метод для обчислення значення entsoe_domain_id
    @api.depends('country_id') # Цей метод буде викликатися при зміні country_id
    def _compute_entsoe_domain_id(self):
        for record in self:
            if record.country_id and record.country_id.entsoe_domain_id:
                record.entsoe_domain_id = record.country_id.entsoe_domain_id
            else:
                record.entsoe_domain_id = False

    @api.model
    def _cron_fetch_daily_prices(self):
        # ... (решта коду залишається без змін) ...
        pass

    @api.model
    def _fetch_and_store_prices(self, country_id, target_date):
        # ... (решта коду залишається без змін) ...
        pass

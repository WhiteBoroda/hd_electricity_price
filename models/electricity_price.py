# -*- coding: utf-8 -*-
import logging
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from odoo import fields, models, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ElectricityPriceRdn(models.Model):
    _name = 'electricity.price.rdn'
    _description = 'Ціна Електроенергії РДН'
    _order = 'price_date desc, hour asc'

    country_id = fields.Many2one(
        'res.country',
        string='Країна',
        required=True,
        help="Країна, для якої завантажено ціну"
    )
    entsoe_domain_id = fields.Many2one(
        'electricity.entsoe.domain',
        string='Домен ENTSO-E',
        compute='_compute_entsoe_domain_id',
        store=True,
        readonly=True,
        help="Домен ENTSO-E, що обчислюється на основі обраної країни."
    )
    price_date = fields.Date(
        string='Дата',
        required=True,
        help="Дата, до якої відноситься ціна"
    )
    hour = fields.Integer(
        string='Година',
        required=True,
        help="Година (0-23) за місцевим часом домену"
    )
    price = fields.Float(
        string='Ціна (EUR/MWh)',
        required=True,
        digits=(10, 4),
        help="Ціна електроенергії за мегават-годину"
    )
    api_response_raw = fields.Text(
        string='Сира відповідь API',
        readonly=True,
        help="Сира XML-відповідь від API для перевірки"
    )

    _sql_constraints = [
        ('unique_price_per_hour', 'unique(country_id, price_date, hour)',
         'Ціна для цієї країни, дати та години вже існує!'),
        ('hour_range_check', 'CHECK(hour >= 0 AND hour <= 23)',
         'Година повинна бути в діапазоні від 0 до 23!'),
    ]

    @api.depends('country_id')
    def _compute_entsoe_domain_id(self):
        for record in self:
            if record.country_id and record.country_id.entsoe_domain_id:
                record.entsoe_domain_id = record.country_id.entsoe_domain_id
            else:
                record.entsoe_domain_id = False

    @api.model
    def _get_api_config(self):
        """Отримати налаштування API з конфігурації"""
        ICPSudo = self.env['ir.config_parameter'].sudo()
        base_url = ICPSudo.get_param('hd_electricity_price.entsoe_api_base_url',
                                     'https://transparency.entsoe.eu/api')
        token = ICPSudo.get_param('hd_electricity_price.entsoe_api_token')

        if not token:
            raise UserError(_("API токен ENTSO-E не налаштований. Будь ласка, налаштуйте його в Налаштуваннях модуля."))

        return base_url, token

    @api.model
    def _fetch_price_data_from_api(self, domain_code, target_date):
        """Завантажити дані про ціни з API ENTSO-E"""
        base_url, token = self._get_api_config()

        # Формуємо дати для запиту (потрібен день + 1 день для повного покриття)
        start_time = target_date.strftime('%Y%m%d0000')
        end_time = (target_date + timedelta(days=1)).strftime('%Y%m%d0000')

        params = {
            'securityToken': token,
            'documentType': 'A44',  # Day-ahead prices
            'in_Domain': domain_code,
            'out_Domain': domain_code,
            'periodStart': start_time,
            'periodEnd': end_time,
        }

        try:
            _logger.info(f"Запит до ENTSO-E API для домену {domain_code}, дата {target_date}")
            response = requests.get(base_url, params=params, timeout=30)
            response.raise_for_status()

            if response.status_code == 200:
                return response.text
            else:
                raise UserError(_(f"API повернув код помилки: {response.status_code}"))

        except requests.exceptions.RequestException as e:
            _logger.error(f"Помилка при запиті до API: {e}")
            raise UserError(_(f"Не вдалося з'єднатися з API ENTSO-E: {e}"))

    @api.model
    def _parse_xml_response(self, xml_data, target_date):
        """Парсити XML відповідь від API"""
        try:
            root = ET.fromstring(xml_data)

            # Namespace для ENTSO-E XML
            namespaces = {
                'ns': 'urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:0'
            }

            prices_data = []

            # Знаходимо всі TimeSeries
            for timeseries in root.findall('.//ns:TimeSeries', namespaces):
                period = timeseries.find('.//ns:Period', namespaces)
                if period is None:
                    continue

                # Отримуємо початкову дату періоду
                start_elem = period.find('ns:timeInterval/ns:start', namespaces)
                if start_elem is None:
                    continue

                start_time_str = start_elem.text
                # Формат: 2023-12-07T23:00Z
                start_time = datetime.strptime(start_time_str[:19], '%Y-%m-%dT%H:%M')

                # Обробляємо всі точки у періоді
                for point in period.findall('.//ns:Point', namespaces):
                    position_elem = point.find('ns:position', namespaces)
                    price_elem = point.find('ns:price.amount', namespaces)

                    if position_elem is None or price_elem is None:
                        continue

                    position = int(position_elem.text)
                    price = float(price_elem.text)

                    # Обчислюємо час для цієї позиції (position починається з 1)
                    point_time = start_time + timedelta(hours=position - 1)

                    # Перевіряємо, чи це потрібна нам дата
                    if point_time.date() == target_date:
                        prices_data.append({
                            'hour': point_time.hour,
                            'price': price,
                            'datetime': point_time
                        })

            if not prices_data:
                _logger.warning(f"Не знайдено даних про ціни для дати {target_date}")

            return prices_data

        except ET.ParseError as e:
            _logger.error(f"Помилка парсингу XML: {e}")
            raise UserError(_(f"Помилка обробки відповіді від API: {e}"))
        except Exception as e:
            _logger.error(f"Неочікувана помилка при парсингу: {e}")
            raise UserError(_(f"Неочікувана помилка при обробці даних: {e}"))

    @api.model
    def _fetch_and_store_prices(self, country_id, target_date):
        """Завантажити та зберегти ціни для певної країни та дати"""
        country = self.env['res.country'].browse(country_id)
        if not country.exists():
            raise UserError(_("Країну не знайдено"))

        if not country.entsoe_domain_id:
            raise UserError(_(f"Для країни {country.name} не налаштований домен ENTSO-E"))

        domain_code = country.entsoe_domain_id.domain_code

        # Перевіряємо, чи вже є дані для цієї дати
        existing_records = self.search([
            ('country_id', '=', country_id),
            ('price_date', '=', target_date)
        ])

        if existing_records:
            _logger.info(f"Дані для {country.name} на {target_date} вже існують, пропускаємо")
            return len(existing_records)

        # Завантажуємо дані з API
        xml_response = self._fetch_price_data_from_api(domain_code, target_date)
        prices_data = self._parse_xml_response(xml_response, target_date)

        if not prices_data:
            raise UserError(_(f"Не отримано даних про ціни для {country.name} на {target_date}"))

        # Зберігаємо дані
        created_count = 0
        for price_data in prices_data:
            try:
                self.create({
                    'country_id': country_id,
                    'price_date': target_date,
                    'hour': price_data['hour'],
                    'price': price_data['price'],
                    'api_response_raw': xml_response if created_count == 0 else False,
                    # Зберігаємо сиру відповідь тільки для першого запису
                })
                created_count += 1
            except Exception as e:
                _logger.error(f"Помилка збереження ціни для години {price_data['hour']}: {e}")

        _logger.info(f"Збережено {created_count} записів цін для {country.name} на {target_date}")
        return created_count

    @api.model
    def _cron_fetch_daily_prices(self):
        """Cron job для щоденного завантаження цін"""
        _logger.info("Запуск щоденного завантаження цін на електроенергію")

        # Отримуємо всі країни з налаштованими доменами ENTSO-E
        countries = self.env['res.country'].search([
            ('entsoe_domain_id', '!=', False)
        ])

        if not countries:
            _logger.warning("Не знайдено країн з налаштованими доменами ENTSO-E")
            return

        # Завантажуємо дані для попереднього дня (зазвичай дані доступні наступного дня)
        target_date = fields.Date.today() - timedelta(days=1)

        total_created = 0
        for country in countries:
            try:
                created = self._fetch_and_store_prices(country.id, target_date)
                total_created += created
                _logger.info(f"Завантажено {created} записів для {country.name}")
            except Exception as e:
                _logger.error(f"Помилка завантаження для {country.name}: {e}")

        _logger.info(f"Щоденне завантаження завершено. Всього створено записів: {total_created}")
        return total_created
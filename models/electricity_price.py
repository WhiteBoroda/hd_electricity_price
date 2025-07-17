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

    country_id = fields.Many2one('res.country', string='Країна', required=True,
                                 help="Країна, для якої завантажено ціну")

    # Змінено з related на обчислюване поле (computed field)
    entsoe_domain_id = fields.Many2one(
        'electricity.entsoe.domain',
        string='Домен ENTSO-E',
        compute='_compute_entsoe_domain_id',  # Вказуємо метод для обчислення
        store=True,  # Зберігати обчислене значення в базі даних
        readonly=True,  # Поле буде тільки для читання
        help="Домен ENTSO-E, що обчислюється на основі обраної країни."
    )

    price_date = fields.Date(string='Дата', required=True, help="Дата, до якої відноситься ціна")
    hour = fields.Integer(string='Година', required=True, help="Година (0-23) за місцевим часом домену")
    price = fields.Float(string='Ціна (EUR/MWh)', required=True, digits=(10, 4),
                         help="Ціна електроенергії за мегават-годину")
    api_response_raw = fields.Text(string='Сира відповідь API', readonly=True,
                                   help="Сира XML-відповідь від API для перевірки")

    _sql_constraints = [
        ('unique_price_per_hour', 'unique(country_id, price_date, hour)',
         'Ціна для цієї країни, дати та години вже існує!'),
    ]

    # Метод для обчислення значення entsoe_domain_id
    @api.depends('country_id')  # Цей метод буде викликатися при зміні country_id
    def _compute_entsoe_domain_id(self):
        for record in self:
            if record.country_id and record.country_id.entsoe_domain_id:
                record.entsoe_domain_id = record.country_id.entsoe_domain_id
            else:
                record.entsoe_domain_id = False

    @api.model
    def _cron_fetch_daily_prices(self):
        """
        Автоматичне завантаження цін для всіх країн з налаштованими доменами ENTSO-E.
        Викликається за розкладом.
        """
        _logger.info("Початок автоматичного завантаження цін на електроенергію")

        # Отримання всіх країн з налаштованими доменами ENTSO-E
        countries_with_domains = self.env['res.country'].search([
            ('entsoe_domain_id', '!=', False)
        ])

        if not countries_with_domains:
            _logger.warning("Не знайдено країн з налаштованими доменами ENTSO-E")
            return

        # Завантаження цін для вчорашнього дня (дані зазвичай доступні наступного дня)
        target_date = fields.Date.today() - timedelta(days=1)

        success_count = 0
        error_count = 0

        for country in countries_with_domains:
            try:
                self._fetch_and_store_prices(country.id, target_date)
                success_count += 1
                _logger.info(f"Успішно завантажено ціни для {country.name} на {target_date}")
            except Exception as e:
                error_count += 1
                _logger.error(f"Помилка завантаження цін для {country.name} на {target_date}: {e}")

        _logger.info(f"Завершено автоматичне завантаження. Успішно: {success_count}, Помилок: {error_count}")

    @api.model
    def _fetch_and_store_prices(self, country_id, target_date):
        """
        Завантаження та збереження цін для конкретної країни та дати.

        :param country_id: ID країни
        :param target_date: Дата для завантаження (date object)
        """
        # Отримання країни та її домену ENTSO-E
        country = self.env['res.country'].browse(country_id)
        if not country.exists():
            raise UserError(_("Країна не знайдена"))

        if not country.entsoe_domain_id:
            raise UserError(_("Для країни %s не налаштовано домен ENTSO-E") % country.name)

        domain_code = country.entsoe_domain_id.domain_code

        # Отримання налаштувань API
        api_base_url = self.env['ir.config_parameter'].sudo().get_param(
            'hd_electricity_price.entsoe_api_base_url',
            'https://web-api.tp.entsoe.eu/api'
        )
        api_token = self.env['ir.config_parameter'].sudo().get_param(
            'hd_electricity_price.entsoe_api_token'
        )

        if not api_token:
            raise UserError(_("Не налаштовано токен API ENTSO-E. Перейдіть до Налаштування модуля."))

        # Підготовка параметрів запиту для Day Ahead Prices
        # Формат: YYYYMMDDHHMM для періодів
        # Запитуємо повний день (00:00 - 23:59)
        period_start = target_date.strftime('%Y%m%d') + '0000'
        period_end = target_date.strftime('%Y%m%d') + '2300'

        params = {
            'securityToken': api_token,
            'documentType': 'A44',  # Price Document (Day Ahead Prices)
            'in_Domain': domain_code,
            'out_Domain': domain_code,
            'periodStart': period_start,
            'periodEnd': period_end,
        }

        _logger.info(f"Запит до ENTSO-E API для домену {domain_code}, дата {target_date}")
        _logger.info(f"Параметри: {params}")

        try:
            # Виконання HTTP запиту
            response = requests.get(api_base_url, params=params, timeout=30)
            response.raise_for_status()

            # Перевірка чи отримали XML
            if not response.text.strip():
                raise UserError(_("Отримано порожню відповідь від API"))

            _logger.info(f"Отримано відповідь API: {response.text[:500]}...")

            # Парсинг XML відповіді
            try:
                root = ET.fromstring(response.text)
            except ET.ParseError as e:
                _logger.error(f"Помилка парсингу XML: {e}")
                _logger.error(f"XML відповідь: {response.text[:1000]}...")
                raise UserError(_("Неправильний формат XML у відповіді API"))

            # Парсинг та збереження цін
            prices_saved = self._parse_and_save_prices(root, country_id, target_date, response.text)

            if prices_saved == 0:
                _logger.warning(f"Не знайдено даних про ціни для дати {target_date}")
                raise UserError(_("Не отримано даних про ціни для %s на %s") % (country.name, target_date))

            _logger.info(f"Збережено {prices_saved} записів цін для {country.name} на {target_date}")

        except requests.exceptions.RequestException as e:
            _logger.error(f"Помилка HTTP запиту: {e}")
            raise UserError(_("Помилка з'єднання з API ENTSO-E: %s") % str(e))

    def _parse_and_save_prices(self, xml_root, country_id, target_date, raw_response):
        """
        Парсинг XML відповіді та збереження цін у базі даних.

        :param xml_root: Корінь XML дерева
        :param country_id: ID країни
        :param target_date: Дата (date object)
        :param raw_response: Сира XML відповідь для збереження
        :return: Кількість збережених записів
        """
        prices_saved = 0

        # Namespace для ENTSO-E XML
        ns = {'ns': 'urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3'}

        # Знаходження всіх TimeSeries
        timeseries_list = xml_root.findall('ns:TimeSeries', ns)

        if not timeseries_list:
            _logger.warning("Не знайдено жодного TimeSeries у XML відповіді")
            return 0

        _logger.info(f"Знайдено {len(timeseries_list)} TimeSeries в XML")

        for ts_index, timeseries in enumerate(timeseries_list):
            _logger.info(f"Обробка TimeSeries {ts_index + 1}")

            # Отримання інформації про період
            period = timeseries.find('ns:Period', ns)
            if period is None:
                _logger.warning(f"TimeSeries {ts_index + 1}: Period не знайдено")
                continue

            # Парсинг дати початку періоду
            time_interval = period.find('ns:timeInterval', ns)
            if time_interval is None:
                _logger.warning(f"TimeSeries {ts_index + 1}: timeInterval не знайдено")
                continue

            start_time_elem = time_interval.find('ns:start', ns)
            if start_time_elem is None:
                _logger.warning(f"TimeSeries {ts_index + 1}: start time не знайдено")
                continue

            start_time_str = start_time_elem.text
            _logger.info(f"TimeSeries {ts_index + 1}: початок періоду {start_time_str}")

            # Конвертація UTC часу в дату
            try:
                # Формат: 2025-07-14T22:00Z або 2025-07-15T22:00:00Z
                if start_time_str.endswith('Z'):
                    if '.' in start_time_str:
                        # Формат з мікросекундами
                        start_datetime_utc = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M:%S.%fZ')
                    elif start_time_str.count(':') == 2:
                        # Формат з секундами
                        start_datetime_utc = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%M:%SZ')
                    else:
                        # Формат без секунд
                        start_datetime_utc = datetime.strptime(start_time_str, '%Y-%m-%dT%H:%MZ')
                else:
                    raise ValueError(f"Несподіваний формат часу: {start_time_str}")

                _logger.info(f"TimeSeries {ts_index + 1}: UTC час початку {start_datetime_utc}")

            except ValueError as e:
                _logger.error(f"TimeSeries {ts_index + 1}: Помилка парсингу дати початку періоду: {e}")
                continue

            # Отримання всіх точок цін
            points = period.findall('ns:Point', ns)
            _logger.info(f"TimeSeries {ts_index + 1}: знайдено {len(points)} точок")

            for point in points:
                try:
                    position_elem = point.find('ns:position', ns)
                    price_elem = point.find('ns:price.amount', ns)

                    if position_elem is None or price_elem is None:
                        _logger.warning(f"TimeSeries {ts_index + 1}: Пропущено точку - відсутній position або price")
                        continue

                    # Перевірка на валідність даних
                    position_text = position_elem.text
                    price_text = price_elem.text

                    if not position_text or not price_text:
                        _logger.warning(
                            f"TimeSeries {ts_index + 1}: Порожні значення position='{position_text}' або price='{price_text}'")
                        continue

                    try:
                        position = int(position_text.strip())
                        price = float(price_text.strip())
                    except (ValueError, TypeError) as conv_error:
                        _logger.error(
                            f"TimeSeries {ts_index + 1}: Помилка конвертації position='{position_text}' або price='{price_text}': {conv_error}")
                        continue

                    # Перевірка розумності значень
                    if position < 1 or position > 24:
                        _logger.warning(f"TimeSeries {ts_index + 1}: Неправильна позиція {position}, пропускаємо")
                        continue

                    if price < 0:
                        _logger.warning(f"TimeSeries {ts_index + 1}: Негативна ціна {price}, пропускаємо")
                        continue

                    # Position 1 відповідає першій годині періоду
                    # Час точки = час початку + (position - 1) годин
                    point_datetime_utc = start_datetime_utc + timedelta(hours=position - 1)

                    # Для Румынії потрібно конвертувати UTC в місцевий час
                    # Румунія: UTC+2 (зимовий час) або UTC+3 (літній час)
                    # Спрощуємо: використовуємо UTC+2 як базу
                    # В реальному проекті краще використовувати pytz
                    local_offset = 2  # Часова зона Румунії UTC+2/+3
                    point_datetime_local = point_datetime_utc + timedelta(hours=local_offset)

                    point_date = point_datetime_local.date()
                    local_hour = point_datetime_local.hour

                    _logger.debug(
                        f"Position {position}: UTC {point_datetime_utc} -> Local {point_datetime_local} (дата {point_date}, година {local_hour}), ціна {price}")

                    # Перевіряємо чи цей час відповідає цільовій даті
                    if point_date != target_date:
                        _logger.debug(f"Пропускаємо дату {point_date}, очікуємо {target_date}")
                        continue

                    # Додаткова перевірка на валідність години
                    if local_hour < 0 or local_hour > 23:
                        _logger.warning(f"TimeSeries {ts_index + 1}: Неправильна година {local_hour}, пропускаємо")
                        continue

                    # Перевірка чи запис вже існує
                    existing_record = self.search([
                        ('country_id', '=', country_id),
                        ('price_date', '=', point_date),
                        ('hour', '=', local_hour)
                    ])

                    # Підготовка даних для збереження
                    record_data = {
                        'price': price,
                        'api_response_raw': raw_response
                    }

                    if existing_record:
                        # Оновлення існуючого запису
                        existing_record.write(record_data)
                        _logger.debug(f"Оновлено запис для {point_date} {local_hour}:00, ціна {price}")
                    else:
                        # Створення нового запису
                        record_data.update({
                            'country_id': country_id,
                            'price_date': point_date,
                            'hour': local_hour,
                        })

                        # Додаткова перевірка перед створенням
                        if all(v is not None for v in [country_id, point_date, local_hour, price]):
                            self.create(record_data)
                            _logger.debug(f"Створено запис для {point_date} {local_hour}:00, ціна {price}")
                        else:
                            _logger.error(
                                f"Не вдається створити запис - None значення: country_id={country_id}, date={point_date}, hour={local_hour}, price={price}")
                            continue

                    prices_saved += 1

                except Exception as e:
                    _logger.error(
                        f"TimeSeries {ts_index + 1}: Помилка обробки точки position={position_text if 'position_text' in locals() else 'N/A'}: {e}")
                    continue

        _logger.info(f"Загалом збережено {prices_saved} записів цін")
        return prices_saved
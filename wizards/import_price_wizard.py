# -*- coding: utf-8 -*-
# Майстер для ручного імпорту цін

from odoo import fields, models, api, _
from odoo.exceptions import UserError

class ImportElectricityPriceWizard(models.TransientModel):
    _name = 'electricity.price.import.wizard'
    _description = 'Майстер імпорту цін на електроенергію'

    country_id = fields.Many2one('res.country', string='Країна', required=True, help="Оберіть країну, для якої потрібно імпортувати ціни.")
    import_date = fields.Date(string='Дата імпорту', required=True, default=fields.Date.today(), help="Оберіть дату, для якої потрібно завантажити ціни.")

    def action_import_prices(self):
        """
        Запускає імпорт цін для обраної країни та дати.
        """
        self.ensure_one()
        if not self.country_id or not self.import_date:
            raise UserError(_("Будь ласка, оберіть країну та дату для імпорту."))

        try:
            self.env['electricity.price.rdn']._fetch_and_store_prices(self.country_id.id, self.import_date)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Успіх!'),
                    'message': _('Ціни на електроенергію успішно імпортовано.'),
                    'type': 'success',
                    'sticky': False,
                }
            }
        except UserError as e:
            raise e
        except Exception as e:
            raise UserError(_(f"Не вдалося імпортувати ціни: {e}"))

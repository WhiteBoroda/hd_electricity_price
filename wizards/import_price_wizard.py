# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import UserError


class ImportElectricityPriceWizard(models.TransientModel):
    _name = 'electricity.price.import.wizard'
    _description = 'Майстер імпорту цін на електроенергію'

    country_id = fields.Many2one(
        'res.country',
        string='Країна',
        required=True,
        domain=[('entsoe_domain_id', '!=', False)],
        help="Оберіть країну, для якої потрібно імпортувати ціни."
    )
    import_date = fields.Date(
        string='Дата імпорту',
        required=True,
        default=fields.Date.today(),
        help="Оберіть дату, для якої потрібно завантажити ціни."
    )

    @api.onchange('country_id')
    def _onchange_country_id(self):
        if self.country_id and not self.country_id.entsoe_domain_id:
            return {
                'warning': {
                    'title': _('Увага!'),
                    'message': _(
                        'Для обраної країни не налаштований домен ENTSO-E. Будь ласка, оберіть іншу країну або налаштуйте домен.')
                }
            }

    def action_import_prices(self):
        """Запускає імпорт цін для обраної країни та дати"""
        self.ensure_one()

        if not self.country_id or not self.import_date:
            raise UserError(_("Будь ласка, оберіть країну та дату для імпорту."))

        if not self.country_id.entsoe_domain_id:
            raise UserError(_("Для обраної країни не налаштований домен ENTSO-E."))

        try:
            created_count = self.env['electricity.price.rdn']._fetch_and_store_prices(
                self.country_id.id,
                self.import_date
            )

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Успіх!'),
                    'message': _('Успішно імпортовано %d записів цін на електроенергію.') % created_count,
                    'type': 'success',
                    'sticky': False,
                }
            }
        except UserError as e:
            raise e
        except Exception as e:
            raise UserError(_("Не вдалося імпортувати ціни: %s") % str(e))
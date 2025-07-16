# -*- coding: utf-8 -*-
# Метадані модуля Odoo

{
    'name': "Ціни на Електроенергію РДН",
    'summary': """Модуль для збору даних про ціну електроенергії на ринку РДН з Transparency Platform.""",
    'description': """
        Цей модуль дозволяє автоматично та вручну завантажувати дані про ціну електроенергії
        з Transparency Platform Restful API (ENTSO-E) для різних країн.
        Дані зберігаються з унікальною ідентифікацією за роком, місяцем, днем та годиною.
    """,
    'author': "Ярослав Гришин",
    'website': "http://www.hlibodar.com.ua",
    'category': 'Custom/Electricity',
    'version': '1.0',
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/entsoe_domain_views.xml', 
        'views/electricity_price_views.xml',  
        'views/res_country_views.xml',
        'views/res_config_settings_views.xml',  
        'views/menus.xml',
        'wizards/import_price_wizard_views.xml',
       
    ],
    'images': ['static/descriptions/icon.png'],
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
    'auto_install': False,
}
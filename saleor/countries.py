#coding: utf-8

from django.utils.translation import ugettext_lazy
from django.utils.importlib import import_module
from django.conf import settings

DEFAULT_COUNTRY_CHOICES = (
    ('AF', ugettext_lazy(u'Afghanistan')),
    ('AX', ugettext_lazy(u'Åland Islands')),
    ('AL', ugettext_lazy(u'Albania')),
    ('DZ', ugettext_lazy(u'Algeria')),
    ('AS', ugettext_lazy(u'American Samoa')),
    ('AD', ugettext_lazy(u'Andorra')),
    ('AO', ugettext_lazy(u'Angola')),
    ('AI', ugettext_lazy(u'Anguilla')),
    ('AQ', ugettext_lazy(u'Antarctica')),
    ('AG', ugettext_lazy(u'Antigua And Barbuda')),
    ('AR', ugettext_lazy(u'Argentina')),
    ('AM', ugettext_lazy(u'Armenia')),
    ('AW', ugettext_lazy(u'Aruba')),
    ('AU', ugettext_lazy(u'Australia')),
    ('AT', ugettext_lazy(u'Austria')),
    ('AZ', ugettext_lazy(u'Azerbaijan')),
    ('BS', ugettext_lazy(u'Bahamas')),
    ('BH', ugettext_lazy(u'Bahrain')),
    ('BD', ugettext_lazy(u'Bangladesh')),
    ('BB', ugettext_lazy(u'Barbados')),
    ('BY', ugettext_lazy(u'Belarus')),
    ('BE', ugettext_lazy(u'Belgium')),
    ('BZ', ugettext_lazy(u'Belize')),
    ('BJ', ugettext_lazy(u'Benin')),
    ('BM', ugettext_lazy(u'Bermuda')),
    ('BT', ugettext_lazy(u'Bhutan')),
    ('BO', ugettext_lazy(u'Bolivia')),
    ('BQ', ugettext_lazy(u'Bonaire, Saint Eustatius And Saba')),
    ('BA', ugettext_lazy(u'Bosnia And Herzegovina')),
    ('BW', ugettext_lazy(u'Botswana')),
    ('BV', ugettext_lazy(u'Bouvet Island')),
    ('BR', ugettext_lazy(u'Brazil')),
    ('IO', ugettext_lazy(u'British Indian Ocean Territory')),
    ('BN', ugettext_lazy(u'Brunei Darussalam')),
    ('BG', ugettext_lazy(u'Bulgaria')),
    ('BF', ugettext_lazy(u'Burkina Faso')),
    ('BI', ugettext_lazy(u'Burundi')),
    ('KH', ugettext_lazy(u'Cambodia')),
    ('CM', ugettext_lazy(u'Cameroon')),
    ('CA', ugettext_lazy(u'Canada')),
    ('CV', ugettext_lazy(u'Cape Verde')),
    ('KY', ugettext_lazy(u'Cayman Islands')),
    ('CF', ugettext_lazy(u'Central African Republic')),
    ('TD', ugettext_lazy(u'Chad')),
    ('CL', ugettext_lazy(u'Chile')),
    ('CN', ugettext_lazy(u'China')),
    ('CX', ugettext_lazy(u'Christmas Island')),
    ('CC', ugettext_lazy(u'Cocos (Keeling) Islands')),
    ('CO', ugettext_lazy(u'Colombia')),
    ('KM', ugettext_lazy(u'Comoros')),
    ('CG', ugettext_lazy(u'Congo')),
    ('CD', ugettext_lazy(u'Congo, The Democratic Republic of the')),
    ('CK', ugettext_lazy(u'Cook Islands')),
    ('CR', ugettext_lazy(u'Costa Rica')),
    ('CI', ugettext_lazy(u'Côte D\'Ivoire')),
    ('HR', ugettext_lazy(u'Croatia')),
    ('CU', ugettext_lazy(u'Cuba')),
    ('CW', ugettext_lazy(u'Curaço')),
    ('CY', ugettext_lazy(u'Cyprus')),
    ('CZ', ugettext_lazy(u'Czech Republic')),
    ('DK', ugettext_lazy(u'Denmark')),
    ('DJ', ugettext_lazy(u'Djibouti')),
    ('DM', ugettext_lazy(u'Dominica')),
    ('DO', ugettext_lazy(u'Dominican Republic')),
    ('EC', ugettext_lazy(u'Ecuador')),
    ('EG', ugettext_lazy(u'Egypt')),
    ('SV', ugettext_lazy(u'El Salvador')),
    ('GQ', ugettext_lazy(u'Equatorial Guinea')),
    ('ER', ugettext_lazy(u'Eritrea')),
    ('EE', ugettext_lazy(u'Estonia')),
    ('ET', ugettext_lazy(u'Ethiopia')),
    ('FK', ugettext_lazy(u'Falkland Islands (Malvinas)')),
    ('FO', ugettext_lazy(u'Faroe Islands')),
    ('FJ', ugettext_lazy(u'Fiji')),
    ('FI', ugettext_lazy(u'Finland')),
    ('FR', ugettext_lazy(u'France')),
    ('GF', ugettext_lazy(u'French Guiana')),
    ('PF', ugettext_lazy(u'French Polynesia')),
    ('TF', ugettext_lazy(u'French Southern Territories')),
    ('GA', ugettext_lazy(u'Gabon')),
    ('GM', ugettext_lazy(u'Gambia')),
    ('GE', ugettext_lazy(u'Georgia')),
    ('DE', ugettext_lazy(u'Germany')),
    ('GH', ugettext_lazy(u'Ghana')),
    ('GI', ugettext_lazy(u'Gibraltar')),
    ('GR', ugettext_lazy(u'Greece')),
    ('GL', ugettext_lazy(u'Greenland')),
    ('GD', ugettext_lazy(u'Grenada')),
    ('GP', ugettext_lazy(u'Guadeloupe')),
    ('GU', ugettext_lazy(u'Guam')),
    ('GT', ugettext_lazy(u'Guatemala')),
    ('GG', ugettext_lazy(u'Guernsey')),
    ('GN', ugettext_lazy(u'Guinea')),
    ('GW', ugettext_lazy(u'Guinea-Bissau')),
    ('GY', ugettext_lazy(u'Guyana')),
    ('HT', ugettext_lazy(u'Haiti')),
    ('HM', ugettext_lazy(u'Heard Island And Mcdonald Islands')),
    ('VA', ugettext_lazy(u'Holy See (Vatican City State)')),
    ('HN', ugettext_lazy(u'Honduras')),
    ('HK', ugettext_lazy(u'Hong Kong')),
    ('HU', ugettext_lazy(u'Hungary')),
    ('IS', ugettext_lazy(u'Iceland')),
    ('IN', ugettext_lazy(u'India')),
    ('ID', ugettext_lazy(u'Indonesia')),
    ('IR', ugettext_lazy(u'Iran, Islamic Republic of')),
    ('IQ', ugettext_lazy(u'Iraq')),
    ('IE', ugettext_lazy(u'Ireland')),
    ('IM', ugettext_lazy(u'Isle of Man')),
    ('IL', ugettext_lazy(u'Israel')),
    ('IT', ugettext_lazy(u'Italy')),
    ('JM', ugettext_lazy(u'Jamaica')),
    ('JP', ugettext_lazy(u'Japan')),
    ('JE', ugettext_lazy(u'Jersey')),
    ('JO', ugettext_lazy(u'Jordan')),
    ('KZ', ugettext_lazy(u'Kazakhstan')),
    ('KE', ugettext_lazy(u'Kenya')),
    ('KI', ugettext_lazy(u'Kiribati')),
    ('KP', ugettext_lazy(u'Korea, Democratic People\'s Republic of')),
    ('KR', ugettext_lazy(u'Korea, Republic of')),
    ('KW', ugettext_lazy(u'Kuwait')),
    ('KG', ugettext_lazy(u'Kyrgyzstan')),
    ('LA', ugettext_lazy(u'Lao People\'s Democratic Republic')),
    ('LV', ugettext_lazy(u'Latvia')),
    ('LB', ugettext_lazy(u'Lebanon')),
    ('LS', ugettext_lazy(u'Lesotho')),
    ('LR', ugettext_lazy(u'Liberia')),
    ('LY', ugettext_lazy(u'Libya')),
    ('LI', ugettext_lazy(u'Liechtenstein')),
    ('LT', ugettext_lazy(u'Lithuania')),
    ('LU', ugettext_lazy(u'Luxembourg')),
    ('MO', ugettext_lazy(u'Macao')),
    ('MK', ugettext_lazy(u'Macedonia, The Former Yugoslav Republic of')),
    ('MG', ugettext_lazy(u'Madagascar')),
    ('MW', ugettext_lazy(u'Malawi')),
    ('MY', ugettext_lazy(u'Malaysia')),
    ('MV', ugettext_lazy(u'Maldives')),
    ('ML', ugettext_lazy(u'Mali')),
    ('MT', ugettext_lazy(u'Malta')),
    ('MH', ugettext_lazy(u'Marshall Islands')),
    ('MQ', ugettext_lazy(u'Martinique')),
    ('MR', ugettext_lazy(u'Mauritania')),
    ('MU', ugettext_lazy(u'Mauritius')),
    ('YT', ugettext_lazy(u'Mayotte')),
    ('MX', ugettext_lazy(u'Mexico')),
    ('FM', ugettext_lazy(u'Micronesia, Federated States of')),
    ('MD', ugettext_lazy(u'Moldova, Republic of')),
    ('MC', ugettext_lazy(u'Monaco')),
    ('MN', ugettext_lazy(u'Mongolia')),
    ('ME', ugettext_lazy(u'Montenegro')),
    ('MS', ugettext_lazy(u'Montserrat')),
    ('MA', ugettext_lazy(u'Morocco')),
    ('MZ', ugettext_lazy(u'Mozambique')),
    ('MM', ugettext_lazy(u'Myanmar')),
    ('NA', ugettext_lazy(u'Namibia')),
    ('NR', ugettext_lazy(u'Nauru')),
    ('NP', ugettext_lazy(u'Nepal')),
    ('NL', ugettext_lazy(u'Netherlands')),
    ('NC', ugettext_lazy(u'New Caledonia')),
    ('NZ', ugettext_lazy(u'New Zealand')),
    ('NI', ugettext_lazy(u'Nicaragua')),
    ('NE', ugettext_lazy(u'Niger')),
    ('NG', ugettext_lazy(u'Nigeria')),
    ('NU', ugettext_lazy(u'Niue')),
    ('NF', ugettext_lazy(u'Norfolk Island')),
    ('MP', ugettext_lazy(u'Northern Mariana Islands')),
    ('NO', ugettext_lazy(u'Norway')),
    ('OM', ugettext_lazy(u'Oman')),
    ('PK', ugettext_lazy(u'Pakistan')),
    ('PW', ugettext_lazy(u'Palau')),
    ('PS', ugettext_lazy(u'Palestinian Territory, Occupied')),
    ('PA', ugettext_lazy(u'Panama')),
    ('PG', ugettext_lazy(u'Papua New Guinea')),
    ('PY', ugettext_lazy(u'Paraguay')),
    ('PE', ugettext_lazy(u'Peru')),
    ('PH', ugettext_lazy(u'Philippines')),
    ('PN', ugettext_lazy(u'Pitcairn')),
    ('PL', ugettext_lazy(u'Poland')),
    ('PT', ugettext_lazy(u'Portugal')),
    ('PR', ugettext_lazy(u'Puerto Rico')),
    ('QA', ugettext_lazy(u'Qatar')),
    ('RE', ugettext_lazy(u'Réunion')),
    ('RO', ugettext_lazy(u'Romania')),
    ('RU', ugettext_lazy(u'Russian Federation')),
    ('RW', ugettext_lazy(u'Rwanda')),
    ('BL', ugettext_lazy(u'Saint Barthélemy')),
    ('SH', ugettext_lazy(u'Saint Helena, Ascension And Tristan Da Cunha')),
    ('KN', ugettext_lazy(u'Saint Kitts And Nevis')),
    ('LC', ugettext_lazy(u'Saint Lucia')),
    ('MF', ugettext_lazy(u'Saint Martin (French Part)')),
    ('PM', ugettext_lazy(u'Saint Pierre And Miquelon')),
    ('VC', ugettext_lazy(u'Saint Vincent And the Grenadines')),
    ('WS', ugettext_lazy(u'Samoa')),
    ('SM', ugettext_lazy(u'San Marino')),
    ('ST', ugettext_lazy(u'Sao Tome And Principe')),
    ('SA', ugettext_lazy(u'Saudi Arabia')),
    ('SN', ugettext_lazy(u'Senegal')),
    ('RS', ugettext_lazy(u'Serbia')),
    ('SC', ugettext_lazy(u'Seychelles')),
    ('SL', ugettext_lazy(u'Sierra Leone')),
    ('SG', ugettext_lazy(u'Singapore')),
    ('SX', ugettext_lazy(u'Sint Maarten (Dutch Part)')),
    ('SK', ugettext_lazy(u'Slovakia')),
    ('SI', ugettext_lazy(u'Slovenia')),
    ('SB', ugettext_lazy(u'Solomon Islands')),
    ('SO', ugettext_lazy(u'Somalia')),
    ('ZA', ugettext_lazy(u'South Africa')),
    ('GS', ugettext_lazy(u'South Georgia and the South Sandwich Islands')),
    ('ES', ugettext_lazy(u'Spain')),
    ('LK', ugettext_lazy(u'Sri Lanka')),
    ('SD', ugettext_lazy(u'Sudan')),
    ('SR', ugettext_lazy(u'Suriname')),
    ('SJ', ugettext_lazy(u'Svalbard and Jan Mayen')),
    ('SZ', ugettext_lazy(u'Swaziland')),
    ('SE', ugettext_lazy(u'Sweden')),
    ('CH', ugettext_lazy(u'Switzerland')),
    ('SY', ugettext_lazy(u'Syria')),
    ('TW', ugettext_lazy(u'Taiwan')),
    ('TJ', ugettext_lazy(u'Tajikistan')),
    ('TZ', ugettext_lazy(u'Tanzania')),
    ('TH', ugettext_lazy(u'Thailand')),
    ('TL', ugettext_lazy(u'Timor-Leste')),
    ('TG', ugettext_lazy(u'Togo')),
    ('TK', ugettext_lazy(u'Tokelau')),
    ('TO', ugettext_lazy(u'Tonga')),
    ('TT', ugettext_lazy(u'Trinidad And Tobago')),
    ('TN', ugettext_lazy(u'Tunisia')),
    ('TR', ugettext_lazy(u'Turkey')),
    ('TM', ugettext_lazy(u'Turkmenistan')),
    ('TC', ugettext_lazy(u'Turks And Caicos Islands')),
    ('TV', ugettext_lazy(u'Tuvalu')),
    ('UG', ugettext_lazy(u'Uganda')),
    ('UA', ugettext_lazy(u'Ukraine')),
    ('AE', ugettext_lazy(u'United Arab Emirates')),
    ('GB', ugettext_lazy(u'United Kingdom')),
    ('US', ugettext_lazy(u'United States')),
    ('UM', ugettext_lazy(u'United States Minor Outlying Islands')),
    ('UY', ugettext_lazy(u'Uruguay')),
    ('UZ', ugettext_lazy(u'Uzbekistan')),
    ('VU', ugettext_lazy(u'Vanuatu')),
    ('VE', ugettext_lazy(u'Venezuela')),
    ('VN', ugettext_lazy(u'Viet Nam')),
    ('VG', ugettext_lazy(u'Virgin Islands, British')),
    ('VI', ugettext_lazy(u'Virgin Islands, U.S.')),
    ('WF', ugettext_lazy(u'Wallis And Futuna')),
    ('EH', ugettext_lazy(u'Western Sahara')),
    ('YE', ugettext_lazy(u'Yemen')),
    ('ZM', ugettext_lazy(u'Zambia')),
    ('ZW', ugettext_lazy(u'Zimbabwe')),
)


def build_country_choices():
    country_list = getattr(
        settings, 'SATCHLESS_COUNTRY_CHOICES', DEFAULT_COUNTRY_CHOICES)
    if isinstance(country_list, str):
        mod_name, han_name = country_list.rsplit('.', 1)
        module = import_module(mod_name)
        country_list = getattr(module, han_name)
    if hasattr(country_list, '__call__'):
        country_list = country_list()
    country_keys = dict(DEFAULT_COUNTRY_CHOICES)
    countries = []
    for country in country_list:
        if country is None:
            country = (u'', u'---------')
        if isinstance(country, str):
            country = (country, country_keys[country])
        countries.append(country)
    return countries

COUNTRY_CHOICES = build_country_choices()

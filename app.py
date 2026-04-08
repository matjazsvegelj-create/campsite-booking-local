import html
import os
import cgi
import json
import re
import sqlite3
import smtplib
from contextlib import closing
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from email.message import EmailMessage
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, urlencode
from urllib.request import Request, urlopen
from wsgiref.simple_server import make_server


APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "booking.db"
STATIC_DIR = APP_DIR / "static"
DATE_FMT = "%Y-%m-%d"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
SMTP_HOST = os.environ.get("SMTP_HOST", "").strip()
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587") or "587")
SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "").strip()
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "").strip()
SMTP_FROM_EMAIL = os.environ.get("SMTP_FROM_EMAIL", "").strip()
SMTP_FROM_NAME = os.environ.get("SMTP_FROM_NAME", "Campsite Booking").strip()
SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "1").strip() != "0"
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "").strip()
RESEND_FROM_EMAIL = os.environ.get("RESEND_FROM_EMAIL", "").strip()
RESEND_FROM_NAME = os.environ.get("RESEND_FROM_NAME", SMTP_FROM_NAME).strip()
SUPPORTED_LANGS = ("en", "sl")
LOCATION_LABELS = {
    "Laski rovt ZTS": {"en": "Laski rovt ZTS", "sl": "Laški rovt ZTS"},
    "Laski rovt ZR": {"en": "Laski rovt ZR", "sl": "Laški rovt ZR"},
    "Laski rovt MB": {"en": "Laski rovt MB", "sl": "Laški rovt MB"},
    "Taborni prostor Ukanc": {"en": "Ukanc camping area", "sl": "Taborni prostor Ukanc"},
    "Gozdna sola Ukanc": {"en": "Ukanc forest school", "sl": "Gozdna šola Ukanc"},
    "Taborni prostor Baredi": {"en": "Baredi camping area", "sl": "Taborni prostor Baredi"},
    "Taborni prostor Radlje ob Dravi": {"en": "Radlje ob Dravi camping area", "sl": "Taborni prostor Radlje ob Dravi"},
}
TEXTS = {
    "en": {
        "search": "Search",
        "admin": "Admin",
        "prototype": "Local Prototype",
        "period": "Period",
        "type": "Type",
        "booking": "Booking",
        "summary": "Summary",
        "choose_intro": "Choose the campsite first. Then select the stay period and guest count for that location to continue to the next step.",
        "check_in": "Check-in",
        "check_out": "Check-out",
        "guests": "Guests",
        "continue": "Continue",
        "capacity": "Capacity",
        "guests_word": "guests",
        "price": "Price",
        "per_guest_per_night": "per guest per night",
        "total_nights": "Total number of nights",
        "choose_dates_to_calc": "Choose dates to calculate nights.",
        "date_note": "Please note that arrival and departure times are between 9:00 am and 6:00 pm. On Sundays and public holidays until 4:00 pm.",
        "arrival_optional": "Please let us know your preferred arrival time. We'll then see if we can welcome you at that time. - Optional",
        "departure_optional": "Please let us know your preferred departure time so that our team can be there on time. - Optional",
        "select_time": "Select time",
        "arrival_note_optional": "Additional note about arrival - Optional",
        "departure_note_optional": "Additional note about departure - Optional",
        "available": "Available",
        "unavailable": "Unavailable",
        "continue_unit": "Continue with this unit",
        "type_heading": "Type",
        "who_are_you": "Who are you?",
        "boarding_type": "Boarding type",
        "update_options": "Update options",
        "current_pricing_note": "Current pricing note",
        "type_of_group": "Type of group",
        "laski_choose_group": "Choose whether the group is Taborniki ZTS.",
        "stay": "Stay",
        "estimated_total": "Estimated total",
        "member_category": "Member category",
        "boarding_option": "Boarding option",
        "laski_group_type": "Laski group type",
        "full_name": "Full name",
        "email": "Email",
        "phone": "Phone",
        "notes": "Notes",
        "create_booking": "Create pending booking",
        "location_type_campsite": "Campsite",
        "location_type_house": "House",
        "selected_location_not_found": "Selected location was not found.",
        "selected_unit_not_found": "Selected unit was not found.",
        "not_specified": "Not specified",
        "selected_location": "Selected location",
        "language_en": "EN",
        "language_sl": "SL",
        "app_title": "Campsite Booking",
        "group_details": "Group details",
        "rental": "Rental",
        "contact_details": "Contact details",
        "other_information": "Other information",
        "subcamp": "Subcamp",
        "our_group_is_from": "Our scout group is from:",
        "choose_one": "Choose one",
        "capacity_guests": "Capacity: {count} guests",
        "booking_submitted": "Booking submitted",
        "booking_submitted_text": "Your booking request has been submitted successfully.",
        "booking_email_sent": "A booking summary has been sent to the contact person's email address.",
        "booking_email_not_sent": "The booking was saved, but the confirmation email could not be sent yet.",
    },
    "sl": {
        "search": "Iskanje",
        "admin": "Admin",
        "prototype": "Lokalni prototip",
        "period": "Termin",
        "type": "Tip",
        "booking": "Rezervacija",
        "summary": "Povzetek",
        "choose_intro": "Najprej izberite lokacijo. Nato izberite termin bivanja in število gostov za to lokacijo, da nadaljujete na naslednji korak.",
        "check_in": "Prihod",
        "check_out": "Odhod",
        "guests": "Gostje",
        "continue": "Nadaljuj",
        "capacity": "Kapaciteta",
        "guests_word": "gostov",
        "price": "Cena",
        "per_guest_per_night": "na gosta na noč",
        "total_nights": "Skupno število noči",
        "choose_dates_to_calc": "Izberite datume za izračun noči.",
        "date_note": "Prihodi in odhodi so med 9:00 in 18:00. Ob nedeljah in praznikih do 16:00.",
        "arrival_optional": "Sporočite želen čas prihoda. Nato bomo preverili, ali vas lahko sprejmemo ob tem času. - Neobvezno",
        "departure_optional": "Sporočite želen čas odhoda, da je naša ekipa pravočasno na lokaciji. - Neobvezno",
        "select_time": "Izberite uro",
        "arrival_note_optional": "Dodatna opomba o prihodu - neobvezno",
        "departure_note_optional": "Dodatna opomba o odhodu - neobvezno",
        "available": "Na voljo",
        "unavailable": "Ni na voljo",
        "continue_unit": "Nadaljuj s to enoto",
        "type_heading": "Tip",
        "who_are_you": "Kdo ste?",
        "boarding_type": "Vrsta oskrbe",
        "update_options": "Posodobi možnosti",
        "current_pricing_note": "Trenutna opomba o ceni",
        "type_of_group": "Tip skupine",
        "laski_choose_group": "Izberite, ali je skupina Taborniki ZTS.",
        "stay": "Termin",
        "estimated_total": "Ocenjeni znesek",
        "member_category": "Kategorija članstva",
        "boarding_option": "Izbrana oskrba",
        "laski_group_type": "Tip skupine Laški rovt",
        "full_name": "Ime in priimek",
        "email": "E-pošta",
        "phone": "Telefon",
        "notes": "Opombe",
        "create_booking": "Ustvari čakajočo rezervacijo",
        "location_type_campsite": "Taborni prostor",
        "location_type_house": "Hiša",
        "selected_location_not_found": "Izbrana lokacija ni bila najdena.",
        "selected_unit_not_found": "Izbrana enota ni bila najdena.",
        "not_specified": "Ni določeno",
        "selected_location": "Izbrana lokacija",
        "language_en": "EN",
        "language_sl": "SL",
        "app_title": "Rezervacija taborjenja",
        "group_details": "Podatki o skupini",
        "rental": "Izposoja",
        "contact_details": "Kontaktni podatki",
        "other_information": "Druge informacije",
        "subcamp": "Podtabor",
        "our_group_is_from": "Naša skavtska skupina prihaja iz:",
        "choose_one": "Izberite eno",
        "capacity_guests": "Kapaciteta: {count} gostov",
        "booking_submitted": "Rezervacija oddana",
        "booking_submitted_text": "Vaša rezervacijska zahteva je bila uspešno oddana.",
        "booking_email_sent": "Povzetek rezervacije je bil poslan na e-poštni naslov kontaktne osebe.",
        "booking_email_not_sent": "Rezervacija je bila shranjena, vendar potrditvenega e-sporočila še ni bilo mogoče poslati.",
    },
}
SEEDED_LOCATIONS = [
    {
        "name": "Laski rovt ZTS",
        "type": "campsite",
        "display_order": 1,
        "units": [
            {"name": "Subcamp 1", "max_guests": 70, "price": "8.50", "display_order": 1},
            {"name": "Subcamp 2", "max_guests": 35, "price": "8.50", "display_order": 2},
            {"name": "Subcamp 3", "max_guests": 20, "price": "8.50", "display_order": 3},
        ],
    },
    {
        "name": "Laski rovt ZR",
        "type": "campsite",
        "display_order": 2,
        "units": [
            {"name": "Main", "max_guests": 35, "price": "8.50", "display_order": 1},
        ],
    },
    {
        "name": "Laski rovt MB",
        "type": "campsite",
        "display_order": 3,
        "units": [
            {"name": "Main", "max_guests": 100, "price": "8.50", "display_order": 1},
        ],
    },
    {
        "name": "Taborni prostor Ukanc",
        "type": "campsite",
        "display_order": 4,
        "units": [
            {"name": "Main", "max_guests": 120, "price": "18.00", "display_order": 1},
        ],
    },
    {
        "name": "Gozdna sola Ukanc",
        "type": "house",
        "display_order": 5,
        "units": [
            {"name": "Main", "max_guests": 38, "price": "18.00", "display_order": 1},
        ],
    },
    {
        "name": "Taborni prostor Baredi",
        "type": "campsite",
        "display_order": 6,
        "units": [
            {"name": "Main", "max_guests": 50, "price": "10.00", "display_order": 1},
        ],
    },
    {
        "name": "Taborni prostor Radlje ob Dravi",
        "type": "campsite",
        "display_order": 7,
        "units": [
            {"name": "Main", "max_guests": 120, "price": "8.50", "display_order": 1},
        ],
    },
]
ACCOMMODATION_TYPES = [
    ("field", "Field"),
    ("building", "Building"),
]
UKANC_LOCATION_NAMES = {"Taborni prostor Ukanc", "Gozdna sola Ukanc"}
DYNAMIC_PRICING_LOCATION_NAMES = {
    "Laski rovt ZTS",
    "Laski rovt ZR",
    "Laski rovt MB",
    "Taborni prostor Ukanc",
    "Gozdna sola Ukanc",
}
LASKI_LOCATION_NAMES = {"Laski rovt ZTS", "Laski rovt ZR", "Laski rovt MB"}
SEASON_LIMITED_LOCATION_NAMES = {"Laski rovt ZTS", "Laski rovt ZR", "Laski rovt MB", "Taborni prostor Ukanc"}
MEMBER_CATEGORIES = [
    ("zts_member", "Member of Taborniki / ZTS"),
    ("other", "Others / foreign scouts / non-scouts"),
]
LASKI_GROUP_TYPES = [
    ("foreign_scouts", "Non Slovenian scouts"),
    ("non_scouts", "Non scouts"),
    ("taborniki_zts", "Taborniki ZTS"),
]
GROUP_SECTION_OPTIONS = [
    ("beavers", "Beavers [5 - 7]"),
    ("cub_scouts", "Cub Scouts [7 - 10]"),
    ("scouts", "Scouts [10 - 13]"),
    ("explorers", "Explorers [13 - 16]"),
    ("rover_scouts", "Rover Scouts [16 - 20]"),
    ("leaders", "Leaders [> 20]"),
    ("team", "Team [> 18]"),
]
NON_SCOUT_SECTION_LABELS = {
    "beavers": "[5 - 7]",
    "cub_scouts": "[7 - 10]",
    "scouts": "[10 - 13]",
    "explorers": "[13 - 16]",
    "rover_scouts": "[16 - 20]",
    "leaders": "[> 20]",
    "team": "",
}
ADULT_SECTION_KEYS = {"rover_scouts", "leaders", "team"}
COUNTRY_OPTIONS = [
    "Afghanistan", "Albania", "Algeria", "Andorra", "Angola", "Antigua and Barbuda", "Argentina", "Armenia", "Australia",
    "Austria", "Azerbaijan", "Bahamas", "Bahrain", "Bangladesh", "Barbados", "Belarus", "Belgium", "Belize", "Benin",
    "Bhutan", "Bolivia", "Bosnia and Herzegovina", "Botswana", "Brazil", "Brunei", "Bulgaria", "Burkina Faso", "Burundi",
    "Cabo Verde", "Cambodia", "Cameroon", "Canada", "Central African Republic", "Chad", "Chile", "China", "Colombia",
    "Comoros", "Congo", "Costa Rica", "Croatia", "Cuba", "Cyprus", "Czechia", "Denmark", "Djibouti", "Dominica",
    "Dominican Republic", "Ecuador", "Egypt", "El Salvador", "Equatorial Guinea", "Eritrea", "Estonia", "Eswatini",
    "Ethiopia", "Fiji", "Finland", "France", "Gabon", "Gambia", "Georgia", "Germany", "Ghana", "Greece", "Grenada",
    "Guatemala", "Guinea", "Guinea-Bissau", "Guyana", "Haiti", "Honduras", "Hungary", "Iceland", "India", "Indonesia",
    "Iran", "Iraq", "Ireland", "Israel", "Italy", "Jamaica", "Japan", "Jordan", "Kazakhstan", "Kenya", "Kiribati",
    "Kuwait", "Kyrgyzstan", "Laos", "Latvia", "Lebanon", "Lesotho", "Liberia", "Libya", "Liechtenstein", "Lithuania",
    "Luxembourg", "Madagascar", "Malawi", "Malaysia", "Maldives", "Mali", "Malta", "Marshall Islands", "Mauritania",
    "Mauritius", "Mexico", "Micronesia", "Moldova", "Monaco", "Mongolia", "Montenegro", "Morocco", "Mozambique",
    "Myanmar", "Namibia", "Nauru", "Nepal", "Netherlands", "New Zealand", "Nicaragua", "Niger", "Nigeria",
    "North Korea", "North Macedonia", "Norway", "Oman", "Pakistan", "Palau", "Panama", "Papua New Guinea", "Paraguay",
    "Peru", "Philippines", "Poland", "Portugal", "Qatar", "Romania", "Russia", "Rwanda", "Saint Kitts and Nevis",
    "Saint Lucia", "Saint Vincent and the Grenadines", "Samoa", "San Marino", "Sao Tome and Principe", "Saudi Arabia",
    "Senegal", "Serbia", "Seychelles", "Sierra Leone", "Singapore", "Slovakia", "Slovenia", "Solomon Islands",
    "Somalia", "South Africa", "South Korea", "South Sudan", "Spain", "Sri Lanka", "Sudan", "Suriname", "Sweden",
    "Switzerland", "Syria", "Taiwan", "Tajikistan", "Tanzania", "Thailand", "Timor-Leste", "Togo", "Tonga",
    "Trinidad and Tobago", "Tunisia", "Turkey", "Turkmenistan", "Tuvalu", "Uganda", "Ukraine", "United Arab Emirates",
    "United Kingdom", "United States", "Uruguay", "Uzbekistan", "Vanuatu", "Vatican City", "Venezuela", "Vietnam",
    "Yemen", "Zambia", "Zimbabwe",
]
RENTAL_ITEMS = [
    {"key": "kitchen", "label": "Kitchen", "price": "50.00 EUR", "note": "rent per stay, maximum 2 per group", "max_quantity": 2},
    {"key": "cooler_refrigerator", "label": "Cooler/refrigerator", "price": "50.00 EUR", "note": "rent per stay, maximum 1 per group", "max_quantity": 1},
    {"key": "table_set", "label": "Set of tables and two benches", "price": "10.00 EUR", "note": "rent per day per set, maximum 10 per group. If needed more than 10 add in the comments below.", "max_quantity": 10},
    {"key": "small_canoe_half_day", "label": "Small canoe (up to 3 people)", "price": "25.00 EUR", "note": "morning or afternoon, pickup at Ukanc forest school (Ukanc 3), maximum 3", "max_quantity": 3},
    {"key": "small_canoe_all_day", "label": "Small canoe (up to 3 people)", "price": "35.00 EUR", "note": "all day, pickup at Ukanc forest school (Ukanc 3), maximum 3", "max_quantity": 3},
    {"key": "large_canoe_half_day", "label": "Large canoe (up to 10 people)", "price": "30.00 EUR", "note": "morning or afternoon, pickup at Ukanc forest school (Ukanc 3), maximum 2", "max_quantity": 2},
    {"key": "large_canoe_all_day", "label": "Large canoe (up to 10 people)", "price": "45.00 EUR", "note": "all day, pickup at Ukanc forest school (Ukanc 3), maximum 2", "max_quantity": 2},
    {"key": "bike_half_day", "label": "Bike", "price": "10.00 EUR", "note": "morning or afternoon, pickup at Ukanc forest school (Ukanc 3), maximum 15", "max_quantity": 15},
    {"key": "bike_all_day", "label": "Bike", "price": "20.00 EUR", "note": "all day, pickup at Ukanc forest school (Ukanc 3), maximum 15", "max_quantity": 15},
    {"key": "electric_bike_half_day", "label": "Electric bike", "price": "40.00 EUR", "note": "half day, pickup at Ukanc forest school (Ukanc 3), maximum 10", "max_quantity": 10},
    {"key": "electric_bike_all_day", "label": "Electric bike", "price": "60.00 EUR", "note": "all day, pickup at Ukanc forest school (Ukanc 3), maximum 10", "max_quantity": 10},
    {"key": "sup_all_day", "label": "SUP", "price": "10.00 EUR", "note": "all day, maximum 2", "max_quantity": 2},
    {"key": "bow_half_day", "label": "Bow", "price": "10.00 EUR", "note": "morning or afternoon, arrows and target included, pickup at Ukanc forest school (Ukanc 3), maximum 2", "max_quantity": 2},
    {"key": "bow_all_day", "label": "Bow", "price": "15.00 EUR", "note": "all day, arrows and target included, pickup at Ukanc forest school (Ukanc 3), maximum 2", "max_quantity": 2},
    {"key": "air_rifle_half_day", "label": "Air rifle", "price": "10.00 EUR", "note": "morning or afternoon, pellets and target included, pickup at Ukanc forest school (Ukanc 3), maximum 1", "max_quantity": 1},
    {"key": "air_rifle_all_day", "label": "Air rifle", "price": "15.00 EUR", "note": "all day, pellets and target included, pickup at Ukanc forest school (Ukanc 3), maximum 1", "max_quantity": 1},
    {"key": "firewood", "label": "Firewood", "price": "90 EUR/m³", "note": "base unit is 1 m³", "quantity_options": ["0.5", "1", "2"]},
    {"key": "pioneering_wood", "label": "Pioneering projects wood", "price": "5.00 EUR per log", "note": "when selected, specify how many and approximately how long, maximum 50 logs", "max_quantity": 50, "requires_length": True},
]
UKANC_BOARDING_OPTIONS = {
    "zts_member": [
        {
            "key": "zts_individual_breakfast",
            "label": "A. ZTS member - overnight with breakfast",
            "prices": {"high": "20.50", "low": "17.00"},
            "max_guests": 9,
        },
        {
            "key": "zts_individual_half",
            "label": "A. ZTS member - half board (1/2)",
            "prices": {"high": "23.50", "low": "20.00"},
            "max_guests": 9,
        },
        {
            "key": "zts_individual_full",
            "label": "A. ZTS member - full board (1/1)",
            "prices": {"high": "25.50", "low": "22.00"},
            "max_guests": 9,
        },
        {
            "key": "zts_group_breakfast",
            "label": "A. ZTS group 10+ - overnight with breakfast",
            "prices": {"high": "19.50", "low": "16.00"},
            "min_guests": 10,
        },
        {
            "key": "zts_group_half",
            "label": "A. ZTS group 10+ - half board (1/2)",
            "prices": {"high": "22.50", "low": "19.00"},
            "min_guests": 10,
        },
        {
            "key": "zts_group_full",
            "label": "A. ZTS group 10+ - full board (1/1)",
            "prices": {"high": "24.50", "low": "21.00"},
            "min_guests": 10,
        },
    ],
    "other": [
        {
            "key": "other_individual_breakfast",
            "label": "A. Individual - overnight with breakfast",
            "prices": {"high": "28.50", "low": "27.50"},
            "max_guests": 9,
        },
        {
            "key": "other_individual_half",
            "label": "A. Individual - half board (1/2)",
            "prices": {"high": "31.50", "low": "30.50"},
            "max_guests": 9,
        },
        {
            "key": "other_individual_full",
            "label": "A. Individual - full board (1/1)",
            "prices": {"high": "34.50", "low": "33.50"},
            "max_guests": 9,
        },
        {
            "key": "other_group_breakfast",
            "label": "A. Group - one night with breakfast",
            "prices": {"high": "27.50", "low": "26.50"},
            "min_guests": 10,
        },
        {
            "key": "other_group_half",
            "label": "A. Group - one night with half board (1/2)",
            "prices": {"high": "30.50", "low": "29.50"},
            "min_guests": 10,
        },
        {
            "key": "other_group_full",
            "label": "A. Group - one night with full board (1/1)",
            "prices": {"high": "33.50", "low": "32.50"},
            "min_guests": 10,
        },
        {
            "key": "other_holiday_full",
            "label": "A. Christmas/New Year holidays - minimum 2 nights full board",
            "prices": {"holiday": "50.00"},
        },
        {
            "key": "other_tent_selfcook",
            "label": "B. Overnight in tent - outside kitchen, electricity",
            "prices": {"high": "18.50"},
            "min_guests": 10,
        },
    ],
}


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def get_lang(value):
    return value if value in SUPPORTED_LANGS else "en"


def t(lang, key):
    return TEXTS[get_lang(lang)].get(key, key)


def tf(lang, key, **kwargs):
    return t(lang, key).format(**kwargs)


def build_time_options():
    options = []
    for hour in range(9, 19):
        options.append(f"{hour}:00")
    return options


TIME_OPTIONS = build_time_options()


def render_time_select(name, selected_value, lang):
    options = [f'<option value="">{html.escape(t(lang, "select_time"))}</option>']
    for value in TIME_OPTIONS:
        selected_attr = " selected" if value == selected_value else ""
        options.append(f'<option value="{value}"{selected_attr}>{value}</option>')
    return f'<select name="{html.escape(name)}">{"".join(options)}</select>'


def render_country_input(selected_value, name="country", list_id="country-options"):
    options = "".join(
        f'<option value="{html.escape(country)}"></option>'
        for country in COUNTRY_OPTIONS
    )
    return (
        f'<input type="text" name="{html.escape(name)}" value="{html.escape(selected_value)}" '
        f'list="{html.escape(list_id)}" autocomplete="off" class="country-input">'
        f'<datalist id="{html.escape(list_id)}">{options}</datalist>'
    )


def render_member_category_select(selected_value):
    options = ['<option value="">Choose one</option>']
    choices = [
        ("zts_member", "Member of Taborniki / ZTS"),
        ("other", "Others"),
    ]
    for value, label in choices:
        selected_attr = " selected" if value == selected_value else ""
        options.append(f'<option value="{value}"{selected_attr}>{html.escape(label)}</option>')
    return f'<select name="member_category" class="member-category-select">{"".join(options)}</select>'


def render_rental_quantity_select(item, selected_value):
    options = ['<option value="" class="rental-zero-option">0</option>']
    if "quantity_options" in item:
        for value in item["quantity_options"]:
            selected_attr = " selected" if str(value) == str(selected_value) else ""
            options.append(f'<option value="{value}"{selected_attr}>{value}</option>')
    else:
        for number in range(1, item["max_quantity"] + 1):
            selected_attr = " selected" if str(number) == str(selected_value) else ""
            options.append(f'<option value="{number}"{selected_attr}>{number}</option>')
    return (
        f'<select class="rental-qty" data-rental-key="{item["key"]}" name="rental_{item["key"]}">'
        f'{"".join(options)}'
        f'</select>'
    )


def build_return_to(path, params):
    query = urlencode({key: value for key, value in params.items() if value != ""})
    return f"{path}?{query}" if query else path


def render_step_actions(back_href, continue_html):
    return f"""
    <div class="step-actions field-span-full">
      <a class="button button-secondary" href="{html.escape(back_href)}">Back</a>
      {continue_html}
    </div>
    """


def render_step_actions_form(back_path, continue_html):
    return f"""
    <div class="step-actions field-span-full">
      <button type="submit" class="button button-secondary" formaction="{html.escape(back_path)}">Back</button>
      {continue_html}
    </div>
    """


def parse_rental_quantities(source):
    selected = []
    for item in RENTAL_ITEMS:
        enabled = source.get(f"rental_{item['key']}_enabled", "") == "yes"
        raw_value = str(source.get(f"rental_{item['key']}", "")).strip()
        length_value = str(source.get(f"rental_{item['key']}_length", "")).strip()
        if "quantity_options" in item:
            quantity_value = raw_value if raw_value in item["quantity_options"] else ""
            if enabled and quantity_value:
                selected.append({"item": item, "quantity": quantity_value, "length": length_value})
        else:
            quantity = min(
                to_non_negative_int(raw_value or "0"),
                item["max_quantity"],
            )
            if enabled and quantity > 0:
                selected.append({"item": item, "quantity": str(quantity), "length": length_value})
    return selected


def parse_decimal_amount(value):
    match = re.search(r"\d+(?:\.\d+)?", str(value))
    return Decimal(match.group(0)) if match else Decimal("0.00")


def format_currency(amount):
    return f"{Decimal(amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}".replace(".", ",") + " EUR"


def round_booking_fee(amount, divisor):
    raw = (Decimal(amount) / Decimal(divisor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    rounded = (raw // Decimal("50")) * Decimal("50")
    if raw > 0 and rounded <= 0:
        rounded = Decimal("50")
    return rounded.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def count_overlapping_ukanc_bookings(connection, check_in, check_out):
    row = connection.execute(
        """
        select count(*) as booking_count
        from bookings b
        join bookable_units bu on bu.id = b.bookable_unit_id
        join locations l on l.id = bu.location_id
        where l.name in (?, ?)
          and b.status in ('pending', 'confirmed')
          and b.check_in < ?
          and b.check_out > ?
        """,
        ("Taborni prostor Ukanc", "Gozdna sola Ukanc", check_out.isoformat(), check_in.isoformat()),
    ).fetchone()
    return int(row["booking_count"]) if row else 0


def build_summary_breakdown(connection, unit, check_in, check_out, guest_count, member_category, boarding_option, laski_group_type, selected_rentals):
    total_nights = nights_between(check_in, check_out)
    rows = []
    total_amount = Decimal("0.00")
    summary_price_text = ""

    if is_ukanc_location(unit["location_name"]) and boarding_option:
        season = detect_pricing_season(check_in, check_out)
        seasons = detect_pricing_seasons(check_in, check_out)
        available_boarding = filter_boarding_options(
            UKANC_BOARDING_OPTIONS.get(member_category, UKANC_BOARDING_OPTIONS["other"]),
            guest_count,
            season,
            check_in,
            check_out,
        )
        selected_boarding_option = get_boarding_option(available_boarding, boarding_option)
        if selected_boarding_option:
            for current_season in seasons:
                season_nights = sum(1 for stay_date in daterange(check_in, check_out) if detect_date_season(stay_date) == current_season)
                if season_nights <= 0:
                    continue
                prices = selected_boarding_option["prices"]
                if current_season == "holiday" and "holiday" in prices:
                    rate = Decimal(prices["holiday"])
                elif current_season in prices:
                    rate = Decimal(prices[current_season])
                else:
                    continue
                charged_guests = guest_count
                label_suffix = season_label(current_season)
                if current_season == "low" and guest_count < 20:
                    charged_guests = 20
                    label_suffix += " (charged as 20 guests)"
                amount = (rate * charged_guests * season_nights).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                total_amount += amount
                rows.append({
                    "label": f"{selected_boarding_option['label']} - {label_suffix}",
                    "participants": str(charged_guests),
                    "nights": str(season_nights),
                    "price": format_currency(rate),
                    "amount": format_currency(amount),
                })
            cleaning_base = Decimal("100.00")
            cleaning_amount = cleaning_base / 2 if count_overlapping_ukanc_bookings(connection, check_in, check_out) > 0 else cleaning_base
            total_amount += cleaning_amount
            rows.append({
                "label": "Final cleaning",
                "participants": "1",
                "nights": "1",
                "price": format_currency(cleaning_base),
                "amount": format_currency(cleaning_amount),
                "note": "50%" if cleaning_amount != cleaning_base else "",
            })
            summary_price_text = " | ".join(format_boarding_prices(selected_boarding_option, seasons))
    elif is_laski_location(unit["location_name"]) and laski_group_type == "taborniki_zts":
        remaining = guest_count
        bands = [
            ("Accommodation fee - first 50 participants", 50, Decimal("2.00")),
            ("Accommodation fee - participants 51-100", 50, Decimal("1.70")),
            ("Accommodation fee - participants 101+", 10**9, Decimal("1.40")),
        ]
        for label, limit, rate in bands:
            band_guests = min(remaining, limit)
            if band_guests <= 0:
                continue
            amount = (Decimal(band_guests) * rate * total_nights).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            total_amount += amount
            rows.append({
                "label": label,
                "participants": str(band_guests),
                "nights": str(total_nights),
                "price": format_currency(rate),
                "amount": format_currency(amount),
            })
            remaining -= band_guests
        nightly_total = calculate_laski_zts_nightly_total(guest_count)
        average = (nightly_total / Decimal(guest_count)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        summary_price_text = f"Estimated average {format_currency(average)} per person per night"
    else:
        rate = money(unit["price_per_guest_per_night"])
        amount = (rate * guest_count * total_nights).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total_amount += amount
        rows.append({
            "label": "Accommodation fee",
            "participants": str(guest_count),
            "nights": str(total_nights),
            "price": format_currency(rate),
            "amount": format_currency(amount),
        })
        summary_price_text = f"{format_currency(rate)} per guest per night"

    for entry in selected_rentals:
        item = entry["item"]
        quantity = Decimal(str(entry["quantity"]))
        rate = parse_decimal_amount(item["price"])
        amount = (rate * quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total_amount += amount
        label = item["label"]
        if entry.get("length"):
            label += f" ({entry['length']})"
        rows.append({
            "label": label,
            "participants": entry["quantity"],
            "nights": "1",
            "price": format_currency(rate),
            "amount": format_currency(amount),
        })

    if is_ukanc_location(unit["location_name"]):
        booking_fee = round_booking_fee(total_amount * Decimal("0.20"), 1)
        booking_fee_label = "Booking fee (approx. 20% of the total amount)"
        second_payment_label = "Second payment - 1 week before the arrival"
    else:
        booking_fee = round_booking_fee(total_amount, 3)
        booking_fee_label = "Booking fee (approx. 1/3 of the total amount)"
        second_payment_label = "Second payment - 1 week before the arrival"
    second_payment = (total_amount - booking_fee).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return {
        "rows": rows,
        "total_nights": total_nights,
        "total_amount": total_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "summary_price_text": summary_price_text,
        "booking_fee": booking_fee,
        "booking_fee_label": booking_fee_label,
        "second_payment": second_payment,
        "second_payment_label": second_payment_label,
    }


def render_breakdown_table(breakdown):
    row_html = []
    for row in breakdown["rows"]:
        note_cell = f'<td>{html.escape(row.get("note", ""))}</td>'
        row_html.append(
            f"""
            <tr>
              <td>{html.escape(row['label'])}</td>
              {note_cell}
              <td>{html.escape(row['participants'])}</td>
              <td>{html.escape(row['nights'])}</td>
              <td>{html.escape(row['price'])}</td>
              <td>{html.escape(row['amount'])}</td>
            </tr>
            """
        )
    row_html.append(
        f"""
        <tr class="summary-total-row">
          <td>TOTAL AMOUNT</td>
          <td></td>
          <td></td>
          <td></td>
          <td></td>
          <td>{html.escape(format_currency(breakdown['total_amount']))}</td>
        </tr>
        <tr>
          <td>{html.escape(breakdown['booking_fee_label'])}</td>
          <td></td>
          <td></td>
          <td></td>
          <td></td>
          <td>{html.escape(format_currency(breakdown['booking_fee']))}</td>
        </tr>
        <tr>
          <td>{html.escape(breakdown['second_payment_label'])}</td>
          <td></td>
          <td></td>
          <td></td>
          <td></td>
          <td>{html.escape(format_currency(breakdown['second_payment']))}</td>
        </tr>
        """
    )
    return f"""
    <div class="table-wrap summary-breakdown-wrap">
      <table class="summary-breakdown-table">
        <thead>
          <tr>
            <th>Item</th>
            <th>Discounts / note</th>
            <th>Participants / qty</th>
            <th>Nights</th>
            <th>Price</th>
            <th>Amount</th>
          </tr>
        </thead>
        <tbody>
          {''.join(row_html)}
        </tbody>
      </table>
    </div>
    """


def render_detail_group(title, rows):
    row_html = "".join(
        f"""
        <tr>
          <th>{html.escape(label)}</th>
          <td>{html.escape(value)}</td>
        </tr>
        """
        for label, value in rows
    )
    return f"""
    <section class="summary-detail-group">
      <h3>{html.escape(title)}</h3>
      <div class="table-wrap">
        <table class="summary-detail-table">
          <tbody>
            {row_html}
          </tbody>
        </table>
      </div>
    </section>
    """


def render_submitted_group_details(data, lang):
    not_specified = t(lang, "not_specified")
    sections = ", ".join(data["selected_sections"]) if data["selected_sections"] else not_specified
    rentals = ", ".join(data["selected_rentals"]) if data["selected_rentals"] else not_specified
    blocks = [
        render_detail_group("Scout unit details", [
            ("National scout organization", data["organization_name"] or not_specified),
            ("Local scout unit", data["group_name"] or not_specified),
            ("Exact address of the unit", data["group_location"] or not_specified),
            ("VAT number", data["vat_number"] or not_specified),
            ("Country", data["country"] or not_specified),
        ]),
        render_detail_group("Participants", [
            ("Sections", sections),
            ("Adults", data["adult_count"] or not_specified),
            ("Children", data["child_count"] or not_specified),
            ("Total participants", data["guest_count"] or not_specified),
        ]),
        render_detail_group("Unit leader", [
            ("Name, surname", data["unit_leader_name"] or not_specified),
            ("Address", data["unit_leader_address"] or not_specified),
            ("E-mail", data["unit_leader_email"] or not_specified),
            ("Reachable telephone number", data["unit_leader_phone"] or not_specified),
        ]),
        render_detail_group("Contact person", [
            ("Name, surname", data["contact_person_name"] or not_specified),
            ("Address", data["contact_person_address"] or not_specified),
            ("E-mail", data["contact_person_email"] or not_specified),
            ("Reachable telephone number", data["contact_person_phone"] or not_specified),
        ]),
        render_detail_group("International commissioner", [
            ("Name, surname", data["international_commissioner_name"] or not_specified),
            ("Address", data["international_commissioner_address"] or not_specified),
            ("E-mail", data["international_commissioner_email"] or not_specified),
            ("Telephone", data["international_commissioner_phone"] or not_specified),
        ]),
        render_detail_group("Travel and stay", [
            ("Dates of travel", f"{data['check_in']} to {data['check_out']}"),
            ("Preferred arrival time", data["preferred_arrival_slot"] or not_specified),
            ("Additional note about arrival", data["preferred_arrival_note"] or not_specified),
            ("Preferred departure time", data["preferred_departure_slot"] or not_specified),
            ("Additional note about departure", data["preferred_departure_note"] or not_specified),
        ]),
        render_detail_group("Special requirements", [
            ("Rentals", rentals),
            ("Rental comments", data["rental_comments"] or not_specified),
            ("Other notes", data["notes"] or not_specified),
        ]),
    ]
    return '<div class="summary-detail-grid">' + "".join(blocks) + '</div>'


def build_submitted_group_details_html(data, lang):
    return render_submitted_group_details(data, lang)


def build_booking_summary_data(connection, unit, params):
    check_in = params.get("check_in", "")
    check_out = params.get("check_out", "")
    guest_count = params.get("guest_count", "1")
    unit_leader_name = params.get("unit_leader_name", "")
    unit_leader_address = params.get("unit_leader_address", "")
    unit_leader_email = params.get("unit_leader_email", "")
    unit_leader_phone = params.get("unit_leader_phone", "")
    contact_same_as_unit_leader = params.get("contact_same_as_unit_leader", "") == "on"
    contact_person_name = params.get("contact_person_name", "")
    contact_person_phone = params.get("contact_person_phone", "")
    contact_person_address = params.get("contact_person_address", "")
    contact_person_email = params.get("contact_person_email", "")
    if contact_same_as_unit_leader:
        contact_person_name = unit_leader_name
        contact_person_address = unit_leader_address
        contact_person_email = unit_leader_email
        contact_person_phone = unit_leader_phone
    international_commissioner_name = params.get("international_commissioner_name", "")
    international_commissioner_address = params.get("international_commissioner_address", "")
    international_commissioner_email = params.get("international_commissioner_email", "")
    international_commissioner_phone = params.get("international_commissioner_phone", "")
    notes = params.get("notes", "")
    member_category = params.get("member_category", "")
    boarding_option = params.get("boarding_option", "")
    laski_group_type = params.get("laski_group_type", "")
    preferred_arrival_slot = params.get("preferred_arrival_slot", "")
    preferred_arrival_note = params.get("preferred_arrival_note", "")
    preferred_departure_slot = params.get("preferred_departure_slot", "")
    preferred_departure_note = params.get("preferred_departure_note", "")
    group_name = params.get("group_name", "")
    organization_name = params.get("organization_name", "")
    group_location = params.get("group_location", "")
    vat_number = params.get("vat_number", "")
    country = params.get("country", "")
    rental_comments = params.get("rental_comments", "")
    adult_total, child_total, section_rows = calculate_section_totals(params)
    adult_count = str(adult_total)
    child_count = str(child_total)
    selected_rentals = parse_rental_quantities(params)
    selected_sections = [f'{row["label"]}: {row["count"]}' for row in section_rows if row["selected"]]
    breakdown = build_summary_breakdown(
        connection,
        unit,
        parse_date(check_in),
        parse_date(check_out),
        int(guest_count),
        member_category,
        boarding_option,
        laski_group_type,
        selected_rentals,
    )
    details_data = {
        "organization_name": organization_name,
        "group_name": group_name,
        "group_location": group_location,
        "vat_number": vat_number,
        "country": country,
        "selected_sections": selected_sections,
        "adult_count": adult_count,
        "child_count": child_count,
        "guest_count": guest_count,
        "unit_leader_name": unit_leader_name,
        "unit_leader_address": unit_leader_address,
        "unit_leader_email": unit_leader_email,
        "unit_leader_phone": unit_leader_phone,
        "contact_person_name": contact_person_name,
        "contact_person_address": contact_person_address,
        "contact_person_email": contact_person_email,
        "contact_person_phone": contact_person_phone,
        "international_commissioner_name": international_commissioner_name,
        "international_commissioner_address": international_commissioner_address,
        "international_commissioner_email": international_commissioner_email,
        "international_commissioner_phone": international_commissioner_phone,
        "check_in": check_in,
        "check_out": check_out,
        "preferred_arrival_slot": preferred_arrival_slot,
        "preferred_arrival_note": preferred_arrival_note,
        "preferred_departure_slot": preferred_departure_slot,
        "preferred_departure_note": preferred_departure_note,
        "selected_rentals": [
            f"{entry['item']['label']} x{entry['quantity']}" + (f" ({entry['length']})" if entry['length'] else "")
            for entry in selected_rentals
        ],
        "rental_comments": rental_comments,
        "notes": notes,
    }
    return {
        "details_data": details_data,
        "breakdown": breakdown,
        "contact_person_name": contact_person_name,
        "contact_person_email": contact_person_email,
        "contact_person_phone": contact_person_phone,
    }


def render_rental_item_row(item, params, lang, admin_mode, return_to):
    item_key = item["key"]
    enabled_value = params.get(f"rental_{item_key}_enabled", "no")
    gallery_images = get_rental_item_gallery(item_key)
    gallery_html = ""
    if admin_mode:
        lead_image = gallery_images[0]
        gallery_html = f"""
        <div class="rental-gallery-admin">
          <img src="{lead_image["url"]}" alt="{html.escape(item["label"])}" class="rental-item-image">
          {render_gallery_admin_controls(lang, "rental_item", item_key, "", lead_image, return_to=return_to) if lead_image.get("filename") else ""}
          {render_upload_form(lang, "rental_item", item_key, "", f"Add picture for {item['label']}", extra_class="upload-form--unit", return_to=return_to)}
        </div>
        """
    return f"""
    <div class="rental-item-wrap">
      <label class="rental-row">
        <span class="rental-meta">
          <strong>{html.escape(item["label"])}</strong>
          <span>{html.escape(item["note"]) if item["note"] else ""}</span>
        </span>
        <span class="rental-price">{html.escape(item["price"])}</span>
        <span class="rental-choice">
          <label><input type="radio" name="rental_{item_key}_enabled" value="no" {"checked" if enabled_value != "yes" else ""}> No</label>
          <label><input type="radio" name="rental_{item_key}_enabled" value="yes" {"checked" if enabled_value == "yes" else ""}> Yes</label>
        </span>
        {render_rental_quantity_select(item, params.get(f"rental_{item_key}", ""))}
      </label>
      {f'''
      <div class="rental-extra">
        <label>
          Approximate length of the logs (write as 5x 5m, 6x 4m)
          <input type="text" class="rental-extra-input" data-rental-key="{item_key}" name="rental_{item_key}_length" value="{html.escape(params.get(f"rental_{item_key}_length", ""))}">
        </label>
      </div>
      ''' if item.get("requires_length") else ''}
      {gallery_html}
    </div>
    """


def to_non_negative_int(value):
    try:
        return max(0, int(str(value).strip() or "0"))
    except (TypeError, ValueError):
        return 0


def calculate_section_totals(source):
    adults = 0
    children = 0
    rows = []
    for key, label in GROUP_SECTION_OPTIONS:
        selected = bool(source.get(f"section_{key}_selected"))
        count = to_non_negative_int(source.get(f"section_{key}_count", "0"))
        rows.append({"key": key, "label": label, "selected": selected, "count": count})
        if not selected:
            continue
        if key in ADULT_SECTION_KEYS:
            adults += count
        else:
            children += count
    return adults, children, rows


def validate_group_details_params(params):
    errors = []
    if not params.get("group_name", "").strip():
        errors.append("Local scout unit is required.")
    if not params.get("group_location", "").strip():
        errors.append("Exact address of the unit is required.")
    if not params.get("organization_name", "").strip():
        errors.append("National scout organization is required.")
    if not params.get("vat_number", "").strip():
        errors.append("VAT number is required.")
    adults, children, _ = calculate_section_totals(params)
    total = adults + children
    expected_total = to_non_negative_int(params.get("guest_count", "0"))
    if total != expected_total:
        errors.append(f"Section total must equal the guest count ({expected_total}).")
    return errors


def validate_contact_details_params(params):
    errors = []
    required_fields = [
        ("unit_leader_name", "Unit leader name is required."),
        ("unit_leader_address", "Unit leader address is required."),
        ("unit_leader_email", "Unit leader email is required."),
        ("unit_leader_phone", "Unit leader telephone number is required."),
    ]
    for field_name, message in required_fields:
        if not params.get(field_name, "").strip():
            errors.append(message)
    same_as_unit_leader = params.get("contact_same_as_unit_leader", "") == "on"
    if not same_as_unit_leader:
        contact_required = [
            ("contact_person_name", "Contact person name is required."),
            ("contact_person_phone", "Reachable telephone number is required."),
            ("contact_person_address", "Contact person address is required."),
            ("contact_person_email", "Contact person email is required."),
        ]
        for field_name, message in contact_required:
            if not params.get(field_name, "").strip():
                errors.append(message)
    return errors


def display_location_name(name, lang):
    return LOCATION_LABELS.get(name, {}).get(get_lang(lang), name)


def display_unit_name(name, lang):
    if name.startswith("Subcamp "):
        return f"{t(lang, 'subcamp')} {name.split(' ', 1)[1]}"
    return name


def translate_location_type(value, lang):
    return t(lang, f"location_type_{value}")


def slugify_location_name(name):
    return (
        name.lower()
        .replace("š", "s")
        .replace("ž", "z")
        .replace("č", "c")
        .replace(" ", "-")
    )


def gallery_dir_for_target(target_type, location_name, unit_name=""):
    base = STATIC_DIR / "galleries" / slugify_location_name(location_name)
    if target_type == "location":
        return base
    if target_type == "unit":
        return base / slugify_location_name(unit_name)
    if target_type == "rental_item":
        return STATIC_DIR / "galleries" / "rentals" / slugify_location_name(location_name)
    return None


def load_gallery_captions(gallery_dir):
    captions_path = gallery_dir / "captions.json"
    if not captions_path.exists():
        return {}
    try:
        return json.loads(captions_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_gallery_captions(gallery_dir, captions):
    captions_path = gallery_dir / "captions.json"
    captions_path.write_text(json.dumps(captions, indent=2), encoding="utf-8")


def list_gallery_items(gallery_dir, web_prefix):
    items = []
    captions = load_gallery_captions(gallery_dir)
    if gallery_dir.exists():
        for pattern in ("*.jpg", "*.jpeg", "*.png", "*.webp", "*.svg"):
            for path in sorted(gallery_dir.glob(pattern)):
                items.append(
                    {
                        "url": f"{web_prefix}/{path.name}",
                        "filename": path.name,
                        "caption": captions.get(path.name, ""),
                    }
                )
    return items


def get_location_gallery(location_name):
    gallery_dir = gallery_dir_for_target("location", location_name)
    items = list_gallery_items(gallery_dir, f"/static/galleries/{gallery_dir.name}")
    if items:
        return items
    return [{"url": "/static/placeholder-campsite.svg", "filename": "", "caption": ""}]


def get_unit_gallery(location_name, unit_name):
    gallery_dir = gallery_dir_for_target("unit", location_name, unit_name)
    return list_gallery_items(
        gallery_dir,
        f"/static/galleries/{slugify_location_name(location_name)}/{gallery_dir.name}",
    )


def get_rental_item_gallery(item_key):
    gallery_dir = gallery_dir_for_target("rental_item", item_key)
    items = list_gallery_items(gallery_dir, f"/static/galleries/rentals/{gallery_dir.name}")
    if items:
        return items
    return [{"url": "/static/placeholder-campsite.svg", "filename": "", "caption": ""}]


def get_cookie_value(environ, name):
    raw = environ.get("HTTP_COOKIE", "")
    cookie = SimpleCookie()
    cookie.load(raw)
    if name in cookie:
        return cookie[name].value
    return ""


def is_admin_request(environ):
    return get_cookie_value(environ, "campsite_admin") == "1"


def smtp_is_configured():
    return bool(SMTP_HOST and SMTP_FROM_EMAIL)


def resend_is_configured():
    return bool(RESEND_API_KEY and (RESEND_FROM_EMAIL or SMTP_FROM_EMAIL))


def email_is_configured():
    return resend_is_configured() or smtp_is_configured()


def save_uploaded_image(environ):
    form = cgi.FieldStorage(fp=environ["wsgi.input"], environ=environ, keep_blank_values=True)
    lang = get_lang(form.getfirst("lang", "en"))
    return_to = form.getfirst("return_to", "/")
    if not is_admin_request(environ):
        return lang, "Admin login required.", return_to
    target_type = form.getfirst("target_type", "")
    location_name = form.getfirst("location_name", "")
    unit_name = form.getfirst("unit_name", "")
    upload = form["image"] if "image" in form else None
    if upload is None or not getattr(upload, "filename", ""):
        return lang, "No image selected.", return_to

    original_name = Path(upload.filename).name
    suffix = Path(original_name).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".svg"}:
        return lang, "Unsupported image type.", return_to

    target_dir = gallery_dir_for_target(target_type, location_name, unit_name)
    if target_dir is None:
        return lang, "Invalid upload target.", return_to

    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    safe_name = f"{timestamp}{suffix}"
    target_path = target_dir / safe_name
    with open(target_path, "wb") as output_file:
        output_file.write(upload.file.read())
    return lang, "Image uploaded.", return_to


def delete_gallery_image(environ):
    form = read_post_data(environ)
    lang = get_lang(form.get("lang", "en"))
    return_to = form.get("return_to", "/")
    if not is_admin_request(environ):
        return lang, "Admin login required.", return_to
    target_dir = gallery_dir_for_target(form.get("target_type", ""), form.get("location_name", ""), form.get("unit_name", ""))
    if target_dir is None:
        return lang, "Invalid gallery target.", return_to
    filename = Path(form.get("filename", "")).name
    if not filename:
        return lang, "Missing filename.", return_to
    image_path = target_dir / filename
    if image_path.exists():
        image_path.unlink()
    captions = load_gallery_captions(target_dir)
    captions.pop(filename, None)
    save_gallery_captions(target_dir, captions)
    return lang, "Image deleted.", return_to


def sync_seed_data(connection):
    existing_locations = {
        row["display_order"]: row
        for row in connection.execute(
            "select id, display_order from locations order by display_order"
        )
    }

    active_location_ids = []
    for location in SEEDED_LOCATIONS:
        existing = existing_locations.get(location["display_order"])
        if existing:
            connection.execute(
                """
                update locations
                set name = ?, type = ?, is_active = 1
                where id = ?
                """,
                (location["name"], location["type"], existing["id"]),
            )
            location_id = existing["id"]
        else:
            cursor = connection.execute(
                """
                insert into locations (name, type, is_active, display_order)
                values (?, ?, 1, ?)
                """,
                (location["name"], location["type"], location["display_order"]),
            )
            location_id = cursor.lastrowid
        active_location_ids.append(location_id)

        existing_units = {
            row["display_order"]: row
            for row in connection.execute(
                """
                select id, display_order
                from bookable_units
                where location_id = ?
                order by display_order
                """,
                (location_id,),
            )
        }
        active_unit_ids = []
        for unit in location["units"]:
            existing_unit = existing_units.get(unit["display_order"])
            if existing_unit:
                connection.execute(
                    """
                    update bookable_units
                    set name = ?, max_guests = ?, price_per_guest_per_night = ?, is_active = 1
                    where id = ?
                    """,
                    (unit["name"], unit["max_guests"], unit["price"], existing_unit["id"]),
                )
                unit_id = existing_unit["id"]
            else:
                cursor = connection.execute(
                    """
                    insert into bookable_units (
                        location_id, name, max_guests, price_per_guest_per_night, is_active, display_order
                    ) values (?, ?, ?, ?, 1, ?)
                    """,
                    (
                        location_id,
                        unit["name"],
                        unit["max_guests"],
                        unit["price"],
                        unit["display_order"],
                    ),
                )
                unit_id = cursor.lastrowid
            active_unit_ids.append(unit_id)

        if active_unit_ids:
            placeholders = ", ".join("?" for _ in active_unit_ids)
            connection.execute(
                f"""
                update bookable_units
                set is_active = 0
                where location_id = ?
                  and id not in ({placeholders})
                """,
                [location_id, *active_unit_ids],
            )

    if active_location_ids:
        placeholders = ", ".join("?" for _ in active_location_ids)
        connection.execute(
            f"""
            update locations
            set is_active = 0
            where id not in ({placeholders})
            """,
            active_location_ids,
        )


def init_db():
    with closing(get_connection()) as connection:
        connection.executescript(
            """
            create table if not exists locations (
                id integer primary key autoincrement,
                name text not null,
                type text not null check (type in ('campsite', 'house')),
                is_active integer not null default 1,
                display_order integer not null default 0,
                created_at text not null default current_timestamp
            );

            create table if not exists bookable_units (
                id integer primary key autoincrement,
                location_id integer not null references locations(id) on delete cascade,
                name text not null,
                max_guests integer not null check (max_guests > 0),
                price_per_guest_per_night numeric not null check (price_per_guest_per_night >= 0),
                is_active integer not null default 1,
                display_order integer not null default 0,
                created_at text not null default current_timestamp
            );

            create table if not exists bookings (
                id integer primary key autoincrement,
                bookable_unit_id integer not null references bookable_units(id) on delete restrict,
                guest_name text not null,
                guest_email text not null,
                guest_phone text,
                check_in text not null,
                check_out text not null,
                guest_count integer not null check (guest_count > 0),
                status text not null check (status in ('pending', 'confirmed', 'cancelled', 'rejected', 'expired')),
                total_price numeric not null check (total_price >= 0),
                created_by_admin integer not null default 0,
                overbook_allowed integer not null default 0,
                notes text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                check (check_out > check_in)
            );

            create index if not exists idx_bookable_units_location_id
                on bookable_units(location_id);

            create index if not exists idx_bookings_unit_dates
                on bookings(bookable_unit_id, check_in, check_out);

            create index if not exists idx_bookings_status
                on bookings(status);
            """
        )
        sync_seed_data(connection)
        connection.commit()


def parse_date(value):
    return datetime.strptime(value, DATE_FMT).date()


def daterange(start_date, end_date):
    current = start_date
    while current < end_date:
        yield current
        current += timedelta(days=1)


def money(value):
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def nights_between(check_in, check_out):
    return (check_out - check_in).days


def calculate_total_price(price_per_guest_per_night, guest_count, check_in, check_out):
    return money(price_per_guest_per_night) * guest_count * nights_between(check_in, check_out)


def get_unit(connection, unit_id):
    return connection.execute(
        """
        select
            bu.id,
            bu.location_id,
            bu.name as unit_name,
            bu.max_guests,
            bu.price_per_guest_per_night,
            l.name as location_name,
            l.type as location_type
        from bookable_units bu
        join locations l on l.id = bu.location_id
        where bu.id = ? and bu.is_active = 1 and l.is_active = 1
        """,
        (unit_id,),
    ).fetchone()


def get_reserved_guests_by_day(connection, unit_id, check_in, check_out, exclude_booking_id=None):
    reservations = {}
    sql = """
        select check_in, check_out, guest_count
        from bookings
        where bookable_unit_id = ?
          and status in ('pending', 'confirmed')
          and check_in < ?
          and check_out > ?
    """
    params = [unit_id, check_out.isoformat(), check_in.isoformat()]
    if exclude_booking_id is not None:
        sql += " and id != ?"
        params.append(exclude_booking_id)

    for row in connection.execute(sql, params):
        row_start = parse_date(row["check_in"])
        row_end = parse_date(row["check_out"])
        for stay_date in daterange(max(check_in, row_start), min(check_out, row_end)):
            reservations[stay_date] = reservations.get(stay_date, 0) + row["guest_count"]
    return reservations


def capacity_check(connection, unit_id, check_in, check_out, guest_count, exclude_booking_id=None):
    unit = get_unit(connection, unit_id)
    if not unit:
        return None, ["Selected unit does not exist."]

    reservations = get_reserved_guests_by_day(
        connection, unit_id, check_in, check_out, exclude_booking_id=exclude_booking_id
    )
    violations = []
    nightly = []
    for stay_date in daterange(check_in, check_out):
        reserved = reservations.get(stay_date, 0)
        available = unit["max_guests"] - reserved
        can_fit = reserved + guest_count <= unit["max_guests"]
        nightly.append(
            {
                "date": stay_date.isoformat(),
                "reserved": reserved,
                "available": available,
                "can_fit": can_fit,
            }
        )
        if not can_fit:
            violations.append(
                f"{stay_date.isoformat()}: only {max(available, 0)} guest spots left"
            )
    return {"unit": unit, "nightly": nightly}, violations


def fetch_locations(connection):
    rows = connection.execute(
        """
        select
            l.id as location_id,
            l.name as location_name,
            l.type as location_type,
            l.display_order as location_display_order,
            bu.id as unit_id,
            bu.name as unit_name,
            bu.max_guests,
            bu.price_per_guest_per_night,
            bu.display_order as unit_display_order
        from locations l
        join bookable_units bu on bu.location_id = l.id
        where l.is_active = 1 and bu.is_active = 1
        order by l.display_order, bu.display_order, bu.id
        """
    ).fetchall()
    grouped = []
    current = None
    for row in rows:
        if not current or current["id"] != row["location_id"]:
            current = {
                "id": row["location_id"],
                "name": row["location_name"],
                "type": row["location_type"],
                "units": [],
            }
            grouped.append(current)
        current["units"].append(
            {
                "id": row["unit_id"],
                "name": row["unit_name"],
                "max_guests": row["max_guests"],
                "price_per_guest_per_night": money(row["price_per_guest_per_night"]),
            }
        )
    return grouped


def fetch_bookings(connection):
    return connection.execute(
        """
        select
            b.*,
            bu.name as unit_name,
            l.name as location_name
        from bookings b
        join bookable_units bu on bu.id = b.bookable_unit_id
        join locations l on l.id = bu.location_id
        order by b.created_at desc, b.id desc
        """
    ).fetchall()


def booking_status_class(status):
    return {
        "pending": "is-pending",
        "confirmed": "is-confirmed",
        "cancelled": "is-cancelled",
        "rejected": "is-rejected",
        "expired": "is-expired",
    }.get(status, "is-pending")


def assign_booking_tracks(bookings):
    tracks = []
    assigned = []
    for booking in sorted(bookings, key=lambda item: (item["check_in"], item["check_out"], item["id"])):
        for index, track_end in enumerate(tracks):
            if booking["check_in"] >= track_end:
                tracks[index] = booking["check_out"]
                assigned.append((booking, index))
                break
        else:
            tracks.append(booking["check_out"])
            assigned.append((booking, len(tracks) - 1))
    return assigned, max(1, len(tracks))


def render_admin_booking_board(connection, locations, bookings):
    today = datetime.now().date()
    board_start = datetime(today.year, 1, 1).date()
    board_last_year = today.year + 2
    board_end = datetime(board_last_year + 1, 1, 1).date()
    range_days = (board_end - board_start).days
    today_offset = (today - board_start).days
    month_cells = []
    day_cells = []
    current_month_label = None
    current_month_count = 0
    for offset in range(range_days):
        current = board_start + timedelta(days=offset)
        month_label = current.strftime("%B %Y")
        if current_month_label is None:
            current_month_label = month_label
            current_month_count = 1
        elif month_label == current_month_label:
            current_month_count += 1
        else:
            month_cells.append(
                f'<div class="board-month" style="grid-column: span {current_month_count};">{html.escape(current_month_label)}</div>'
            )
            current_month_label = month_label
            current_month_count = 1
        classes = ["board-day"]
        if current.weekday() >= 5:
            classes.append("is-weekend")
        day_cells.append(
            f'<div class="{" ".join(classes)}"><span>{current.day}</span></div>'
        )
    if current_month_label is not None:
        month_cells.append(
            f'<div class="board-month" style="grid-column: span {current_month_count};">{html.escape(current_month_label)}</div>'
        )

    bookings_by_unit = {}
    for booking in bookings:
        normalized = {
            "id": booking["id"],
            "guest_name": booking["guest_name"],
            "guest_count": booking["guest_count"],
            "status": booking["status"],
            "check_in": parse_date(booking["check_in"]),
            "check_out": parse_date(booking["check_out"]),
            "unit_id": booking["bookable_unit_id"],
            "location_name": booking["location_name"],
        }
        bookings_by_unit.setdefault(booking["bookable_unit_id"], []).append(normalized)

    location_sections = []
    for location in locations:
        unit_rows = []
        for unit in location["units"]:
            relevant_bookings = []
            for booking in bookings_by_unit.get(unit["id"], []):
                if booking["check_in"] < board_end and booking["check_out"] > board_start:
                    relevant_bookings.append(booking)
            assigned, track_count = assign_booking_tracks(relevant_bookings)
            bars = []
            for booking, track_index in assigned:
                visible_start = max(booking["check_in"], board_start)
                visible_end = min(booking["check_out"], board_end)
                span_days = max(1, (visible_end - visible_start).days)
                start_offset = (visible_start - board_start).days
                left = (start_offset / range_days) * 100
                width = (span_days / range_days) * 100
                top = 0.35 + (track_index * 2.2)
                bars.append(
                    f'''
                    <a class="booking-bar {booking_status_class(booking["status"])}"
                       href="#booking-{booking["id"]}"
                       style="left:{left:.4f}%; width:{width:.4f}%; top:{top:.2f}rem;">
                      <strong>{html.escape(booking["guest_name"])}</strong>
                      <span>{booking["guest_count"]} guests</span>
                    </a>
                    '''
                )
            unit_rows.append(
                f'''
                <div class="booking-board-row">
                  <div class="booking-board-label">
                    <strong>{html.escape(unit["name"])}</strong>
                    <span>{unit["max_guests"]} guests max</span>
                  </div>
                  <div class="booking-board-track" style="min-height:{(track_count * 2.2) + 0.7:.2f}rem;">
                    <div class="booking-board-grid">
                      {''.join('<span class="booking-board-cell"></span>' for _ in range(range_days))}
                    </div>
                    {''.join(bars) if bars else '<p class="booking-board-empty">No reservations in this period.</p>'}
                  </div>
                </div>
                '''
            )
        location_sections.append(
            f'''
            <section class="panel admin-board-section">
              <div class="location-heading">
                <h2>{html.escape(location["name"])}</h2>
                <p>Reservations by unit</p>
              </div>
              <div class="booking-board-scroll" data-today-offset="{today_offset}" data-range-days="{range_days}">
                <div class="booking-board-canvas">
                  <div class="booking-board-header">
                    <div class="booking-board-label booking-board-label--header">Unit</div>
                    <div class="booking-board-headings">
                      <div class="booking-board-months">{''.join(month_cells)}</div>
                      <div class="booking-board-days">{''.join(day_cells)}</div>
                    </div>
                  </div>
                  <div class="booking-board">
                    {''.join(unit_rows)}
                  </div>
                </div>
              </div>
            </section>
            '''
        )
    return "".join(location_sections)


def parse_accommodation_types(params):
    if hasattr(params, "getall"):
        values = params.getall("accommodation_type")
    else:
        value = params.get("accommodation_type", "")
        if isinstance(value, list):
            values = value
        elif value:
            values = [value]
        else:
            values = []
    normalized = []
    for value in values:
        parts = [item.strip() for item in str(value).split(",")]
        for part in parts:
            if part and part not in normalized:
                normalized.append(part)
    return normalized


def first_param(params, key, default=""):
    value = params.get(key, default)
    if isinstance(value, list):
        return value[0] if value else default
    return value


def is_ukanc_location(location_name):
    return location_name in UKANC_LOCATION_NAMES


def is_laski_location(location_name):
    return location_name in LASKI_LOCATION_NAMES


def is_slovenia_country(value):
    normalized = value.strip().lower()
    return normalized in {"slovenia", "slovenija", "republic of slovenia", "republika slovenija"}


def is_season_limited_location(location_name):
    return location_name in SEASON_LIMITED_LOCATION_NAMES


def seasonal_bounds_for_year(year):
    return datetime(year, 5, 15).date(), datetime(year, 9, 15).date()


def get_location_date_bounds(location_name, year):
    if not is_season_limited_location(location_name):
        return None, None
    return seasonal_bounds_for_year(year)


def is_location_date_range_allowed(location_name, check_in, check_out):
    if not is_season_limited_location(location_name):
        return True
    start_bound, end_bound = seasonal_bounds_for_year(check_in.year)
    return check_in.year == check_out.year and start_bound <= check_in < check_out <= end_bound


def detect_pricing_season(check_in, check_out):
    for stay_date in daterange(check_in, check_out):
        if (stay_date.month == 12 and stay_date.day >= 24) or (stay_date.month == 1 and stay_date.day <= 2):
            return "holiday"
    for stay_date in daterange(check_in, check_out):
        if (stay_date.month == 6 and stay_date.day >= 24) or stay_date.month in (7, 8):
            return "high"
    return "low"


def detect_date_season(stay_date):
    if (stay_date.month == 12 and stay_date.day >= 24) or (stay_date.month == 1 and stay_date.day <= 2):
        return "holiday"
    if (stay_date.month == 6 and stay_date.day >= 24) or stay_date.month in (7, 8):
        return "high"
    return "low"


def detect_pricing_seasons(check_in, check_out):
    seasons = []
    for stay_date in daterange(check_in, check_out):
        season = detect_date_season(stay_date)
        if season not in seasons:
            seasons.append(season)
    return seasons or ["low"]


def season_label(season):
    return {
        "high": "High season: 24 June to 31 August",
        "low": "Low season: 1 September to 23 June",
        "holiday": "Christmas/New Year period: 24.12 to 2.1",
    }[season]


def format_boarding_price(option, season):
    prices = option["prices"]
    if season == "holiday" and "holiday" in prices:
        return f"EUR {prices['holiday']} per person per night"
    if season in prices:
        return f"EUR {prices[season]} per person per night"
    fallback = prices.get("high") or prices.get("low") or prices.get("holiday")
    return f"EUR {fallback} per person per night"


def format_boarding_prices(option, seasons):
    lines = []
    for season in seasons:
        if season in option["prices"]:
            lines.append(f"{season_label(season)}: EUR {option['prices'][season]} per person per night")
        elif season == "holiday" and "holiday" in option["prices"]:
            lines.append(f"{season_label(season)}: EUR {option['prices']['holiday']} per person per night")
    if not lines:
        lines.append(format_boarding_price(option, seasons[0]))
    return lines


def calculate_ukanc_total(option, guest_count, check_in, check_out):
    total = Decimal("0.00")
    low_season_minimum_applied = False
    for stay_date in daterange(check_in, check_out):
        season = detect_date_season(stay_date)
        prices = option["prices"]
        if season == "holiday" and "holiday" in prices:
            rate = Decimal(prices["holiday"])
        elif season in prices:
            rate = Decimal(prices[season])
        else:
            fallback = prices.get("high") or prices.get("low") or prices.get("holiday")
            rate = Decimal(fallback)
        charged_guest_count = guest_count
        if season == "low" and guest_count < 20:
            charged_guest_count = 20
            low_season_minimum_applied = True
        total += rate * Decimal(charged_guest_count)
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), low_season_minimum_applied


def is_high_season_only_stay(check_in, check_out):
    seasons = detect_pricing_seasons(check_in, check_out)
    return seasons == ["high"]


def is_boarding_option_allowed(option_key, check_in, check_out):
    if option_key != "other_tent_selfcook":
        return True
    return is_high_season_only_stay(check_in, check_out)


def calculate_laski_zts_nightly_total(guest_count):
    remaining = guest_count
    total = Decimal("0.00")

    first_band = min(remaining, 50)
    total += Decimal(first_band) * Decimal("2.00")
    remaining -= first_band

    if remaining > 0:
        second_band = min(remaining, 50)
        total += Decimal(second_band) * Decimal("1.70")
        remaining -= second_band

    if remaining > 0:
        total += Decimal(remaining) * Decimal("1.40")

    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def describe_laski_price(guest_count, group_type):
    if group_type != "taborniki_zts":
        return None
    nightly_total = calculate_laski_zts_nightly_total(guest_count)
    average = (nightly_total / Decimal(guest_count)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if guest_count <= 50:
        rule = "Base price 2.00 EUR per person per night."
    elif guest_count <= 100:
        rule = "Guests 51-100 receive 15% discount, so those nights price at 1.70 EUR per person."
    else:
        rule = "Guests 51-100 receive 15% discount and guests 101+ receive 30% discount."
    return {
        "nightly_total": nightly_total,
        "average": average,
        "rule": rule,
    }


def filter_boarding_options(options, guest_count, season, check_in=None, check_out=None):
    filtered = []
    for option in options:
        min_guests = option.get("min_guests")
        max_guests = option.get("max_guests")
        if min_guests is not None and guest_count < min_guests:
            continue
        if max_guests is not None and guest_count > max_guests:
            continue
        if check_in and check_out and not is_boarding_option_allowed(option["key"], check_in, check_out):
            continue
        if season == "holiday" and "holiday" not in option["prices"] and option["key"] != "other_tent_selfcook":
            continue
        if season != "holiday" and "holiday" in option["prices"]:
            continue
        filtered.append(option)
    return filtered


def get_boarding_option(options, key):
    for option in options:
        if option["key"] == key:
            return option
    return options[0] if options else None


def render_steps(active_step, lang):
    steps = [
        ("Period", t(lang, "period")),
        ("Type", t(lang, "type")),
        ("Group details", t(lang, "group_details")),
        ("Rental", t(lang, "rental")),
        ("Contact details", t(lang, "contact_details")),
        ("Other information", t(lang, "other_information")),
        ("Summary", t(lang, "summary")),
    ]
    pills = []
    for step, label in steps:
        cls = "step-pill active" if step == active_step else "step-pill"
        pills.append(f'<span class="{cls}">{html.escape(label)}</span>')
    return f'<div class="stepper">{"".join(pills)}</div>'


def render_reservation_steps(active_step, lang):
    return render_steps(active_step, lang)


def build_type_query(params):
    query = {
        "location_id": params.get("location_id", ""),
        "check_in": params.get("check_in", ""),
        "check_out": params.get("check_out", ""),
        "guest_count": params.get("guest_count", ""),
    }
    if params.get("preferred_arrival_slot"):
        query["preferred_arrival_slot"] = params["preferred_arrival_slot"]
    if params.get("preferred_arrival_note"):
        query["preferred_arrival_note"] = params["preferred_arrival_note"]
    if params.get("preferred_departure_slot"):
        query["preferred_departure_slot"] = params["preferred_departure_slot"]
    if params.get("preferred_departure_note"):
        query["preferred_departure_note"] = params["preferred_departure_note"]
    if params.get("group_type"):
        query["group_type"] = params["group_type"]
    if params.get("accommodation_type"):
        query["accommodation_type"] = ",".join(params["accommodation_type"])
    return urlencode(query)


def render_type_page(connection, params, errors=None):
    errors = errors or []
    lang = get_lang(first_param(params, "lang", "en"))
    location_id = int(first_param(params, "location_id", "0") or "0")
    if not location_id:
        unit_id = int(first_param(params, "unit_id", "0") or "0")
        if unit_id:
            unit = get_unit(connection, unit_id)
            if unit:
                location_id = int(unit["location_id"])
    check_in = first_param(params, "check_in", "")
    check_out = first_param(params, "check_out", "")
    guest_count = first_param(params, "guest_count", "2")
    origin_country = first_param(params, "origin_country", "")
    preferred_arrival_slot = first_param(params, "preferred_arrival_slot", "")
    preferred_arrival_note = first_param(params, "preferred_arrival_note", "")
    preferred_departure_slot = first_param(params, "preferred_departure_slot", "")
    preferred_departure_note = first_param(params, "preferred_departure_note", "")
    member_category = first_param(params, "member_category", MEMBER_CATEGORIES[1][0])
    laski_group_type = first_param(params, "laski_group_type", LASKI_GROUP_TYPES[1][0])
    boarding_option = first_param(params, "boarding_option", "")
    locations = {location["id"]: location for location in fetch_locations(connection)}
    location = locations.get(location_id)
    if not location:
        return render_layout(
            t(lang, "type"),
            render_steps("Type", lang) + f'<section class="panel error"><p>{html.escape(t(lang, "selected_location_not_found"))}</p></section>',
            lang=lang,
            current_path="/type",
            current_params={key: first_param(params, key, "") for key in params.keys()},
        )

    requested_check_in = parse_date(check_in)
    requested_check_out = parse_date(check_out)
    requested_guest_count = int(guest_count)
    season = detect_pricing_season(requested_check_in, requested_check_out)
    seasons = detect_pricing_seasons(requested_check_in, requested_check_out)
    ukanc_flow = is_ukanc_location(location["name"])
    laski_flow = is_laski_location(location["name"])
    selected_boarding_option = None
    available_units = []
    for unit in location["units"]:
        details, violations = capacity_check(
            connection,
            unit["id"],
            requested_check_in,
            requested_check_out,
            requested_guest_count,
        )
        available_units.append(
            {
                "unit": unit,
                "available": not violations,
                "violations": violations,
                "details": details,
            }
        )

    error_html = ""
    if errors:
        items = "".join(f"<li>{html.escape(error)}</li>" for error in errors)
        error_html = f'<section class="panel error"><ul>{items}</ul></section>'
    preserved_type_fields = "".join(
        f'<input type="hidden" name="{html.escape(key)}" value="{html.escape(first_param(params, key, ""))}">'
        for key in params.keys()
        if key not in {"location_id", "lang", "boarding_option"}
    )

    pricing_note = ""
    selection_panel = ""
    if ukanc_flow:
        is_foreign_group = bool(origin_country.strip()) and not is_slovenia_country(origin_country)
        if is_foreign_group:
            member_category = "other"
        elif member_category not in {"zts_member", "other"}:
            member_category = MEMBER_CATEGORIES[1][0]

        available_boarding = filter_boarding_options(
            UKANC_BOARDING_OPTIONS[member_category],
            requested_guest_count,
            season,
            requested_check_in,
            requested_check_out,
        )
        if not boarding_option:
            boarding_option = available_boarding[0]["key"]
        selected_boarding_option = get_boarding_option(available_boarding, boarding_option)
        if selected_boarding_option:
            boarding_option = selected_boarding_option["key"]
        boarding_options = []
        for option in available_boarding:
            checked = " checked" if option["key"] == boarding_option else ""
            boarding_options.append(
                f"""
                <label class="choice-item">
                  <input type="radio" name="boarding_option" value="{option['key']}" class="boarding-option-input"{checked}>
                  <span>{html.escape(option['label'])}<br><small>{html.escape(format_boarding_price(option, season))}</small></span>
                </label>
                """
            )

        season_heading = " / ".join(season_label(item) for item in seasons)
        season_specific_lines = []
        if selected_boarding_option:
            season_specific_lines.extend(
                f"<p>{html.escape(selected_boarding_option['label'])}: {html.escape(line)}</p>"
                for line in format_boarding_prices(selected_boarding_option, seasons)
            )
        extra_note = ""
        if season == "holiday":
            extra_note = "<p>Christmas and New Year bookings require a minimum stay of 2 nights.</p>"
        elif member_category == "other" and selected_boarding_option and selected_boarding_option["key"] == "other_tent_selfcook":
            extra_note = "<p>If the group chooses only sleeping and cooks by itself, section B applies (the outside kitchen can accommodate up to 20 person).</p>"
        if "low" in seasons and requested_guest_count < 20:
            extra_note += "<p>Minimum stay is 2 full boardings and 20 person. If there is less than 20 person, it is calculated for 20 person.</p>"
        pricing_note = f"""
        <section class="panel">
          <div class="location-heading">
            <h2>Current pricing note</h2>
            <p>{html.escape(season_heading)}</p>
          </div>
          <div class="pricing-note">
            {''.join(season_specific_lines)}
            {extra_note}
          </div>
        </section>
        """
        selection_panel = f"""
        <section class="panel">
          <div class="location-heading">
            <h2>Type</h2>
            <p>{html.escape(season_heading)}</p>
          </div>
          <form method="get" action="/type" class="type-layout ukanc-type-form">
            <input type="hidden" name="location_id" value="{location_id}">
            <input type="hidden" name="lang" value="{lang}">
            {preserved_type_fields}
            <input type="hidden" name="member_category" value="{html.escape(member_category)}">
            <section class="choice-panel">
              <h3>Boarding type</h3>
              <div class="choice-list">
                {''.join(boarding_options)}
              </div>
            </section>
          </form>
        </section>
        <script>
        (() => {{
          const form = document.querySelector('.ukanc-type-form');
          if (!form) {{
            return;
          }}
          const boardingInputs = form.querySelectorAll('.boarding-option-input');
          boardingInputs.forEach((input) => {{
            input.addEventListener('change', () => {{
              form.submit();
            }});
          }});
        }})();
        </script>
        """
    elif laski_flow:
        group_options = []
        for value, label in LASKI_GROUP_TYPES:
            checked = " checked" if value == laski_group_type else ""
            group_options.append(
                f"""
                <label class="choice-item">
                  <input type="radio" name="laski_group_type" value="{value}"{checked}>
                  <span>{html.escape(label)}</span>
                </label>
                """
            )
        pricing_note = ""
        selection_panel = f"""
        <section class="panel">
          <div class="location-heading">
            <h2>Type</h2>
            <p>Choose if you are a member of the Scout association of Slovenia (Taborniki).</p>
          </div>
          <form method="get" action="/type" class="type-layout">
            <input type="hidden" name="location_id" value="{location_id}">
            <input type="hidden" name="lang" value="{lang}">
            <input type="hidden" name="check_in" value="{html.escape(check_in)}">
            <input type="hidden" name="check_out" value="{html.escape(check_out)}">
            <input type="hidden" name="guest_count" value="{html.escape(guest_count)}">
            <input type="hidden" name="preferred_arrival_slot" value="{html.escape(preferred_arrival_slot)}">
            <input type="hidden" name="preferred_arrival_note" value="{html.escape(preferred_arrival_note)}">
            <input type="hidden" name="preferred_departure_slot" value="{html.escape(preferred_departure_slot)}">
            <input type="hidden" name="preferred_departure_note" value="{html.escape(preferred_departure_note)}">
            <section class="choice-panel">
              <h3>Type of group</h3>
              <div class="choice-list">
                {''.join(group_options)}
              </div>
              <button type="submit">Update options</button>
            </section>
          </form>
        </section>
        """

    show_unit_names = len(location["units"]) > 1
    unit_cards = []
    for item in available_units:
        unit = item["unit"]
        if item["available"]:
            query_data = {key: first_param(params, key, "") for key in params.keys()}
            query_data["unit_id"] = unit["id"]
            query_data["lang"] = lang
            if ukanc_flow:
                query_data["member_category"] = member_category
                query_data["boarding_option"] = boarding_option
            elif laski_flow:
                query_data["laski_group_type"] = laski_group_type
            query = urlencode(
                query_data
            )
            action = f'<p><a class="button" href="/details?{query}">Continue with this unit</a></p>'
            status = '<p class="status available">Available</p>'
        else:
            problems = "".join(f"<li>{html.escape(problem)}</li>" for problem in item["violations"])
            action = f"<ul>{problems}</ul>"
            status = '<p class="status unavailable">Unavailable</p>'
        price_line = f"<p>Price: EUR {unit['price_per_guest_per_night']:.2f} per guest per night</p>"
        if laski_flow:
            price_line = ""
        elif ukanc_flow and selected_boarding_option:
            ukanc_price_lines = "".join(
                f"<p>Price: {html.escape(line)}</p>"
                for line in format_boarding_prices(selected_boarding_option, seasons)
            )
            price_line = (
                f"<p>{html.escape(selected_boarding_option['label'])}</p>"
                f"{ukanc_price_lines}"
            )
        unit_title = f"<h3>{html.escape(display_unit_name(unit['name'], lang))}</h3>" if show_unit_names else ""
        unit_cards.append(
            f"""
            <article class="unit-card">
              {unit_title}
              <p>{html.escape(tf(lang, "capacity_guests", count=unit["max_guests"]))}</p>
              {price_line}
              {status}
              {action}
            </article>
            """
        )

    back_to_search_params = {key: first_param(params, key, "") for key in params.keys()}
    back_to_search_params["location_id"] = str(location_id)
    back_to_search_params["lang"] = lang
    back_to_search_params["check_in"] = check_in
    back_to_search_params["check_out"] = check_out
    back_to_search_params["guest_count"] = guest_count
    back_to_search_params["origin_country"] = origin_country
    back_to_search_params["member_category"] = member_category
    back_to_search_params["preferred_arrival_slot"] = preferred_arrival_slot
    back_to_search_params["preferred_arrival_note"] = preferred_arrival_note
    back_to_search_params["preferred_departure_slot"] = preferred_departure_slot
    back_to_search_params["preferred_departure_note"] = preferred_departure_note
    back_to_search = build_return_to("/", back_to_search_params)
    back_to_search += f"#location-{location_id}"
    content = f"""
    {render_steps("Type", lang)}
    {error_html}
    {pricing_note}
    {selection_panel}
    <section class="panel">
      <div class="location-heading">
        <h2>{html.escape(display_location_name(location['name'], lang))}</h2>
        <p>{html.escape(check_in)} to {html.escape(check_out)} | {html.escape(guest_count)} guests</p>
      </div>
        <div class="unit-grid">
          {''.join(unit_cards)}
        </div>
      </section>
      <section class="panel">
        {render_step_actions(back_to_search, "")}
      </section>
      """
    return render_layout(t(lang, "type"), content, lang=lang, current_path="/type", current_params={key: first_param(params, key, "") for key in params.keys()})


def render_details_page(connection, params, errors=None):
    errors = errors or []
    lang = get_lang(params.get("lang", "en"))
    admin_mode = params.get("admin_mode") == "1"
    unit_id = int(params.get("unit_id", "0") or "0")
    unit = get_unit(connection, unit_id)
    if not unit:
        return render_layout(
            "Group details",
            render_reservation_steps("Group details", lang) + f'<section class="panel error"><p>{html.escape(t(lang, "selected_unit_not_found"))}</p></section>',
            lang=lang,
            current_path="/details",
            current_params=params,
        )

    check_in = params.get("check_in", "")
    check_out = params.get("check_out", "")
    guest_count = params.get("guest_count", "1")
    total_nights = 0
    try:
        total_nights = nights_between(parse_date(check_in), parse_date(check_out))
    except Exception:
        pass
    laski_group_type = params.get("laski_group_type", "")

    adult_total, child_total, section_rows = calculate_section_totals(params)
    if laski_group_type == "non_scouts":
        for row in section_rows:
            row["label"] = NON_SCOUT_SECTION_LABELS.get(row["key"], row["label"])
        section_rows = [row for row in section_rows if row["label"]]
    section_total = adult_total + child_total
    expected_guest_total = to_non_negative_int(guest_count)

    fields = {
        "origin_country": params.get("origin_country", ""),
        "group_name": params.get("group_name", ""),
        "organization_name": params.get("organization_name", ""),
        "group_location": params.get("group_location", ""),
        "vat_number": params.get("vat_number", ""),
        "country": params.get("country", "") or params.get("origin_country", ""),
        "adult_count": str(adult_total),
        "child_count": str(child_total),
        "kitchen_rental": params.get("kitchen_rental", ""),
        "fridge_rental": params.get("fridge_rental", ""),
        "table_set_count": params.get("table_set_count", ""),
        "guest_name": params.get("guest_name", ""),
        "guest_email": params.get("guest_email", ""),
        "guest_phone": params.get("guest_phone", ""),
        "notes": params.get("notes", ""),
        "preferred_arrival_slot": params.get("preferred_arrival_slot", ""),
        "preferred_arrival_note": params.get("preferred_arrival_note", ""),
        "preferred_departure_slot": params.get("preferred_departure_slot", ""),
        "preferred_departure_note": params.get("preferred_departure_note", ""),
        "member_category": params.get("member_category", ""),
        "boarding_option": params.get("boarding_option", ""),
        "laski_group_type": laski_group_type,
    }
    hidden_fields = [
        ("lang", lang),
        ("unit_id", str(unit_id)),
        ("check_in", check_in),
        ("check_out", check_out),
        ("guest_count", guest_count),
        ("origin_country", fields["origin_country"]),
        ("member_category", fields["member_category"]),
        ("boarding_option", fields["boarding_option"]),
        ("laski_group_type", fields["laski_group_type"]),
    ]
    visible_field_names = {
        "lang",
        "unit_id",
        "check_in",
        "check_out",
        "guest_count",
        "origin_country",
        "member_category",
        "boarding_option",
        "laski_group_type",
        "group_name",
        "organization_name",
        "group_location",
        "vat_number",
        "country",
        "adult_count",
        "child_count",
        "preferred_arrival_slot",
        "preferred_arrival_note",
        "preferred_departure_slot",
        "preferred_departure_note",
        "notes",
        "section_total",
    }
    hidden_html = "".join(
        f'<input type="hidden" name="{html.escape(name)}" value="{html.escape(value)}">'
        for name, value in hidden_fields if value != ""
    )
    hidden_html += "".join(
        f'<input type="hidden" name="{html.escape(key)}" value="{html.escape(params.get(key, ""))}">'
        for key in params.keys()
        if key.startswith("rental_")
        or (
            key not in visible_field_names
            and not key.startswith("section_")
            and not key.startswith("contact_person_")
            and not key.startswith("unit_leader_")
            and not key.startswith("international_commissioner_")
        )
    )
    error_html = ""
    if errors:
        items = "".join(f"<li>{html.escape(error)}</li>" for error in errors)
        error_html = f'<section class="panel error"><ul>{items}</ul></section>'
    back_to_type_params = {key: params.get(key, "") for key in params.keys()}
    back_to_type_params.pop("unit_id", None)
    back_to_type_params["location_id"] = str(unit["location_id"])
    back_to_type_params["lang"] = lang
    if admin_mode:
        back_to_type_params["admin_mode"] = "1"
    back_to_type = build_return_to("/type", back_to_type_params)

    content = f"""
    {render_reservation_steps("Group details", lang)}
    {error_html}
    <section class="panel">
      <h2>{html.escape(display_location_name(unit['location_name'], lang))} / {html.escape(unit['unit_name'])}</h2>
      <p>{html.escape(t(lang, "stay"))}: {html.escape(check_in)} to {html.escape(check_out)}</p>
      <p>{html.escape(t(lang, "total_nights"))}: {total_nights}</p>
      <p>{html.escape(t(lang, "guests"))}: {html.escape(guest_count)}</p>
      <p>{html.escape(t(lang, "capacity"))}: {unit['max_guests']} {html.escape(t(lang, "guests_word"))}</p>
    </section>
    <section class="panel">
        <form method="get" action="/rental" class="booking-form">
        {hidden_html}
        <section class="form-section field-span-full">
          <h3>Group details</h3>
          <p>Please add the group structure below and continue with the contact information after that.</p>
        </section>
        <section class="panel booking-extra field-span-full">
          <h3>Sections</h3>
          <p>Please tick all that apply and add the number of people for each selected section.</p>
          <div class="section-grid">
            {''.join(
                f'''
                <label class="section-row">
                  <span class="section-check">
                    <input type="checkbox" name="section_{row["key"]}_selected" class="section-toggle" {"checked" if row["selected"] else ""}>
                    <span>{html.escape(row["label"])}</span>
                  </span>
                  <input type="number" name="section_{row["key"]}_count" class="section-count" min="0" value="{row["count"]}" placeholder="0" data-section-kind="{"adult" if row["key"] in ADULT_SECTION_KEYS else "child"}">
                </label>
                '''
                for row in section_rows
            )}
          </div>
          <div class="section-totals">
            <label>
              Adults
              <input type="number" name="adult_count" class="section-total-adults" min="0" value="{html.escape(fields['adult_count'])}" readonly>
            </label>
            <label>
              Children
              <input type="number" name="child_count" class="section-total-children" min="0" value="{html.escape(fields['child_count'])}" readonly>
            </label>
            <label>
              Total
              <input type="number" name="section_total" class="section-total-all" min="0" value="{section_total}" readonly>
              <small class="section-total-note">Must match guests from previous step: {expected_guest_total}</small>
            </label>
          </div>
        </section>
        <section class="form-section field-span-full">
          <h3>Scout unit details</h3>
          <div class="form-section-grid">
            <label class="field-span-2">
              National scout organization
              <input type="text" name="organization_name" value="{html.escape(fields['organization_name'])}" required>
            </label>
            <label class="field-span-2">
              Local scout unit
              <input type="text" name="group_name" value="{html.escape(fields['group_name'])}" required>
            </label>
            <label class="field-span-2">
              Exact address of the unit
              <small>street, post code, town, country</small>
              <input type="text" name="group_location" value="{html.escape(fields['group_location'])}" required>
            </label>
            <label class="field-span-2">
              VAT number
              <small>If not applicable write /</small>
              <input type="text" name="vat_number" value="{html.escape(fields['vat_number'])}" required>
            </label>
            <label class="field-span-2">
              Country
              {render_country_input(fields['country'])}
            </label>
          </div>
        </section>
        <section class="form-section field-span-full">
          <h3>Other information</h3>
          <div class="form-section-grid">
            <div class="time-preference-grid field-span-full">
              <label>
                {html.escape(t(lang, "arrival_optional"))}
                {render_time_select("preferred_arrival_slot", fields["preferred_arrival_slot"], lang)}
              </label>
              <label>
                {html.escape(t(lang, "arrival_note_optional"))}
                <input type="text" name="preferred_arrival_note" value="{html.escape(fields['preferred_arrival_note'])}">
              </label>
            </div>
            <div class="time-preference-grid field-span-full">
              <label>
                {html.escape(t(lang, "departure_optional"))}
                {render_time_select("preferred_departure_slot", fields["preferred_departure_slot"], lang)}
              </label>
              <label>
                {html.escape(t(lang, "departure_note_optional"))}
                <input type="text" name="preferred_departure_note" value="{html.escape(fields['preferred_departure_note'])}">
              </label>
            </div>
            <label class="field-span-full">
              {html.escape(t(lang, "notes"))}
              <textarea name="notes" rows="4">{html.escape(fields['notes'])}</textarea>
            </label>
          </div>
        </section>
        {render_step_actions_form("/type", '<button type="submit" class="section-submit">Continue to rental</button>')}
      </form>
      </section>
      <script>
      (() => {{
        const form = document.querySelector('.booking-form');
        if (!form) return;
        const toggles = form.querySelectorAll('.section-toggle');
        const counts = form.querySelectorAll('.section-count');
        const adults = form.querySelector('.section-total-adults');
        const children = form.querySelector('.section-total-children');
        const total = form.querySelector('.section-total-all');
        const submit = form.querySelector('.section-submit');
        const expectedTotal = {expected_guest_total};
        const totalNote = form.querySelector('.section-total-note');
        const sync = () => {{
          let adultTotal = 0;
          let childTotal = 0;
          counts.forEach((input) => {{
            const row = input.closest('.section-row');
            const checked = row && row.querySelector('.section-toggle')?.checked;
            const count = Math.max(0, parseInt(input.value || '0', 10) || 0);
            input.disabled = !checked;
            if (!checked) {{
              return;
            }}
            if (input.dataset.sectionKind === 'adult') {{
              adultTotal += count;
            }} else {{
              childTotal += count;
            }}
          }});
          adults.value = String(adultTotal);
          children.value = String(childTotal);
          const combinedTotal = adultTotal + childTotal;
          total.value = String(combinedTotal);
          const matches = combinedTotal === expectedTotal;
          total.classList.toggle('is-invalid', !matches);
          if (submit) {{
            submit.disabled = !matches;
            submit.title = matches ? '' : 'Total must match guest count (' + expectedTotal + ').';
          }}
          if (totalNote) {{
            totalNote.textContent = matches
              ? 'Matches guests from previous step: ' + expectedTotal
              : 'Total must match guests from previous step: ' + expectedTotal;
          }}
        }};
        toggles.forEach((input) => input.addEventListener('change', sync));
        counts.forEach((input) => input.addEventListener('input', sync));
        sync();
      }})();
      </script>
      """
    return render_layout("Group details", content, lang=lang, current_path="/details", current_params=params)


def render_rental_page(connection, params, errors=None):
    errors = errors or []
    lang = get_lang(params.get("lang", "en"))
    admin_mode = params.get("admin_mode") == "1"
    unit_id = int(params.get("unit_id", "0") or "0")
    unit = get_unit(connection, unit_id)
    if not unit:
        return render_layout(
            "Rental",
            render_reservation_steps("Rental", lang) + f'<section class="panel error"><p>{html.escape(t(lang, "selected_unit_not_found"))}</p></section>',
            lang=lang,
            current_path="/rental",
            current_params=params,
        )

    hidden_html = "".join(
        f'<input type="hidden" name="{html.escape(key)}" value="{html.escape(value)}">'
        for key, value in params.items()
        if not key.startswith("rental_")
    )
    error_html = ""
    if errors:
        items = "".join(f"<li>{html.escape(error)}</li>" for error in errors)
        error_html = f'<section class="panel error"><ul>{items}</ul></section>'
    return_to = build_return_to("/rental", {**params, "admin_mode": "1"})
    rental_rows_html = "".join(
        render_rental_item_row(item, params, lang, admin_mode, return_to)
        for item in RENTAL_ITEMS
    )
    back_to_details = build_return_to("/details", {})

    content = f"""
    {render_reservation_steps("Rental", lang)}
    {error_html}
    <section class="panel">
      <h2>{html.escape(display_location_name(unit['location_name'], lang))} / {html.escape(unit['unit_name'])}</h2>
      <p>{html.escape(t(lang, "stay"))}: {html.escape(params.get("check_in", ""))} to {html.escape(params.get("check_out", ""))}</p>
      <p>{html.escape(t(lang, "guests"))}: {html.escape(params.get("guest_count", ""))}</p>
    </section>
      <section class="panel">
        <form method="get" action="/contact" class="booking-form">
        {hidden_html}
        <input type="hidden" name="admin_mode" value="{'1' if admin_mode else ''}">
        <section class="form-section field-span-full">
          <h3>Rental</h3>
            <div class="rental-list">
              {rental_rows_html}
            </div>
            <label class="field-span-full">
              Rental comments
              <small>Use this if you need more than the listed limit or want to add rental details.</small>
              <textarea name="rental_comments" rows="4">{html.escape(params.get("rental_comments", ""))}</textarea>
            </label>
          </section>
        <div class="step-actions field-span-full">
          <button type="submit" class="button button-secondary" formaction="/details">Back</button>
          <button type="submit">Continue to contact details</button>
        </div>
      </form>
    </section>
    <script>
    (() => {{
        const rows = document.querySelectorAll('.rental-row');
      rows.forEach((row) => {{
        const qty = row.querySelector('.rental-qty');
        const yes = row.querySelector('input[type="radio"][value="yes"]');
        const no = row.querySelector('input[type="radio"][value="no"]');
        const zeroOption = qty ? qty.querySelector('.rental-zero-option') : null;
        const extraInputs = row.parentElement.querySelectorAll('.rental-extra-input');
        if (!qty || !yes || !no) return;
        const sync = () => {{
          const enabled = yes.checked;
          qty.disabled = !enabled;
          extraInputs.forEach((input) => {{
            input.disabled = !enabled;
            if (!enabled) {{
              input.value = '';
            }}
          }});
          if (zeroOption) {{
            zeroOption.hidden = enabled;
            zeroOption.disabled = enabled;
          }}
          if (enabled && !qty.value) {{
            qty.value = '1';
          }}
          if (!enabled) {{
            qty.value = '';
          }}
        }};
        yes.addEventListener('change', sync);
        no.addEventListener('change', sync);
        qty.addEventListener('change', sync);
        sync();
      }});
    }})();
    </script>
    """
    return render_layout("Rental", content, lang=lang, current_path="/rental", current_params=params, is_admin=admin_mode)


def render_contact_page(connection, params, errors=None):
    errors = errors or []
    lang = get_lang(params.get("lang", "en"))
    unit_id = int(params.get("unit_id", "0") or "0")
    unit = get_unit(connection, unit_id)
    if not unit:
        return render_layout(
            "Contact details",
            render_reservation_steps("Contact details", lang) + f'<section class="panel error"><p>{html.escape(t(lang, "selected_unit_not_found"))}</p></section>',
            lang=lang,
            current_path="/contact",
            current_params=params,
        )

    hidden_html = "".join(
        f'<input type="hidden" name="{html.escape(key)}" value="{html.escape(value)}">'
        for key, value in params.items()
        if key not in {
            "unit_leader_name",
            "unit_leader_address",
            "unit_leader_email",
            "contact_person_name",
            "contact_person_phone",
            "contact_person_address",
            "contact_person_email",
            "international_commissioner_name",
            "international_commissioner_address",
            "international_commissioner_email",
            "international_commissioner_phone",
        }
    )
    error_html = ""
    if errors:
        items = "".join(f"<li>{html.escape(error)}</li>" for error in errors)
        error_html = f'<section class="panel error"><ul>{items}</ul></section>'
    content = f"""
    {render_reservation_steps("Contact details", lang)}
    {error_html}
    <section class="panel">
      <h2>{html.escape(display_location_name(unit['location_name'], lang))} / {html.escape(unit['unit_name'])}</h2>
      <p>{html.escape(t(lang, "stay"))}: {html.escape(params.get("check_in", ""))} to {html.escape(params.get("check_out", ""))}</p>
      <p>{html.escape(t(lang, "guests"))}: {html.escape(params.get("guest_count", ""))}</p>
    </section>
    <section class="panel">
      <form method="get" action="/book" class="booking-form">
        {hidden_html}
          <section class="form-section field-span-full">
            <h3>Contact details</h3>
            <div class="contact-groups">
              <section class="contact-group">
                <div class="form-section-grid">
                  <label class="field-span-full">
                    Unit leader: name, surname
                    <input type="text" name="unit_leader_name" value="{html.escape(params.get('unit_leader_name', ''))}" required>
                  </label>
                  <label class="field-span-2">
                    Unit leader address
                    <small>street with house number, town, zip code</small>
                    <input type="text" name="unit_leader_address" value="{html.escape(params.get('unit_leader_address', ''))}" required>
                  </label>
                  <label class="field-span-2">
                    Unit leader e-mail
                    <input type="email" name="unit_leader_email" value="{html.escape(params.get('unit_leader_email', ''))}" required>
                  </label>
                  <label class="field-span-2">
                    Reachable telephone number
                    <input type="text" name="unit_leader_phone" value="{html.escape(params.get('unit_leader_phone', ''))}" required>
                  </label>
                </div>
              </section>
              <section class="contact-group">
                <label class="field-span-full checkbox contact-same-toggle">
                  <input type="checkbox" name="contact_same_as_unit_leader" {"checked" if params.get('contact_same_as_unit_leader') == 'on' else ""}>
                  Same as Unit leader
                </label>
                <div class="form-section-grid">
                  <label class="field-span-2">
                    Contact person: name, surname
                    <input type="text" name="contact_person_name" class="contact-person-field" value="{html.escape(params.get('contact_person_name', ''))}" required>
                  </label>
                  <label class="field-span-2">
                    Reachable telephone number
                    <input type="text" name="contact_person_phone" class="contact-person-field" value="{html.escape(params.get('contact_person_phone', ''))}" required>
                  </label>
                  <label class="field-span-2">
                    Contact person address
                    <small>street with house number, town, zip code</small>
                    <input type="text" name="contact_person_address" class="contact-person-field" value="{html.escape(params.get('contact_person_address', ''))}" required>
                  </label>
                  <label class="field-span-2">
                    Contact person e-mail
                    <input type="email" name="contact_person_email" class="contact-person-field" value="{html.escape(params.get('contact_person_email', ''))}" required>
                  </label>
                </div>
              </section>
              <section class="contact-group">
                <div class="form-section-grid">
                  <label class="field-span-full">
                    International commissioner: name, surname
                    <input type="text" name="international_commissioner_name" value="{html.escape(params.get('international_commissioner_name', ''))}">
                  </label>
                  <label class="field-span-2">
                    International commissioner address
                    <input type="text" name="international_commissioner_address" value="{html.escape(params.get('international_commissioner_address', ''))}">
                  </label>
                  <label class="field-span-2">
                    International commissioner e-mail
                    <input type="email" name="international_commissioner_email" value="{html.escape(params.get('international_commissioner_email', ''))}">
                  </label>
                  <label class="field-span-full">
                    International commissioner telephone
                    <input type="text" name="international_commissioner_phone" value="{html.escape(params.get('international_commissioner_phone', ''))}">
                  </label>
                </div>
              </section>
            </div>
          </section>
          {render_step_actions_form("/rental", '<button type="submit">Continue to summary</button>')}
        </form>
      </section>
      <script>
      (() => {{
        const same = document.querySelector('input[name="contact_same_as_unit_leader"]');
        if (!same) return;
        const mappings = [
          ['unit_leader_name', 'contact_person_name'],
          ['unit_leader_address', 'contact_person_address'],
          ['unit_leader_email', 'contact_person_email'],
          ['unit_leader_phone', 'contact_person_phone'],
        ];
        const contactFields = document.querySelectorAll('.contact-person-field');
        const sync = () => {{
          const enabled = same.checked;
          mappings.forEach(([sourceName, targetName]) => {{
            const source = document.querySelector('input[name="' + sourceName + '"]');
            const target = document.querySelector('input[name="' + targetName + '"]');
            if (!source || !target) return;
            if (enabled) {{
              target.value = source.value;
            }}
            target.readOnly = enabled;
          }});
          contactFields.forEach((field) => {{
            field.classList.toggle('is-locked', enabled);
          }});
        }};
        same.addEventListener('change', sync);
        mappings.forEach(([sourceName]) => {{
          const source = document.querySelector('input[name="' + sourceName + '"]');
          if (source) source.addEventListener('input', sync);
        }});
        sync();
      }})();
      </script>
      """
    return render_layout("Contact details", content, lang=lang, current_path="/contact", current_params=params)


def html_response(body, status="200 OK", content_type="text/html; charset=utf-8"):
    encoded = body.encode("utf-8")
    return status, [("Content-Type", content_type), ("Content-Length", str(len(encoded)))], [encoded]


def redirect_response(location):
    return "303 See Other", [("Location", location), ("Content-Length", "0")], [b""]


def redirect_with_cookie(location, cookie_header):
    return "303 See Other", [("Location", location), ("Set-Cookie", cookie_header), ("Content-Length", "0")], [b""]


def read_post_data(environ):
    size = int(environ.get("CONTENT_LENGTH", "0") or "0")
    raw = environ["wsgi.input"].read(size).decode("utf-8")
    parsed = parse_qs(raw, keep_blank_values=True)
    return {key: values[0] for key, values in parsed.items()}


def render_admin_login_page(lang="en", error=""):
    error_html = f'<section class="panel error"><p>{html.escape(error)}</p></section>' if error else ""
    content = f"""
    {error_html}
    <section class="panel">
      <h2>Admin media access</h2>
      <form method="post" action="/admin-login" class="booking-form">
        <input type="hidden" name="lang" value="{lang}">
        <label>
          Username
          <input type="text" name="username" required>
        </label>
        <label>
          Password
          <input type="password" name="password" required>
        </label>
        <button type="submit">Unlock media tools</button>
      </form>
    </section>
    """
    return render_layout("Admin Login", content, lang=lang, current_path="/admin-login", current_params={"lang": lang})


def render_booking_submitted_page(lang="en", email_sent=True):
    content = f"""
    <section class="panel">
      <h2>{html.escape(t(lang, "booking_submitted"))}</h2>
      <p>{html.escape(t(lang, "booking_submitted_text"))}</p>
      <p>{html.escape(t(lang, "booking_email_sent" if email_sent else "booking_email_not_sent"))}</p>
      <p><a class="button" href="/?lang={lang}">{html.escape(t(lang, "search"))}</a></p>
    </section>
    """
    return render_layout(t(lang, "booking_submitted"), content, lang=lang, current_path="/booking-submitted", current_params={"lang": lang})


def render_upload_form(lang, target_type, location_name, unit_name, label, extra_class="", return_to="/"):
    return f"""
    <form method="post" action="/upload-image" enctype="multipart/form-data" class="upload-form {extra_class} drop-upload">
      <input type="hidden" name="lang" value="{lang}">
      <input type="hidden" name="return_to" value="{html.escape(return_to)}">
      <input type="hidden" name="target_type" value="{target_type}">
      <input type="hidden" name="location_name" value="{html.escape(location_name)}">
      <input type="hidden" name="unit_name" value="{html.escape(unit_name)}">
      <label class="drop-zone">
        <span>{html.escape(label)}</span>
        <input type="file" name="image" accept=".jpg,.jpeg,.png,.webp,.svg" required>
      </label>
      <button type="submit">Upload</button>
    </form>
    """


def render_gallery_admin_controls(lang, target_type, location_name, unit_name, image, return_to="/"):
    return f"""
    <div class="gallery-admin">
      <form method="post" action="/delete-image" class="gallery-admin-form">
        <input type="hidden" name="lang" value="{lang}">
        <input type="hidden" name="return_to" value="{html.escape(return_to)}">
        <input type="hidden" name="target_type" value="{target_type}">
        <input type="hidden" name="location_name" value="{html.escape(location_name)}">
        <input type="hidden" name="unit_name" value="{html.escape(unit_name)}">
        <input type="hidden" name="filename" value="{html.escape(image['filename'])}">
        <button type="submit" class="danger-button">Delete photo</button>
      </form>
    </div>
    """


def render_layout(title, content, notice="", lang="en", current_path="/", current_params=None, is_admin=False):
    current_params = dict(current_params or {})
    current_params.pop("lang", None)
    en_query = urlencode({"lang": "en", **current_params})
    sl_query = urlencode({"lang": "sl", **current_params})
    notice_html = f'<div class="notice">{html.escape(notice)}</div>' if notice else ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <header class="site-header">
    <div>
      <p class="eyebrow">{html.escape(t(lang, "prototype"))}</p>
      <h1>{html.escape(title)}</h1>
    </div>
    <div class="header-right">
      <nav class="lang-switch">
        <a href="{current_path}?{en_query}" class="{'active' if lang == 'en' else ''}">{html.escape(t(lang, "language_en"))}</a>
        <a href="{current_path}?{sl_query}" class="{'active' if lang == 'sl' else ''}">{html.escape(t(lang, "language_sl"))}</a>
      </nav>
      <nav>
        <a href="/?lang={lang}">{html.escape(t(lang, "search"))}</a>
        {f'<a href="/admin?lang={lang}">{html.escape(t(lang, "admin"))}</a><form method="post" action="/admin-logout" class="inline-form inline-form--header"><input type="hidden" name="lang" value="{lang}"><button type="submit">Media logout</button></form>' if is_admin else ''}
      </nav>
    </div>
  </header>
  <main>
    {notice_html}
    {content}
  </main>
</body>
</html>
"""


def render_search_page(connection, params, errors=None):
    errors = errors or []
    lang = get_lang(params.get("lang", "en"))
    admin_mode = params.get("admin_mode") == "1"
    notice = params.get("notice", "")
    selected_location_id = first_param(params, "location_id", "")
    selected_check_in = first_param(params, "check_in", "")
    selected_check_out = first_param(params, "check_out", "")
    selected_guest_count = first_param(params, "guest_count", "2")
    selected_origin_country = first_param(params, "origin_country", "")
    selected_member_category = first_param(params, "member_category", "")
    preferred_arrival_slot = params.get("preferred_arrival_slot", "")
    preferred_arrival_note = params.get("preferred_arrival_note", "")
    preferred_departure_slot = params.get("preferred_departure_slot", "")
    preferred_departure_note = params.get("preferred_departure_note", "")
    error_html = "".join(f"<li>{html.escape(error)}</li>" for error in errors)
    intro = f"""
    {render_steps("Period", lang)}
    <section class="panel">
      <p>{html.escape(t(lang, "choose_intro"))}</p>
    </section>
    """
    if error_html:
        intro += f'<section class="panel error"><ul>{error_html}</ul></section>'

    cards = []
    for location in fetch_locations(connection):
        is_selected_location = str(location["id"]) == str(selected_location_id)
        card_check_in = selected_check_in if is_selected_location else ""
        card_check_out = selected_check_out if is_selected_location else ""
        card_guest_count = selected_guest_count if is_selected_location else "2"
        card_origin_country = selected_origin_country if is_selected_location else ""
        card_member_category = selected_member_category if is_selected_location else ""
        card_arrival_slot = preferred_arrival_slot if is_selected_location else ""
        card_arrival_note = preferred_arrival_note if is_selected_location else ""
        card_departure_slot = preferred_departure_slot if is_selected_location else ""
        card_departure_note = preferred_departure_note if is_selected_location else ""
        location_capacity_total = sum(unit["max_guests"] for unit in location["units"])
        reference_year = datetime.now().year
        if card_check_in:
            try:
                reference_year = parse_date(card_check_in).year
            except ValueError:
                pass
        location_min_date, location_max_date = get_location_date_bounds(location["name"], reference_year)
        min_attr = f' min="{location_min_date.isoformat()}"' if location_min_date else ""
        max_attr = f' max="{location_max_date.isoformat()}"' if location_max_date else ""
        gallery_images = get_location_gallery(location["name"])
        lead_image = gallery_images[0]
        if len(gallery_images) > 1:
            gallery_html = f"""
            <details class="location-gallery">
              <summary>
                <img src="{lead_image["url"]}" alt="{html.escape(display_location_name(location['name'], lang))}" class="location-image">
                <span class="gallery-hint">Click to view more photos</span>
              </summary>
              <div class="gallery-grid">
                {''.join(
                    f'''
                    <figure class="gallery-figure">
                      <img src="{image["url"]}" alt="{html.escape(display_location_name(location["name"], lang))}" class="gallery-thumb">
                        {render_gallery_admin_controls(lang, "location", location["name"], "", image, return_to=f"/?lang={lang}&admin_mode=1") if admin_mode and image.get("filename") else ''}
                    </figure>
                    '''
                    for image in gallery_images[1:]
                )}
              </div>
            </details>
            """
        else:
            gallery_html = f"""
            <div class="location-gallery location-gallery--single">
              <img src="{lead_image["url"]}" alt="{html.escape(display_location_name(location['name'], lang))}" class="location-image">
                {render_gallery_admin_controls(lang, "location", location["name"], "", lead_image, return_to=f"/?lang={lang}&admin_mode=1") if admin_mode and lead_image.get("filename") else ''}
            </div>
            """
        if admin_mode:
              gallery_html += render_upload_form(lang, "location", location["name"], "", f"Add picture for {display_location_name(location['name'], lang)}", return_to=f"/?lang={lang}&admin_mode=1")
        unit_summaries = []
        if len(location["units"]) > 1:
            for unit in location["units"]:
                price_line = ""
                if location["name"] not in DYNAMIC_PRICING_LOCATION_NAMES:
                    price_line = f"<p>Price: EUR {unit['price_per_guest_per_night']:.2f} per guest per night</p>"
                unit_gallery_images = get_unit_gallery(location["name"], unit["name"])
                unit_gallery_html = ""
                if unit_gallery_images:
                    lead_image = unit_gallery_images[0]
                    if len(unit_gallery_images) > 1:
                        unit_gallery_html = f"""
                        <details class="location-gallery unit-gallery">
                          <summary>
                            <img src="{lead_image["url"]}" alt="{html.escape(unit['name'])}" class="location-image unit-image">
                            <span class="gallery-hint">Click to view more photos</span>
                          </summary>
                          <div class="gallery-grid">
                            {''.join(
                                f'''
                                <figure class="gallery-figure">
                                  <img src="{image["url"]}" alt="{html.escape(unit["name"])}" class="gallery-thumb">
                                    {render_gallery_admin_controls(lang, "unit", location["name"], unit["name"], image, return_to=f"/?lang={lang}&admin_mode=1") if admin_mode and image.get("filename") else ''}
                                </figure>
                                '''
                                for image in unit_gallery_images[1:]
                            )}
                          </div>
                        </details>
                        """
                    else:
                        unit_gallery_html = f"""
                        <div class="location-gallery unit-gallery location-gallery--single">
                          <img src="{lead_image["url"]}" alt="{html.escape(unit['name'])}" class="location-image unit-image">
                            {render_gallery_admin_controls(lang, "unit", location["name"], unit["name"], lead_image, return_to=f"/?lang={lang}&admin_mode=1") if admin_mode and lead_image.get("filename") else ''}
                        </div>
                        """
                if admin_mode:
                    unit_gallery_html += render_upload_form(lang, "unit", location["name"], unit["name"], f"Add picture for {unit['name']}", extra_class="upload-form--unit", return_to=f"/?lang={lang}&admin_mode=1")
                unit_summaries.append(
                    f"""
                    <article class="unit-card unit-card--summary">
                      <h3>{html.escape(unit['name'])}</h3>
                      {unit_gallery_html}
                  <p>{html.escape(tf(lang, "capacity_guests", count=unit["max_guests"]))}</p>
                      {price_line}
                    </article>
                    """
                )

        preserved_search_hidden = ""
        if is_selected_location:
            preserved_search_hidden = "".join(
                f'<input type="hidden" name="{html.escape(key)}" value="{html.escape(first_param(params, key, ""))}">'
                for key in params.keys()
                if key not in {
                    "location_id",
                    "lang",
                    "check_in",
                    "check_out",
                    "guest_count",
                    "origin_country",
                    "member_category",
                    "preferred_arrival_slot",
                    "preferred_arrival_note",
                    "preferred_departure_slot",
                    "preferred_departure_note",
                }
            )

        cards.append(
            f"""
            <section id="location-{location['id']}" class="panel{' panel--selected' if is_selected_location else ''}">
              <div class="location-heading">
                <h2>{html.escape(display_location_name(location['name'], lang))}</h2>
                <p>{html.escape(translate_location_type(location['type'], lang))}</p>
              </div>
              {gallery_html}
              {'<div class="unit-grid">' + ''.join(unit_summaries) + '</div>' if unit_summaries else ''}
              <form method="get" action="/type" class="search-form location-search-form" data-location-name="{html.escape(location['name'])}" data-date-min="{location_min_date.isoformat() if location_min_date else ''}" data-date-max="{location_max_date.isoformat() if location_max_date else ''}" data-location-capacity="{location_capacity_total}">
                <input type="hidden" name="location_id" value="{location['id']}">
                <input type="hidden" name="lang" value="{lang}">
                {preserved_search_hidden}
                  <label>
                    {html.escape(t(lang, "check_in"))}
                    <div class="checkout-picker checkin-picker">
                    <input type="hidden" name="check_in" class="stay-check-in" value="{html.escape(card_check_in)}" required>
                    <button type="button" class="checkout-trigger checkin-trigger">{html.escape(card_check_in or t(lang, "check_in"))}</button>
                    <div class="checkout-calendar checkin-calendar" hidden>
                      <div class="checkout-calendar-nav">
                        <button type="button" class="calendar-prev checkin-prev" aria-label="Previous month">&lsaquo;</button>
                        <strong class="checkout-calendar-month checkin-calendar-month"></strong>
                        <button type="button" class="calendar-next checkin-next" aria-label="Next month">&rsaquo;</button>
                      </div>
                      <div class="checkout-calendar-weekdays">
                        <span>Mo</span>
                        <span>Tu</span>
                        <span>We</span>
                        <span>Th</span>
                        <span>Fr</span>
                        <span>Sa</span>
                        <span>Su</span>
                      </div>
                      <div class="checkout-calendar-days checkin-calendar-days"></div>
                    </div>
                  </div>
                </label>
                <label>
                  {html.escape(t(lang, "check_out"))}
                  <div class="checkout-picker">
                    <input type="hidden" name="check_out" class="stay-check-out" value="{html.escape(card_check_out)}">
                    <button type="button" class="checkout-trigger" disabled>{html.escape(card_check_out or t(lang, "check_out"))}</button>
                    <div class="checkout-calendar" hidden>
                      <div class="checkout-calendar-nav">
                        <button type="button" class="calendar-prev" aria-label="Previous month">&lsaquo;</button>
                        <strong class="checkout-calendar-month"></strong>
                        <button type="button" class="calendar-next" aria-label="Next month">&rsaquo;</button>
                      </div>
                      <div class="checkout-calendar-weekdays">
                        <span>Mo</span>
                        <span>Tu</span>
                        <span>We</span>
                        <span>Th</span>
                        <span>Fr</span>
                        <span>Sa</span>
                        <span>Su</span>
                      </div>
                      <div class="checkout-calendar-days"></div>
                    </div>
                  </div>
                </label>
                <label>
                  {html.escape(t(lang, "guests"))}
                  <input type="number" name="guest_count" min="1" value="{html.escape(card_guest_count)}" required>
                </label>
                <label>
                  {html.escape(t(lang, "our_group_is_from"))}
                  {render_country_input(card_origin_country, name="origin_country", list_id=f"origin-country-options-{location['id']}")}
                  <span class="member-category-period" hidden>
                    <small>{html.escape(t(lang, "choose_one"))}</small>
                    {render_member_category_select(card_member_category)}
                  </span>
                </label>
                <section class="stay-details">
                  <h3>{html.escape(t(lang, "total_nights"))}</h3>
                  <p class="stay-nights">{html.escape(t(lang, "choose_dates_to_calc"))}</p>
                  <p class="stay-warning" hidden>Minimum stay is 2 full boardings and 20 person. If there is less than 20 person, it is calculated for 20 person.</p>
                  <p class="stay-warning stay-warning-capacity" hidden>This location cannot accept that many guests. Please choose fewer people or another location.</p>
                  <div class="stay-details-extra">
                    <p>{html.escape(t(lang, "date_note"))}</p>
                    <div class="time-preference-grid">
                      <label>
                        {html.escape(t(lang, "arrival_optional"))}
                        {render_time_select("preferred_arrival_slot", card_arrival_slot, lang)}
                      </label>
                      <label>
                        {html.escape(t(lang, "arrival_note_optional"))}
                        <input type="text" name="preferred_arrival_note" value="{html.escape(card_arrival_note)}">
                      </label>
                    </div>
                    <div class="time-preference-grid">
                      <label>
                        {html.escape(t(lang, "departure_optional"))}
                        {render_time_select("preferred_departure_slot", card_departure_slot, lang)}
                      </label>
                      <label>
                        {html.escape(t(lang, "departure_note_optional"))}
                        <input type="text" name="preferred_departure_note" value="{html.escape(card_departure_note)}">
                      </label>
                    </div>
                  </div>
                </section>
                <button type="submit">{html.escape(t(lang, "continue"))}</button>
              </form>
            </section>
            """
        )
    script = """
    <script>
    (() => {
      const forms = document.querySelectorAll('.location-search-form');
      forms.forEach((form) => {
        const checkIn = form.querySelector('.stay-check-in');
        const checkInTrigger = form.querySelector('.checkin-picker .checkout-trigger');
        const checkInCalendar = form.querySelector('.checkin-picker .checkout-calendar');
        const checkInMonth = form.querySelector('.checkin-picker .checkout-calendar-month');
        const checkInDays = form.querySelector('.checkin-picker .checkout-calendar-days');
        const checkInPrev = form.querySelector('.checkin-picker .calendar-prev');
        const checkInNext = form.querySelector('.checkin-picker .calendar-next');
        const checkOut = form.querySelector('.stay-check-out');
        const checkOutTrigger = form.querySelector('.checkout-picker .checkout-trigger');
        const checkOutCalendar = form.querySelector('.checkout-picker .checkout-calendar');
        const checkOutMonth = form.querySelector('.checkout-picker .checkout-calendar-month');
        const checkOutDays = form.querySelector('.checkout-picker .checkout-calendar-days');
        const checkOutPrev = form.querySelector('.checkout-picker .calendar-prev');
        const checkOutNext = form.querySelector('.checkout-picker .calendar-next');
        const guestCountInput = form.querySelector('input[name="guest_count"]');
        const originCountryInput = form.querySelector('input[name="origin_country"]');
        const memberCategoryWrap = form.querySelector('.member-category-period');
        const memberCategorySelect = form.querySelector('.member-category-select');
        const continueButton = form.querySelector('button[type="submit"]');
        const output = form.querySelector('.stay-nights');
        const warning = form.querySelector('.stay-warning');
        const capacityWarning = form.querySelector('.stay-warning-capacity');
        const details = form.querySelector('.stay-details');
        const locationName = form.getAttribute('data-location-name') || '';
        const minDateValue = form.getAttribute('data-date-min') || '';
        const maxDateValue = form.getAttribute('data-date-max') || '';
        const locationCapacity = Number.parseInt(form.getAttribute('data-location-capacity') || '0', 10);
        let visibleCheckInMonthStart = null;
        let visibleMonthStart = null;
        const formatDate = (date) => {
          const year = date.getFullYear();
          const month = String(date.getMonth() + 1).padStart(2, '0');
          const day = String(date.getDate()).padStart(2, '0');
          return year + '-' + month + '-' + day;
        };
        const getMonthStart = (date) => new Date(date.getFullYear(), date.getMonth(), 1);
        const parseIsoDate = (value) => value ? new Date(value + 'T00:00:00') : null;
        const absoluteMinDate = parseIsoDate(minDateValue);
        const absoluteMaxDate = parseIsoDate(maxDateValue);
        const detectSeason = (date) => {
          if ((date.getMonth() === 11 && date.getDate() >= 24) || (date.getMonth() === 0 && date.getDate() <= 2)) {
            return 'holiday';
          }
          if ((date.getMonth() === 5 && date.getDate() >= 24) || date.getMonth() === 6 || date.getMonth() === 7) {
            return 'high';
          }
          return 'low';
        };
        const detectSeasons = (start, end) => {
          const seasons = [];
          const cursor = new Date(start);
          while (cursor < end) {
            const season = detectSeason(cursor);
            if (!seasons.includes(season)) {
              seasons.push(season);
            }
            cursor.setDate(cursor.getDate() + 1);
          }
          return seasons;
        };
        const isSlovenia = (value) => {
          const normalized = String(value || '').trim().toLowerCase();
          return ['slovenia', 'slovenija', 'republic of slovenia', 'republika slovenija'].includes(normalized);
        };
        const syncMemberCategory = () => {
          if (!memberCategoryWrap || !memberCategorySelect || !originCountryInput) {
            return;
          }
          const shouldShow = isSlovenia(originCountryInput.value);
          memberCategoryWrap.hidden = !shouldShow;
          memberCategorySelect.disabled = !shouldShow;
          memberCategorySelect.required = shouldShow;
          if (!shouldShow) {
            memberCategorySelect.value = '';
          }
        };
        const setCheckInLabel = () => {
          if (checkInTrigger) {
            checkInTrigger.textContent = checkIn.value || %CHECKIN_LABEL%;
          }
        };
        const setCheckoutLabel = () => {
          checkOutTrigger.textContent = checkOut.value || %SELECT_CHECKOUT%;
        };
        const closeCheckInCalendar = () => {
          checkInCalendar.hidden = true;
        };
        const closeCheckoutCalendar = () => {
          checkOutCalendar.hidden = true;
        };
        const renderCheckInCalendar = () => {
          const effectiveMinDate = absoluteMinDate ? new Date(absoluteMinDate) : new Date();
          if (!visibleCheckInMonthStart || visibleCheckInMonthStart < getMonthStart(effectiveMinDate)) {
            visibleCheckInMonthStart = getMonthStart(effectiveMinDate);
          }
          const monthStart = getMonthStart(visibleCheckInMonthStart);
          const monthEnd = new Date(monthStart.getFullYear(), monthStart.getMonth() + 1, 0);
          const firstWeekday = (monthStart.getDay() + 6) % 7;
          const dayCells = [];
          for (let i = 0; i < firstWeekday; i += 1) {
            dayCells.push('<span class="calendar-day calendar-day--blank"></span>');
          }
          for (let day = 1; day <= monthEnd.getDate(); day += 1) {
            const current = new Date(monthStart.getFullYear(), monthStart.getMonth(), day);
            const value = formatDate(current);
            const beforeMin = absoluteMinDate && current < absoluteMinDate;
            const afterMax = absoluteMaxDate && current > absoluteMaxDate;
            const selected = value === checkIn.value;
            const classNames = ['calendar-day'];
            if (beforeMin || afterMax) classNames.push('calendar-day--disabled');
            if (selected) classNames.push('calendar-day--selected');
            const disabled = beforeMin || afterMax ? ' disabled' : '';
            dayCells.push('<button type="button" class="' + classNames.join(' ') + '" data-date="' + value + '"' + disabled + '>' + day + '</button>');
          }
          checkInMonth.textContent = new Intl.DateTimeFormat(%LOCALE%, { month: 'long', year: 'numeric' }).format(monthStart);
          checkInPrev.disabled = absoluteMinDate ? monthStart <= getMonthStart(absoluteMinDate) : false;
          checkInNext.disabled = absoluteMaxDate ? monthStart >= getMonthStart(absoluteMaxDate) : false;
          checkInDays.innerHTML = dayCells.join('');
        };
        const renderCheckoutCalendar = () => {
          if (!checkIn.value) {
            checkOut.value = '';
            setCheckoutLabel();
            checkOutTrigger.disabled = true;
            visibleMonthStart = null;
            closeCheckoutCalendar();
            return;
          }
          const start = new Date(checkIn.value + 'T00:00:00');
          if (!Number.isFinite(start.getTime())) {
            checkOut.value = '';
            setCheckoutLabel();
            checkOutTrigger.disabled = true;
            visibleMonthStart = null;
            closeCheckoutCalendar();
            return;
          }
          const minDate = new Date(start);
          minDate.setDate(minDate.getDate() + 1);
          const effectiveMinDate = absoluteMinDate && minDate < absoluteMinDate ? new Date(absoluteMinDate) : minDate;
          if (absoluteMaxDate && start > absoluteMaxDate) {
            checkOut.value = '';
            setCheckoutLabel();
            checkOutTrigger.disabled = true;
            closeCheckoutCalendar();
            return;
          }
          checkOutTrigger.disabled = false;
          if (checkOut.value && (checkOut.value < formatDate(effectiveMinDate) || (maxDateValue && checkOut.value > maxDateValue))) {
            checkOut.value = '';
          }
          if (!visibleMonthStart || visibleMonthStart < getMonthStart(effectiveMinDate)) {
            visibleMonthStart = getMonthStart(effectiveMinDate);
          }
          setCheckoutLabel();
          const monthStart = getMonthStart(visibleMonthStart);
          const monthEnd = new Date(monthStart.getFullYear(), monthStart.getMonth() + 1, 0);
          const firstWeekday = (monthStart.getDay() + 6) % 7;
          const dayCells = [];
          for (let i = 0; i < firstWeekday; i += 1) {
            dayCells.push('<span class="calendar-day calendar-day--blank"></span>');
          }
          for (let day = 1; day <= monthEnd.getDate(); day += 1) {
            const current = new Date(monthStart.getFullYear(), monthStart.getMonth(), day);
            const value = formatDate(current);
            const beforeMin = current < effectiveMinDate;
            const afterMax = absoluteMaxDate && current > absoluteMaxDate;
            const selected = value === checkOut.value;
            const classNames = ['calendar-day'];
            if (beforeMin || afterMax) classNames.push('calendar-day--disabled');
            if (selected) classNames.push('calendar-day--selected');
            const disabled = beforeMin || afterMax ? ' disabled' : '';
            dayCells.push('<button type="button" class="' + classNames.join(' ') + '" data-date="' + value + '"' + disabled + '>' + day + '</button>');
          }
          checkOutMonth.textContent = new Intl.DateTimeFormat(%LOCALE%, { month: 'long', year: 'numeric' }).format(monthStart);
          checkOutPrev.disabled = monthStart <= getMonthStart(effectiveMinDate);
          checkOutNext.disabled = absoluteMaxDate ? monthStart >= getMonthStart(absoluteMaxDate) : false;
          checkOutDays.innerHTML = dayCells.join('');
        };
        const recalc = () => {
          renderCheckoutCalendar();
          const checkInDate = parseIsoDate(checkIn.value);
          const guestCount = Number.parseInt(guestCountInput.value || '0', 10);
          const overCapacity = Number.isFinite(locationCapacity) && locationCapacity > 0 && guestCount > locationCapacity;
          if (capacityWarning) {
            capacityWarning.hidden = !overCapacity;
          }
          if (checkInDate && ((absoluteMinDate && checkInDate < absoluteMinDate) || (absoluteMaxDate && checkInDate > absoluteMaxDate))) {
            output.textContent = 'Selected dates are outside the allowed period for this location.';
            if (warning) {
              warning.hidden = true;
            }
            if (continueButton) {
              continueButton.disabled = true;
            }
            details.classList.remove('is-ready');
            return;
          }
          if (!checkIn.value || !checkOut.value) {
            output.textContent = %CHOOSE_DATES%;
            if (warning) {
              warning.hidden = true;
            }
            if (continueButton) {
              continueButton.disabled = overCapacity;
            }
            details.classList.remove('is-ready');
            return;
          }
          const start = new Date(checkIn.value + 'T00:00:00');
          const end = new Date(checkOut.value + 'T00:00:00');
          const diff = Math.round((end - start) / 86400000);
          if (!Number.isFinite(diff) || diff <= 0) {
            output.textContent = 'Check-out must be after check-in.';
            if (warning) {
              warning.hidden = true;
            }
            if (continueButton) {
              continueButton.disabled = true;
            }
            details.classList.remove('is-ready');
            return;
          }
          if (overCapacity) {
            output.textContent = 'Too many guests for this location.';
            if (warning) {
              warning.hidden = true;
            }
            if (continueButton) {
              continueButton.disabled = true;
            }
            details.classList.remove('is-ready');
            return;
          }
          output.textContent = String(diff);
          if (warning) {
            const seasons = detectSeasons(start, end);
            const isUkanc = locationName === 'Taborni prostor Ukanc' || locationName === 'Gozdna sola Ukanc';
            warning.hidden = !(isUkanc && seasons.includes('low') && guestCount > 0 && guestCount < 20);
          }
          if (continueButton) {
            continueButton.disabled = false;
          }
          details.classList.add('is-ready');
        };
        checkIn.addEventListener('change', () => {
          setCheckInLabel();
          recalc();
        });
        if (checkInTrigger) {
          checkInTrigger.addEventListener('click', () => {
            renderCheckInCalendar();
            checkInCalendar.hidden = !checkInCalendar.hidden;
            closeCheckoutCalendar();
          });
        }
        guestCountInput.addEventListener('input', recalc);
        if (originCountryInput) {
          originCountryInput.addEventListener('input', syncMemberCategory);
          originCountryInput.addEventListener('change', syncMemberCategory);
        }
        if (memberCategorySelect) {
          memberCategorySelect.addEventListener('change', recalc);
        }
        checkOutTrigger.addEventListener('click', () => {
          if (checkOutTrigger.disabled) {
            return;
          }
          renderCheckoutCalendar();
          checkOutCalendar.hidden = !checkOutCalendar.hidden;
          closeCheckInCalendar();
        });
        checkInPrev.addEventListener('click', () => {
          if (!visibleCheckInMonthStart) {
            return;
          }
          visibleCheckInMonthStart = new Date(visibleCheckInMonthStart.getFullYear(), visibleCheckInMonthStart.getMonth() - 1, 1);
          renderCheckInCalendar();
        });
        checkInNext.addEventListener('click', () => {
          if (!visibleCheckInMonthStart) {
            return;
          }
          visibleCheckInMonthStart = new Date(visibleCheckInMonthStart.getFullYear(), visibleCheckInMonthStart.getMonth() + 1, 1);
          renderCheckInCalendar();
        });
        checkInDays.addEventListener('click', (event) => {
          const button = event.target.closest('button[data-date]');
          if (!button || button.disabled) {
            return;
          }
          checkIn.value = button.getAttribute('data-date');
          if (checkOut.value && checkOut.value <= checkIn.value) {
            checkOut.value = '';
          }
          setCheckInLabel();
          closeCheckInCalendar();
          recalc();
        });
        checkOutPrev.addEventListener('click', () => {
          if (!visibleMonthStart) {
            return;
          }
          visibleMonthStart = new Date(visibleMonthStart.getFullYear(), visibleMonthStart.getMonth() - 1, 1);
          renderCheckoutCalendar();
        });
        checkOutNext.addEventListener('click', () => {
          if (!visibleMonthStart) {
            return;
          }
          visibleMonthStart = new Date(visibleMonthStart.getFullYear(), visibleMonthStart.getMonth() + 1, 1);
          renderCheckoutCalendar();
        });
        checkOutDays.addEventListener('click', (event) => {
          const button = event.target.closest('button[data-date]');
          if (!button || button.disabled) {
            return;
          }
          checkOut.value = button.getAttribute('data-date');
          setCheckoutLabel();
          closeCheckoutCalendar();
          recalc();
        });
        document.addEventListener('click', (event) => {
          if (!form.contains(event.target)) {
            closeCheckInCalendar();
            closeCheckoutCalendar();
          }
        });
        syncMemberCategory();
        setCheckInLabel();
        recalc();
      });

        const uploadForms = document.querySelectorAll('.drop-upload');
        uploadForms.forEach((form) => {
          const zone = form.querySelector('.drop-zone');
          const input = form.querySelector('input[type="file"]');
          if (!zone || !input) return;
        ['dragenter', 'dragover'].forEach((eventName) => {
          zone.addEventListener(eventName, (event) => {
            event.preventDefault();
            zone.classList.add('is-dragover');
          });
        });
        ['dragleave', 'drop'].forEach((eventName) => {
          zone.addEventListener(eventName, (event) => {
            event.preventDefault();
            zone.classList.remove('is-dragover');
          });
        });
        zone.addEventListener('drop', (event) => {
            if (event.dataTransfer && event.dataTransfer.files.length) {
              input.files = event.dataTransfer.files;
            }
          });
        });

        const numberInputs = document.querySelectorAll('input[type="number"]');
        numberInputs.forEach((input) => {
          input.setAttribute('inputmode', 'numeric');
          input.setAttribute('step', '1');
          input.addEventListener('keydown', (event) => {
            if (['e', 'E', '+', '-', '.'].includes(event.key)) {
              event.preventDefault();
            }
          });
          input.addEventListener('input', () => {
            const digitsOnly = input.value.replace(/\D+/g, '');
            if (input.value !== digitsOnly) {
              input.value = digitsOnly;
            }
          });
        });

        const countryInputs = document.querySelectorAll('.country-input');
        countryInputs.forEach((input) => {
          const listId = input.getAttribute('list');
          const datalist = listId ? document.getElementById(listId) : null;
          if (!datalist) return;
          const allOptions = Array.from(datalist.querySelectorAll('option')).map((option) => option.value);
          const syncOptions = () => {
            const query = input.value.trim().toLowerCase();
            const filtered = allOptions.filter((country) => country.toLowerCase().includes(query)).slice(0, 50);
            datalist.innerHTML = filtered.map((country) => `<option value="${country}"></option>`).join('');
          };
          input.addEventListener('input', syncOptions);
          input.addEventListener('focus', syncOptions);
          syncOptions();
        });
      })();
      </script>
      """
    script = script.replace("%CHOOSE_DATES%", "'" + t(lang, "choose_dates_to_calc").replace("'", "\\'") + "'")
    script = script.replace("%CHECKIN_LABEL%", "'" + t(lang, "check_in").replace("'", "\\'") + "'")
    script = script.replace("%SELECT_CHECKOUT%", "'" + t(lang, "check_out").replace("'", "\\'") + "'")
    script = script.replace("%LOCALE%", "'" + ("sl-SI" if lang == "sl" else "en-GB") + "'")
    return render_layout(t(lang, "app_title"), intro + "".join(cards) + script, notice=notice, lang=lang, current_path="/", current_params=params, is_admin=admin_mode)


def render_booking_page(connection, params, errors=None):
    errors = errors or []
    lang = get_lang(params.get("lang", "en"))
    unit_id = int(params.get("unit_id", "0"))
    unit = get_unit(connection, unit_id)
    if not unit:
        return render_layout(t(lang, "booking"), f'<section class="panel error"><p>{html.escape(t(lang, "selected_unit_not_found"))}</p></section>', lang=lang, current_path="/book", current_params=params)

    check_in = params.get("check_in", "")
    check_out = params.get("check_out", "")
    guest_count = params.get("guest_count", "1")
    member_category = params.get("member_category", "")
    boarding_option = params.get("boarding_option", "")
    laski_group_type = params.get("laski_group_type", "")
    back_to_contact = build_return_to("/contact", params)

    try:
        summary_data = build_booking_summary_data(connection, unit, params)
        breakdown = summary_data["breakdown"]
        details_data = summary_data["details_data"]
        total_nights = breakdown["total_nights"]
        total_price = breakdown["total_amount"]
        display_price = breakdown["summary_price_text"]
        adult_count = details_data["adult_count"]
        child_count = details_data["child_count"]
        selected_rentals = details_data["selected_rentals"]
        unit_leader_name = details_data["unit_leader_name"]
        unit_leader_address = details_data["unit_leader_address"]
        unit_leader_email = details_data["unit_leader_email"]
        unit_leader_phone = details_data["unit_leader_phone"]
        contact_person_name = details_data["contact_person_name"]
        contact_person_phone = details_data["contact_person_phone"]
        contact_person_address = details_data["contact_person_address"]
        contact_person_email = details_data["contact_person_email"]
        international_commissioner_name = details_data["international_commissioner_name"]
        international_commissioner_address = details_data["international_commissioner_address"]
        international_commissioner_email = details_data["international_commissioner_email"]
        international_commissioner_phone = details_data["international_commissioner_phone"]
        group_name = details_data["group_name"]
        organization_name = details_data["organization_name"]
        group_location = details_data["group_location"]
        vat_number = details_data["vat_number"]
        country = details_data["country"]
        rental_comments = details_data["rental_comments"]
        preferred_arrival_slot = details_data["preferred_arrival_slot"]
        preferred_arrival_note = details_data["preferred_arrival_note"]
        preferred_departure_slot = details_data["preferred_departure_slot"]
        preferred_departure_note = details_data["preferred_departure_note"]
        notes = details_data["notes"]
        contact_same_as_unit_leader = params.get("contact_same_as_unit_leader", "") == "on"
    except Exception:
        breakdown = {"rows": [], "total_amount": Decimal("0.00"), "booking_fee": Decimal("0.00"), "second_payment": Decimal("0.00"), "booking_fee_label": "", "second_payment_label": ""}
        total_nights = 0
        total_price = Decimal("0.00")
        display_price = f"EUR {money(unit['price_per_guest_per_night']):.2f} per guest per night"
        details_data = build_booking_summary_data(connection, unit, params)["details_data"]
        adult_count = details_data["adult_count"]
        child_count = details_data["child_count"]
        selected_rentals = details_data["selected_rentals"]
        unit_leader_name = details_data["unit_leader_name"]
        unit_leader_address = details_data["unit_leader_address"]
        unit_leader_email = details_data["unit_leader_email"]
        unit_leader_phone = details_data["unit_leader_phone"]
        contact_person_name = details_data["contact_person_name"]
        contact_person_phone = details_data["contact_person_phone"]
        contact_person_address = details_data["contact_person_address"]
        contact_person_email = details_data["contact_person_email"]
        international_commissioner_name = details_data["international_commissioner_name"]
        international_commissioner_address = details_data["international_commissioner_address"]
        international_commissioner_email = details_data["international_commissioner_email"]
        international_commissioner_phone = details_data["international_commissioner_phone"]
        group_name = details_data["group_name"]
        organization_name = details_data["organization_name"]
        group_location = details_data["group_location"]
        vat_number = details_data["vat_number"]
        country = details_data["country"]
        rental_comments = details_data["rental_comments"]
        preferred_arrival_slot = details_data["preferred_arrival_slot"]
        preferred_arrival_note = details_data["preferred_arrival_note"]
        preferred_departure_slot = details_data["preferred_departure_slot"]
        preferred_departure_note = details_data["preferred_departure_note"]
        notes = details_data["notes"]
        contact_same_as_unit_leader = params.get("contact_same_as_unit_leader", "") == "on"
    show_ukanc_type_fields = is_ukanc_location(unit["location_name"])

    error_html = "".join(f"<li>{html.escape(error)}</li>" for error in errors)
    content = f"""
    {render_reservation_steps("Summary", lang)}
      <section class="panel">
        <h2>{html.escape(display_location_name(unit['location_name'], lang))} / {html.escape(unit['unit_name'])}</h2>
        <p>{html.escape(t(lang, "stay"))}: {html.escape(check_in)} to {html.escape(check_out)}</p>
        <p>{html.escape(t(lang, "total_nights"))}: {total_nights}</p>
        <p>{html.escape(t(lang, "guests"))}: {html.escape(guest_count)}</p>
        <p>{html.escape(t(lang, "capacity"))}: {unit['max_guests']} {html.escape(t(lang, "guests_word"))}</p>
        <p>{html.escape(t(lang, "price"))}: {display_price}</p>
        <p>{html.escape(t(lang, "estimated_total"))}: EUR {total_price:.2f}</p>
        {f'<p>{html.escape(t(lang, "member_category"))}: {html.escape(member_category)}</p>' if show_ukanc_type_fields and member_category else ''}
        {f'<p>{html.escape(t(lang, "boarding_option"))}: {html.escape(boarding_option)}</p>' if show_ukanc_type_fields and boarding_option else ''}
        {f'<p>{html.escape(t(lang, "laski_group_type"))}: {html.escape(laski_group_type)}</p>' if laski_group_type else ''}
      </section>
    """
    if error_html:
        content += f'<section class="panel error"><ul>{error_html}</ul></section>'
    submitted_group_details_html = build_submitted_group_details_html(details_data, lang)
    content += f"""
    <section class="panel">
      <h2>Submitted group details</h2>
      {submitted_group_details_html}
    </section>
    <section class="panel">
      <h2>Calculation</h2>
      {render_breakdown_table(breakdown)}
    </section>
    <section class="panel">
      <form method="post" action="/book" class="booking-form summary-form">
        <input type="hidden" name="unit_id" value="{unit_id}">
        <input type="hidden" name="lang" value="{lang}">
        <input type="hidden" name="member_category" value="{html.escape(member_category)}">
        <input type="hidden" name="boarding_option" value="{html.escape(boarding_option)}">
        <input type="hidden" name="laski_group_type" value="{html.escape(laski_group_type)}">
        <input type="hidden" name="check_in" value="{html.escape(check_in)}">
        <input type="hidden" name="check_out" value="{html.escape(check_out)}">
        <input type="hidden" name="guest_count" value="{html.escape(guest_count)}">
          <input type="hidden" name="unit_leader_name" value="{html.escape(unit_leader_name)}">
          <input type="hidden" name="unit_leader_address" value="{html.escape(unit_leader_address)}">
          <input type="hidden" name="unit_leader_email" value="{html.escape(unit_leader_email)}">
          <input type="hidden" name="unit_leader_phone" value="{html.escape(unit_leader_phone)}">
          <input type="hidden" name="contact_same_as_unit_leader" value="{'on' if contact_same_as_unit_leader else ''}">
          <input type="hidden" name="contact_person_name" value="{html.escape(contact_person_name)}">
          <input type="hidden" name="contact_person_phone" value="{html.escape(contact_person_phone)}">
          <input type="hidden" name="contact_person_address" value="{html.escape(contact_person_address)}">
          <input type="hidden" name="contact_person_email" value="{html.escape(contact_person_email)}">
          <input type="hidden" name="international_commissioner_name" value="{html.escape(international_commissioner_name)}">
          <input type="hidden" name="international_commissioner_address" value="{html.escape(international_commissioner_address)}">
          <input type="hidden" name="international_commissioner_email" value="{html.escape(international_commissioner_email)}">
          <input type="hidden" name="international_commissioner_phone" value="{html.escape(international_commissioner_phone)}">
          <input type="hidden" name="group_name" value="{html.escape(group_name)}">
          <input type="hidden" name="group_location" value="{html.escape(group_location)}">
          <input type="hidden" name="organization_name" value="{html.escape(organization_name)}">
          <input type="hidden" name="vat_number" value="{html.escape(vat_number)}">
          <input type="hidden" name="country" value="{html.escape(country)}">
        <input type="hidden" name="adult_count" value="{html.escape(adult_count)}">
        <input type="hidden" name="child_count" value="{html.escape(child_count)}">
          {''.join(
              f'<input type="hidden" name="rental_{item["key"]}_enabled" value="{html.escape(params.get("rental_" + item["key"] + "_enabled", ""))}">'
              f'<input type="hidden" name="rental_{item["key"]}" value="{html.escape(params.get("rental_" + item["key"], ""))}">'
              f'<input type="hidden" name="rental_{item["key"]}_length" value="{html.escape(params.get("rental_" + item["key"] + "_length", ""))}">'
              for item in RENTAL_ITEMS
          )}
          <input type="hidden" name="rental_comments" value="{html.escape(rental_comments)}">
        {''.join(
            f'<input type="hidden" name="section_{key}_selected" value="{html.escape(params.get(f"section_{key}_selected", ""))}">'
            f'<input type="hidden" name="section_{key}_count" value="{html.escape(params.get(f"section_{key}_count", ""))}">'
            for key, _ in GROUP_SECTION_OPTIONS
        )}
        <input type="hidden" name="preferred_arrival_slot" value="{html.escape(preferred_arrival_slot)}">
        <input type="hidden" name="preferred_arrival_note" value="{html.escape(preferred_arrival_note)}">
        <input type="hidden" name="preferred_departure_slot" value="{html.escape(preferred_departure_slot)}">
        <input type="hidden" name="preferred_departure_note" value="{html.escape(preferred_departure_note)}">
        <input type="hidden" name="notes" value="{html.escape(notes)}">
        {render_step_actions(back_to_contact, f'<button type="submit">{html.escape(t(lang, "create_booking"))}</button>')}
      </form>
    </section>
    """
    return render_layout(t(lang, "booking"), content, lang=lang, current_path="/book", current_params=params)


def build_booking_email_text(payload):
    summary = payload["summary_data"]
    details = summary["details_data"]
    breakdown = summary["breakdown"]
    detail_blocks = build_submitted_group_details_html(details, "en")
    breakdown_table = render_breakdown_table(breakdown)
    return f"""
<html>
  <body style="font-family: Georgia, 'Times New Roman', serif; color: #203127; background: #f3efe4; margin: 0; padding: 24px;">
    <div style="max-width: 960px; margin: 0 auto;">
      <h1 style="margin: 0 0 16px;">Booking summary</h1>
      <div style="background: #fffaf0; border: 1px solid #d8cfbc; border-radius: 18px; padding: 20px; margin-bottom: 16px;">
        <h2 style="margin-top: 0;">{html.escape(payload['location_name'])} / {html.escape(payload['unit_name'])}</h2>
        <p><strong>Stay:</strong> {payload['check_in'].isoformat()} to {payload['check_out'].isoformat()}</p>
        <p><strong>Guests:</strong> {payload['guest_count']}</p>
        <p><strong>Status:</strong> {html.escape(payload['status'])}</p>
        <p><strong>Total:</strong> EUR {payload['total_price']:.2f}</p>
      </div>
      <div style="background: #fffaf0; border: 1px solid #d8cfbc; border-radius: 18px; padding: 20px; margin-bottom: 16px;">
        <h2 style="margin-top: 0;">Submitted group details</h2>
        {detail_blocks}
      </div>
      <div style="background: #fffaf0; border: 1px solid #d8cfbc; border-radius: 18px; padding: 20px;">
        <h2 style="margin-top: 0;">Calculation</h2>
        {breakdown_table}
      </div>
    </div>
  </body>
</html>
"""


def send_booking_confirmation_email(payload):
    if not email_is_configured() or not payload.get("guest_email"):
        return False, "Email delivery not configured"
    if resend_is_configured():
        return send_booking_confirmation_email_via_resend(payload)
    return send_booking_confirmation_email_via_smtp(payload)


def send_booking_confirmation_email_via_resend(payload):
    from_email = RESEND_FROM_EMAIL or SMTP_FROM_EMAIL
    from_name = RESEND_FROM_NAME or SMTP_FROM_NAME
    body = {
        "from": f"{from_name} <{from_email}>",
        "to": [payload["guest_email"]],
        "subject": f"Booking summary - {payload['location_name']}",
        "text": (
            f"Booking summary\n\nLocation: {payload['location_name']}\nUnit: {payload['unit_name']}\n"
            f"Stay: {payload['check_in'].isoformat()} to {payload['check_out'].isoformat()}\n"
            f"Guests: {payload['guest_count']}\nTotal: EUR {payload['total_price']:.2f}"
        ),
        "html": build_booking_email_text(payload),
    }
    request = Request(
        "https://api.resend.com/emails",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            status_code = getattr(response, "status", response.getcode())
            if 200 <= status_code < 300:
                return True, ""
            response_body = response.read().decode("utf-8", errors="replace")
            print(f"Resend send failed: HTTP {status_code} {response_body}")
            return False, f"HTTP {status_code}"
    except Exception as exc:
        print(f"Resend send failed: {exc}")
        return False, str(exc)


def send_booking_confirmation_email_via_smtp(payload):
    if not smtp_is_configured():
        return False, "SMTP not configured"
    smtp_password = SMTP_PASSWORD.replace(" ", "")
    message = EmailMessage()
    message["Subject"] = f"Booking summary - {payload['location_name']}"
    message["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
    message["To"] = payload["guest_email"]
    message.set_content(
        f"Booking summary\n\nLocation: {payload['location_name']}\nUnit: {payload['unit_name']}\nStay: {payload['check_in'].isoformat()} to {payload['check_out'].isoformat()}\nGuests: {payload['guest_count']}\nTotal: EUR {payload['total_price']:.2f}"
    )
    message.add_alternative(build_booking_email_text(payload), subtype="html")
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
            server.ehlo()
            if SMTP_USE_TLS:
                server.starttls()
                server.ehlo()
            if SMTP_USERNAME:
                server.login(SMTP_USERNAME, smtp_password)
            server.send_message(message)
        return True, ""
    except Exception as exc:
        print(f"SMTP send failed: {exc}")
        return False, str(exc)


def validate_booking_form(connection, form, admin_mode=False):
    errors = []
    unit_id = int(form.get("unit_id", "0") or "0")
    unit = get_unit(connection, unit_id)
    if not unit:
        errors.append("Selected unit does not exist.")
        return None, errors

    try:
        check_in = parse_date(form.get("check_in", ""))
        check_out = parse_date(form.get("check_out", ""))
    except ValueError:
        errors.append("Dates must use the YYYY-MM-DD format.")
        return None, errors

    if check_out <= check_in:
        errors.append("Check-out must be after check-in.")

    try:
        guest_count = int(form.get("guest_count", "0"))
        if guest_count <= 0:
            raise ValueError
    except ValueError:
        errors.append("Guest count must be a positive whole number.")
        guest_count = 0

    unit_leader_name = form.get("unit_leader_name", "").strip()
    unit_leader_address = form.get("unit_leader_address", "").strip()
    unit_leader_email = form.get("unit_leader_email", "").strip()
    unit_leader_phone = form.get("unit_leader_phone", "").strip()
    contact_same_as_unit_leader = form.get("contact_same_as_unit_leader", "") == "on"
    contact_person_name = form.get("contact_person_name", "").strip()
    contact_person_phone = form.get("contact_person_phone", "").strip()
    contact_person_address = form.get("contact_person_address", "").strip()
    contact_person_email = form.get("contact_person_email", "").strip()
    international_commissioner_name = form.get("international_commissioner_name", "").strip()
    international_commissioner_address = form.get("international_commissioner_address", "").strip()
    international_commissioner_email = form.get("international_commissioner_email", "").strip()
    international_commissioner_phone = form.get("international_commissioner_phone", "").strip()
    if contact_same_as_unit_leader:
        contact_person_name = unit_leader_name
        contact_person_address = unit_leader_address
        contact_person_email = unit_leader_email
        contact_person_phone = unit_leader_phone
    guest_name = contact_person_name
    guest_email = contact_person_email
    guest_phone = contact_person_phone
    if admin_mode:
        guest_name = form.get("guest_name", "").strip() or guest_name
        guest_email = form.get("guest_email", "").strip() or guest_email
        guest_phone = form.get("guest_phone", "").strip() or guest_phone
    if not guest_name:
        errors.append("Contact person name is required.")
    if not guest_email:
        errors.append("Contact person email is required.")

    member_category = form.get("member_category", "").strip()
    boarding_option = form.get("boarding_option", "").strip()
    member_category = form.get("member_category", "").strip()
    if is_ukanc_location(unit["location_name"]) and boarding_option and not is_boarding_option_allowed(boarding_option, check_in, check_out):
        errors.append("Section B. Overnight in tent - outside kitchen, electricity is available only for stays fully inside high season.")
    laski_group_type = form.get("laski_group_type", "").strip()
    notes = form.get("notes", "").strip()
    preferred_arrival_slot = form.get("preferred_arrival_slot", "").strip()
    preferred_arrival_note = form.get("preferred_arrival_note", "").strip()
    preferred_departure_slot = form.get("preferred_departure_slot", "").strip()
    preferred_departure_note = form.get("preferred_departure_note", "").strip()
    group_name = form.get("group_name", "").strip()
    group_location = form.get("group_location", "").strip()
    organization_name = form.get("organization_name", "").strip()
    vat_number = form.get("vat_number", "").strip()
    country = form.get("country", "").strip()
    rental_comments = form.get("rental_comments", "").strip()
    adult_total, child_total, section_rows = calculate_section_totals(form)
    adult_count = str(adult_total) if adult_total else ""
    child_count = str(child_total) if child_total else ""
    selected_rentals = parse_rental_quantities(form)
    metadata_lines = []
    if member_category:
        metadata_lines.append(f"Member category: {member_category}")
    if boarding_option:
        metadata_lines.append(f"Boarding option: {boarding_option}")
    if laski_group_type:
        metadata_lines.append(f"Laski group type: {laski_group_type}")
    if preferred_arrival_slot:
        metadata_lines.append(f"Preferred arrival time: {preferred_arrival_slot}")
    if preferred_arrival_note:
        metadata_lines.append(f"Arrival note: {preferred_arrival_note}")
    if preferred_departure_slot:
        metadata_lines.append(f"Preferred departure time: {preferred_departure_slot}")
    if preferred_departure_note:
        metadata_lines.append(f"Departure note: {preferred_departure_note}")
    if unit_leader_name:
        metadata_lines.append(f"Unit leader: {unit_leader_name}")
    if unit_leader_address:
        metadata_lines.append(f"Unit leader address: {unit_leader_address}")
    if unit_leader_email:
        metadata_lines.append(f"Unit leader email: {unit_leader_email}")
    if unit_leader_phone:
        metadata_lines.append(f"Unit leader phone: {unit_leader_phone}")
    if contact_person_name:
        metadata_lines.append(f"Contact person: {contact_person_name}")
    if contact_person_phone:
        metadata_lines.append(f"Contact person phone: {contact_person_phone}")
    if contact_person_address:
        metadata_lines.append(f"Contact person address: {contact_person_address}")
    if contact_person_email:
        metadata_lines.append(f"Contact person email: {contact_person_email}")
    if international_commissioner_name:
        metadata_lines.append(f"International commissioner: {international_commissioner_name}")
    if international_commissioner_address:
        metadata_lines.append(f"International commissioner address: {international_commissioner_address}")
    if international_commissioner_email:
        metadata_lines.append(f"International commissioner email: {international_commissioner_email}")
    if international_commissioner_phone:
        metadata_lines.append(f"International commissioner phone: {international_commissioner_phone}")
    if group_name:
        metadata_lines.append(f"Group name: {group_name}")
    if group_location:
        metadata_lines.append(f"Location: {group_location}")
    if organization_name:
        metadata_lines.append(f"Organization: {organization_name}")
    if vat_number:
        metadata_lines.append(f"VAT number: {vat_number}")
    if country:
        metadata_lines.append(f"Country: {country}")
    if adult_count:
        metadata_lines.append(f"Adults: {adult_count}")
    if child_count:
        metadata_lines.append(f"Children: {child_count}")
    if selected_rentals:
        metadata_lines.append(
            "Rentals: " + ", ".join(
                f"{entry['item']['label']} x{entry['quantity']}" + (f" ({entry['length']})" if entry['length'] else "")
                for entry in selected_rentals
            )
        )
    if rental_comments:
        metadata_lines.append(f"Rental comments: {rental_comments}")
    section_details = []
    for row in section_rows:
        if row["selected"]:
            section_details.append(f'{row["label"]}: {row["count"]}')
    if section_details:
        metadata_lines.append("Sections: " + ", ".join(section_details))
    if metadata_lines:
        notes = " | ".join(metadata_lines + ([notes] if notes else []))

    overbook_allowed = form.get("overbook_allowed") == "on"
    if not errors and not overbook_allowed:
        _, violations = capacity_check(connection, unit_id, check_in, check_out, guest_count)
        errors.extend(violations)

    selected_rentals = parse_rental_quantities(form)
    breakdown = build_summary_breakdown(
        connection,
        unit,
        check_in,
        check_out,
        guest_count,
        member_category,
        boarding_option,
        form.get("laski_group_type", "").strip(),
        selected_rentals,
    )
    total_price = breakdown["total_amount"]

    payload = {
        "unit_id": unit_id,
        "location_name": unit["location_name"],
        "unit_name": unit["unit_name"],
        "check_in": check_in,
        "check_out": check_out,
        "guest_count": guest_count,
        "guest_name": guest_name,
        "guest_email": guest_email,
        "guest_phone": form.get("guest_phone", "").strip(),
        "notes": notes,
        "created_by_admin": 1 if admin_mode else 0,
        "overbook_allowed": 1 if overbook_allowed else 0,
        "status": form.get("status", "pending").strip() or "pending",
        "total_price": total_price,
        "summary_data": build_booking_summary_data(connection, unit, form),
    }
    return payload, errors


def insert_booking(connection, payload):
    connection.execute("begin immediate")
    if not payload["overbook_allowed"]:
        _, violations = capacity_check(
            connection,
            payload["unit_id"],
            payload["check_in"],
            payload["check_out"],
            payload["guest_count"],
        )
        if violations:
            connection.rollback()
            return violations

    connection.execute(
        """
        insert into bookings (
            bookable_unit_id, guest_name, guest_email, guest_phone, check_in, check_out,
            guest_count, status, total_price, created_by_admin, overbook_allowed, notes, updated_at
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, current_timestamp)
        """,
        (
            payload["unit_id"],
            payload["guest_name"],
            payload["guest_email"],
            payload["guest_phone"],
            payload["check_in"].isoformat(),
            payload["check_out"].isoformat(),
            payload["guest_count"],
            payload["status"],
            f"{payload['total_price']:.2f}",
            payload["created_by_admin"],
            payload["overbook_allowed"],
            payload["notes"],
        ),
    )
    connection.commit()
    return []


def render_admin_page(connection, notice=""):
    bookings = fetch_bookings(connection)
    locations = fetch_locations(connection)
    booking_board_html = render_admin_booking_board(connection, locations, bookings)
    booking_rows = []
    for booking in bookings:
        booking_rows.append(
            f"""
            <tr>
              <td id="booking-{booking['id']}">{booking['id']}</td>
              <td>{html.escape(booking['location_name'])} / {html.escape(booking['unit_name'])}</td>
              <td>{html.escape(booking['guest_name'])}<br><span class="muted">{html.escape(booking['guest_email'])}</span></td>
              <td>{booking['check_in']} to {booking['check_out']}</td>
              <td>{booking['guest_count']}</td>
              <td>{html.escape(booking['status'])}</td>
              <td>EUR {Decimal(str(booking['total_price'])):.2f}</td>
              <td>{'Yes' if booking['overbook_allowed'] else 'No'}</td>
              <td>
                <form method="post" action="/admin/status" class="inline-form">
                  <input type="hidden" name="booking_id" value="{booking['id']}">
                  <select name="status">
                    {render_status_options(booking['status'])}
                  </select>
                  <button type="submit">Update</button>
                </form>
              </td>
            </tr>
            """
        )

    unit_options = []
    for location in locations:
        for unit in location["units"]:
            label = f"{location['name']} / {unit['name']} ({unit['max_guests']} guests, EUR {unit['price_per_guest_per_night']:.2f})"
            unit_options.append(f'<option value="{unit["id"]}">{html.escape(label)}</option>')

    content = f"""
    <section class="panel">
      <h2>Manual booking</h2>
      <form method="post" action="/admin/manual" class="booking-form">
        <label>
          Unit
          <select name="unit_id">{''.join(unit_options)}</select>
        </label>
        <label>
          Check-in
          <input type="date" name="check_in" required>
        </label>
        <label>
          Check-out
          <input type="date" name="check_out" required>
        </label>
        <label>
          Guests
          <input type="number" name="guest_count" min="1" value="2" required>
        </label>
        <label>
          Full name
          <input type="text" name="guest_name" required>
        </label>
        <label>
          Email
          <input type="email" name="guest_email" required>
        </label>
        <label>
          Phone
          <input type="text" name="guest_phone">
        </label>
        <label>
          Status
          <select name="status">
            <option value="pending">pending</option>
            <option value="confirmed">confirmed</option>
          </select>
        </label>
        <label class="checkbox">
          <input type="checkbox" name="overbook_allowed">
          Allow overbooking
        </label>
        <label>
          Notes
          <textarea name="notes" rows="3"></textarea>
        </label>
        <button type="submit">Create admin booking</button>
      </form>
    </section>
    <section class="panel">
      <h2>Reservation board</h2>
      <p>Visual overview grouped by location and unit across the current year and the next two years.</p>
    </section>
    {booking_board_html}
    <section class="panel">
      <h2>Bookings</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Unit</th>
              <th>Guest</th>
              <th>Stay</th>
              <th>Guests</th>
              <th>Status</th>
              <th>Total</th>
              <th>Overbook</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {''.join(booking_rows) or '<tr><td colspan="9">No bookings yet.</td></tr>'}
          </tbody>
        </table>
      </div>
    </section>
    <script>
    (() => {{
      const boards = document.querySelectorAll('.booking-board-scroll');
      boards.forEach((board) => {{
        const offset = Number.parseInt(board.getAttribute('data-today-offset') || '0', 10);
        const rangeDays = Number.parseInt(board.getAttribute('data-range-days') || '1', 10);
        if (!Number.isFinite(offset) || !Number.isFinite(rangeDays) || rangeDays <= 0) {{
          return;
        }}
        const maxScroll = Math.max(0, board.scrollWidth - board.clientWidth);
        const target = Math.max(0, Math.min(maxScroll, (offset / rangeDays) * board.scrollWidth - (board.clientWidth * 0.35)));
        board.scrollLeft = target;
      }});
    }})();
    </script>
    """
    return render_layout("Admin", content, notice=notice)


def render_status_options(selected):
    statuses = ["pending", "confirmed", "cancelled", "rejected", "expired"]
    options = []
    for status in statuses:
        selected_attr = " selected" if status == selected else ""
        options.append(f'<option value="{status}"{selected_attr}>{status}</option>')
    return "".join(options)


def serve_static(environ):
    path = environ.get("PATH_INFO", "")
    file_name = path.removeprefix("/static/")
    target = STATIC_DIR / file_name
    if not target.is_file():
        return html_response("Not found", status="404 Not Found", content_type="text/plain; charset=utf-8")

    suffix = target.suffix.lower()
    content_type = {
        ".css": "text/css; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".svg": "image/svg+xml",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(suffix, "application/octet-stream")
    data = target.read_bytes()
    return "200 OK", [("Content-Type", content_type), ("Content-Length", str(len(data)))], [data]


def application(environ, start_response):
    path = environ.get("PATH_INFO", "/")
    method = environ.get("REQUEST_METHOD", "GET").upper()

    try:
        if path.startswith("/static/"):
            status, headers, body = serve_static(environ)
        elif path == "/" and method == "GET":
            params = {key: values[0] for key, values in parse_qs(environ.get("QUERY_STRING", "")).items()}
            params["admin_mode"] = "1" if is_admin_request(environ) else ""
            with closing(get_connection()) as connection:
                status, headers, body = html_response(render_search_page(connection, params, []))
        elif path == "/admin-login" and method == "GET":
            lang = get_lang(parse_qs(environ.get("QUERY_STRING", "")).get("lang", ["en"])[0])
            if is_admin_request(environ):
                status, headers, body = redirect_with_cookie(f"/?lang={lang}&notice={quote_plus('Media tools unlocked')}", "campsite_admin=1; Path=/")
            else:
                status, headers, body = html_response(render_admin_login_page(lang))
        elif path == "/admin-login" and method == "POST":
            form = read_post_data(environ)
            lang = get_lang(form.get("lang", "en"))
            if form.get("username", "") == ADMIN_USERNAME and form.get("password", "") == ADMIN_PASSWORD:
                status, headers, body = redirect_with_cookie(f"/?lang={lang}&notice={quote_plus('Media tools unlocked')}", "campsite_admin=1; Path=/")
            else:
                status, headers, body = html_response(render_admin_login_page(lang, error="Invalid username or password."))
        elif path == "/admin-logout" and method == "POST":
            lang = get_lang(read_post_data(environ).get("lang", "en"))
            status, headers, body = redirect_with_cookie(f"/?lang={lang}&notice={quote_plus('Media tools locked')}", "campsite_admin=; Path=/; Max-Age=0")
        elif path == "/type" and method == "GET":
            query_params = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
            params = {key: values[0] for key, values in query_params.items()}
            errors = []
            requested_check_in = None
            requested_check_out = None
            if params.get("check_in") and params.get("check_out"):
                try:
                    requested_check_in = parse_date(params["check_in"])
                    requested_check_out = parse_date(params["check_out"])
                    if requested_check_out <= requested_check_in:
                        errors.append("Check-out must be after check-in.")
                except ValueError:
                    errors.append("Dates must use the YYYY-MM-DD format.")
            else:
                errors.append("Check-in and check-out are required.")
            if params.get("guest_count"):
                try:
                    if int(params["guest_count"]) <= 0:
                        errors.append("Guest count must be positive.")
                except ValueError:
                    errors.append("Guest count must be a whole number.")
            else:
                errors.append("Guest count is required.")
            with closing(get_connection()) as connection:
                location_id = int(params.get("location_id", "0") or "0")
                if location_id:
                    locations = {location["id"]: location for location in fetch_locations(connection)}
                    location = locations.get(location_id)
                    if location and requested_check_in and requested_check_out:
                        if not is_location_date_range_allowed(location["name"], requested_check_in, requested_check_out):
                            errors.append("Selected dates are outside the allowed period for this location.")
                    if location and params.get("guest_count"):
                        try:
                            location_capacity_total = sum(unit["max_guests"] for unit in location["units"])
                            if int(params["guest_count"]) > location_capacity_total:
                                errors.append("This location cannot accept that many guests.")
                        except ValueError:
                            pass
                    if location and params.get("origin_country") and is_slovenia_country(params["origin_country"]) and not params.get("member_category"):
                        errors.append("Choose one is required for groups from Slovenia.")
                if errors:
                    status, headers, body = html_response(render_search_page(connection, params, errors))
                else:
                    status, headers, body = html_response(render_type_page(connection, query_params, errors))
        elif path == "/details" and method == "GET":
            query_params = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
            params = {key: values[0] for key, values in query_params.items()}
            with closing(get_connection()) as connection:
                status, headers, body = html_response(render_details_page(connection, params))
        elif path == "/rental" and method == "GET":
            query_params = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
            params = {key: values[0] for key, values in query_params.items()}
            with closing(get_connection()) as connection:
                errors = validate_group_details_params(params)
                if errors:
                    status, headers, body = html_response(render_details_page(connection, params, errors))
                else:
                    status, headers, body = html_response(render_rental_page(connection, params))
        elif path == "/contact" and method == "GET":
            query_params = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
            params = {key: values[0] for key, values in query_params.items()}
            with closing(get_connection()) as connection:
                group_errors = validate_group_details_params(params)
                if group_errors:
                    status, headers, body = html_response(render_details_page(connection, params, group_errors))
                else:
                    status, headers, body = html_response(render_contact_page(connection, params))
        elif path == "/upload-image" and method == "POST":
            lang, notice, return_to = save_uploaded_image(environ)
            safe_notice = quote_plus(notice)
            separator = "&" if "?" in return_to else "?"
            status, headers, body = redirect_response(f"{return_to}{separator}lang={lang}&notice={safe_notice}")
        elif path == "/delete-image" and method == "POST":
            lang, notice, return_to = delete_gallery_image(environ)
            separator = "&" if "?" in return_to else "?"
            status, headers, body = redirect_response(f"{return_to}{separator}lang={lang}&notice={quote_plus(notice)}")
        elif path == "/book" and method == "GET":
            query_params = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
            params = {key: values[0] for key, values in query_params.items()}
            if "accommodation_type" in query_params:
                params["accommodation_type"] = query_params["accommodation_type"]
            with closing(get_connection()) as connection:
                group_errors = validate_group_details_params(params)
                contact_errors = validate_contact_details_params(params)
                if group_errors:
                    status, headers, body = html_response(render_details_page(connection, params, group_errors))
                elif contact_errors:
                    status, headers, body = html_response(render_contact_page(connection, params, contact_errors))
                else:
                    status, headers, body = html_response(render_booking_page(connection, params))
        elif path == "/book" and method == "POST":
            with closing(get_connection()) as connection:
                form = read_post_data(environ)
                payload, errors = validate_booking_form(connection, form)
                if errors:
                    display_form = {key: value for key, value in form.items()}
                    status, headers, body = html_response(render_booking_page(connection, display_form, errors))
                else:
                    insert_errors = insert_booking(connection, payload)
                    if insert_errors:
                        display_form = {key: value for key, value in form.items()}
                        status, headers, body = html_response(render_booking_page(connection, display_form, insert_errors))
                    else:
                        email_sent, _ = send_booking_confirmation_email(payload)
                        safe_lang = quote_plus(get_lang(form.get("lang", "en")))
                        safe_email_sent = "1" if email_sent else "0"
                        status, headers, body = redirect_response(f"/booking-submitted?lang={safe_lang}&email_sent={safe_email_sent}")
        elif path == "/booking-submitted" and method == "GET":
            params = {key: values[0] for key, values in parse_qs(environ.get("QUERY_STRING", "")).items()}
            lang = get_lang(params.get("lang", "en"))
            email_sent = params.get("email_sent", "0") == "1"
            status, headers, body = html_response(render_booking_submitted_page(lang, email_sent=email_sent))
        elif path == "/admin" and method == "GET":
            params = {key: values[0] for key, values in parse_qs(environ.get("QUERY_STRING", "")).items()}
            if not is_admin_request(environ):
                lang = get_lang(params.get("lang", "en"))
                status, headers, body = redirect_response(f"/admin-login?lang={lang}")
            else:
                with closing(get_connection()) as connection:
                    status, headers, body = html_response(render_admin_page(connection, notice=params.get("notice", "")))
        elif path == "/admin/status" and method == "POST":
            if not is_admin_request(environ):
                status, headers, body = redirect_response("/admin-login?lang=en")
            else:
                with closing(get_connection()) as connection:
                    form = read_post_data(environ)
                    connection.execute(
                        "update bookings set status = ?, updated_at = current_timestamp where id = ?",
                        (form.get("status", "pending"), int(form.get("booking_id", "0"))),
                    )
                    connection.commit()
                    status, headers, body = redirect_response("/admin?notice=Booking+status+updated")
        elif path == "/admin/manual" and method == "POST":
            if not is_admin_request(environ):
                status, headers, body = redirect_response("/admin-login?lang=en")
            else:
                with closing(get_connection()) as connection:
                    form = read_post_data(environ)
                    payload, errors = validate_booking_form(connection, form, admin_mode=True)
                    if errors:
                        status, headers, body = html_response(render_admin_page(connection, notice="; ".join(errors)))
                    else:
                        insert_errors = insert_booking(connection, payload)
                        notice = "Admin booking created" if not insert_errors else "; ".join(insert_errors)
                        safe_notice = quote_plus(notice)
                        status, headers, body = redirect_response(f"/admin?notice={safe_notice}")
        else:
            status, headers, body = html_response("Not found", status="404 Not Found", content_type="text/plain; charset=utf-8")
    except Exception as exc:
        status, headers, body = html_response(
            render_layout(
                "Application Error",
                f'<section class="panel error"><p>{html.escape(str(exc))}</p></section>',
            ),
            status="500 Internal Server Error",
        )

    start_response(status, headers)
    return body


def main():
    init_db()
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    with make_server(host, port, application) as server:
        if host == "0.0.0.0":
            print(f"Serving campsite booking app on http://localhost:{port}")
        else:
            print(f"Serving campsite booking app on http://{host}:{port}")
        server.serve_forever()


if __name__ == "__main__":
    main()

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
from urllib.parse import parse_qs, parse_qsl, quote_plus, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from wsgiref.simple_server import make_server


APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "booking.db"
STATIC_DIR = APP_DIR / "static"
DATA_DIR = APP_DIR / "data"
STYLE_CSS_PATH = STATIC_DIR / "style.css"
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
LOCATION_CONTENT = {
    "Laski rovt ZTS": {
        "en": {
            "summary": "A large summer campsite in Bohinj with three subcamps for scout groups that want flexible layouts and fast access to the lake area.",
            "highlights": ["Up to 125 guests together across 3 subcamps. If your group has that many guests, you must reserve each subcamp separately to reach the desired number of reservations.", "Summer season location", "Best for larger group camps"],
            "season": "Open from 15 May to 15 September",
        },
        "sl": {
            "summary": "Velik poletni taborni prostor v Bohinju s tremi podtabori za skupine, ki potrebujejo prilagodljivo razporeditev in hiter dostop do jezerskega območja.",
            "highlights": ["Do 125 gostov skupaj v 3 podtaborih. V kolikor vas je toliko, morate rezervirati vsak podtabor posebej, da dosežete željeno število rezervacij.", "Lokacija za poletno sezono", "Primerno za večje tabore"],
            "season": "Odprto od 15. maja do 15. septembra",
        },
    },
    "Laski rovt ZR": {
        "en": {
            "summary": "A smaller Laški rovt option for compact groups that want the same Bohinj setting with a simpler booking choice.",
            "highlights": ["Up to 35 guests", "Single booking unit", "Good for smaller camp groups"],
            "season": "Open from 15 May to 15 September",
        },
        "sl": {
            "summary": "Manjša možnost na Laškem rovtu za kompaktne skupine, ki želijo isto bohinjsko okolje z enostavnejšo izbiro rezervacije.",
            "highlights": ["Do 35 gostov", "Ena rezervacijska enota", "Primerno za manjše skupine"],
            "season": "Odprto od 15. maja do 15. septembra",
        },
    },
    "Laski rovt MB": {
        "en": {
            "summary": "An open meadow campsite with strong capacity for larger outdoor stays and traditional scout-style camping.",
            "highlights": ["Up to 100 guests", "Single large campsite", "Built for full-group stays"],
            "season": "Open from 15 May to 15 September",
        },
        "sl": {
            "summary": "Odprt travniški taborni prostor z veliko kapaciteto za večje skupine in klasično taborniško bivanje.",
            "highlights": ["Do 100 gostov", "En velik taborni prostor", "Primerno za celotne skupine"],
            "season": "Odprto od 15. maja do 15. septembra",
        },
    },
    "Taborni prostor Ukanc": {
        "en": {
            "summary": "A flagship Bohinj campsite near Lake Bohinj with flexible accommodation and seasonal boarding options for larger groups.",
            "highlights": ["Up to 120 guests", "Near Lake Bohinj", "Boarding options available"],
            "season": "Open from 15 May to 15 September. Availability depends on season and boarding type",
        },
        "sl": {
            "summary": "Osrednji taborni prostor v Bohinju ob Bohinjskem jezeru s prilagodljivo namestitvijo in sezonskimi možnostmi oskrbe za večje skupine.",
            "highlights": ["Do 120 gostov", "Blizu Bohinjskega jezera", "Na voljo so možnosti oskrbe"],
            "season": "Odprto od 15. maja do 15. septembra. Razpolo?ljivost je odvisna od sezone in vrste oskrbe",
        },
    },
    "Gozdna sola Ukanc": {
        "en": {
            "summary": "An indoor forest school stay for groups that need beds, shared interior spaces, and Bohinj access in one place.",
            "highlights": ["Up to 38 beds", "House accommodation", "Indoor dining and shared rooms"],
            "season": "Open all year. Availability depends on season and boarding type. Minimum 20 person out of main season (low season is from 15.9.-15.5.).",
        },
        "sl": {
            "summary": "Notranja namestitev Gozdne šole za skupine, ki potrebujejo postelje, skupne notranje prostore in dostop do Bohinja na eni lokaciji.",
            "highlights": ["Do 38 postelj", "Hišna namestitev", "Jedilnica in skupni prostori"],
            "season": "Odprto vse leto",
        },
    },
    "Taborni prostor Baredi": {
        "en": {
            "summary": "A coastal-region campsite option for scout groups looking for an outdoor base away from Bohinj.",
            "highlights": ["Up to 50 guests", "Single campsite", "Good for regional group stays"],
            "season": "Open based on local availability",
        },
        "sl": {
            "summary": "Taborni prostor na Primorskem za skupine, ki iščejo zunanjo bazo izven Bohinja.",
            "highlights": ["Do 50 gostov", "En taborni prostor", "Primerno za regionalna bivanja"],
            "season": "Odprto glede na lokalno razpoložljivost",
        },
    },
    "Taborni prostor Radlje ob Dravi": {
        "en": {
            "summary": "A spacious campsite for larger outdoor groups in the Radlje ob Dravi area with a simple booking setup.",
            "highlights": ["Up to 120 guests", "Single campsite", "Simple setup for large groups"],
            "season": "Open based on local availability",
        },
        "sl": {
            "summary": "Prostoren taborni prostor za večje skupine na območju Radelj ob Dravi z enostavno rezervacijsko postavitvijo.",
            "highlights": ["Do 120 gostov", "En taborni prostor", "Enostavna postavitev za večje skupine"],
            "season": "Odprto glede na lokalno razpoložljivost",
        },
    },
}
TEXTS = {
    "en": {
        "search": "Search",
        "admin": "Admin",
        "prototype": "Local Prototype",
        "information": "Information",
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
        "estimated_total_warning": "Warning: this is not the final calculation. The final confirmed calculation will be sent by email after confirmation and contract preparation.",
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
        "group_details_intro": "Please add the group structure below and continue with the contact information after that.",
        "sections_heading": "Sections",
        "sections_intro": "Add the number of people in each age category. These counts are also used for tourist tax.",
        "scout_unit_details": "Scout unit details",
        "taborniki_unit_details": "Scout unit details",
        "national_scout_organization": "National scout organization",
        "local_scout_unit": "Local scout unit",
        "local_taborniki_unit": "Local scout unit",
        "group_name_label": "Registered name of the group",
        "street_label": "Street",
        "house_number_label": "House number",
        "post_code_label": "Post code",
        "town_label": "Town",
        "country_label": "Country",
        "vat_number_label": "VAT number",
        "vat_number_note": "VAT number is required.",
        "vat_number_foreign_note": "If not applicable, foreign groups can write /.",
        "adults_label": "Adults",
        "children_label": "Children",
        "total_label": "Total",
        "section_total_note": "Must match guests from previous step: {count}",
        "tourist_tax": "Tourist tax",
        "tourist_tax_exemption_note": "Tourist tax exemption: the group can be excused from paying tourist tax if it provides proof of being an NGO. An official document must be sent.",
        "back": "Back",
        "reset_this_page": "Reset this page",
        "media_logout": "Media logout",
        "admin_login_title": "Admin media access",
        "username": "Username",
        "password": "Password",
        "unlock_media_tools": "Unlock media tools",
        "invalid_username_password": "Invalid username or password.",
        "media_tools_unlocked": "Media tools unlocked",
        "media_tools_locked": "Media tools locked",
        "admin_login_required": "Admin login required.",
        "upload_button": "Upload",
        "upload_drop_hint": "Drop images here or choose files.",
        "make_first_picture": "Make first",
        "move_picture_back": "Move back",
        "move_picture_forward": "Move forward",
        "admin_manual_booking": "Manual booking",
        "admin_reservation_board": "Reservation board",
        "admin_board_intro": "Visual overview grouped by location and unit across the current year and the next two years.",
        "admin_bookings": "Bookings",
        "admin_booking_details": "Booking #{id} details",
        "admin_reservation_details": "Reservation details",
        "admin_calculation": "Calculation",
        "admin_create_booking": "Create admin booking",
        "admin_booking_created": "Admin booking created",
        "admin_status_updated": "Booking status updated",
        "admin_details": "Details",
        "admin_update": "Update",
        "admin_allow_overbooking": "Allow overbooking",
        "admin_no_bookings": "No bookings yet.",
        "admin_default": "Default",
        "admin_all_campsites": "All campsites",
        "admin_all_countries": "All countries",
        "admin_unit": "Unit",
        "admin_check_in": "Check-in",
        "admin_check_out": "Check-out",
        "admin_status": "Status",
        "admin_total": "Total",
        "admin_action": "Action",
        "admin_applied": "Applied",
        "admin_campsite": "Campsite",
        "admin_group_name": "Group name",
        "admin_stay": "Stay",
        "admin_board_heading": "Reservations by unit",
        "admin_board_empty": "No reservations in this period.",
        "admin_unit_header": "Unit",
        "admin_guests_max": "{count} guests max",
        "status_pending": "pending",
        "status_confirmed": "confirmed",
        "status_fee_paid": "paid reservation fee",
        "status_cancelled": "cancelled",
        "status_rejected": "rejected",
        "status_expired": "expired",
        "rental": "Rental",
        "rental_heading": "Rental",
        "rental_comments_label": "Rental comments",
        "rental_comments_help": "Use this if you need more than the listed limit or want to add rental details.",
        "continue_to_contact": "Continue to contact details",
        "continue_to_rental": "Continue to rental",
        "rental_yes": "Yes",
        "rental_no": "No",
        "rental_days_label": "Days",
        "rental_how_many_days": "How many days?",
        "rental_days_count": "{count} days",
        "rental_day_count": "{count} day",
        "rental_date_later": "The exact date is to be decided later",
        "rental_add_picture": "Add picture for {label}",
        "rental_available_selected_dates": "Available for selected dates: {count}",
        "contact_details": "Contact details",
        "contact_leader_section": "{label} contact details",
        "first_name_label": "Name",
        "surname_label": "Surname",
        "contact_name_surname": "{label}: name, surname",
        "contact_address": "{label} address",
        "contact_address_help": "street with house number, town, zip code",
        "contact_email": "{label} e-mail",
        "contact_phone": "Reachable telephone number",
        "phone_country_code_note": "Please include the country code, e.g. +xxx (phone number).",
        "contact_same_as": "Same as {label}",
        "contact_person_name": "Contact person: name, surname",
        "contact_person_address": "Contact person address",
        "contact_person_email": "Contact person e-mail",
        "international_commissioner_name": "International commissioner: name, surname",
        "international_commissioner_address": "International commissioner address",
        "international_commissioner_email": "International commissioner e-mail",
        "international_commissioner_phone": "International commissioner telephone",
        "continue_to_summary": "Continue to summary",
        "unit_leader_label": "Unit leader",
        "group_leader_label": "Group leader",
        "other_information": "Other information",
        "subcamp": "Subcamp",
        "our_group_is_from": "Our (scout) group is from:",
        "choose_one": "Choose one",
        "capacity_guests": "Capacity: {count} guests",
        "booking_submitted": "Booking submitted",
        "booking_submitted_text": "Your booking request has been submitted successfully.",
        "booking_email_sent": "A booking summary has been sent to the contact person's email address.",
        "booking_email_not_sent": "The booking was saved, but the confirmation email could not be sent yet.",
        "info_eyebrow": "Before you choose dates",
        "info_title": "Scout and group stays in one overview.",
        "info_text": "Use this first page to review the available places, practical notes, and useful documents before you continue to the date and availability step.",
        "info_continue": "Continue to period selection",
        "info_map_heading": "Locations map",
        "info_map_text": "Zoom in or out and select a pin to view the campsite location.",
        "info_places_heading": "Places overview",
        "info_documents_heading": "Documents and useful links",
        "info_document_rules": "House rules and camp instructions",
        "info_document_prices": "Price and rental information",
        "info_document_contact": "Contact before booking",
        "info_document_nature_heading": "General information and rules in nature",
        "info_document_nature_zts": "Visiting nature in Slovenia",
        "info_document_nature_pzs": "Summer mountaineering safety tips",
        "info_document_nature_tnp": "Triglav National Park map",
        "info_document_campsite_heading": "Campsite rules",
        "info_document_campsite_tc": "TC campsite rules",
        "info_document_campsite_laski": "Laški rovt campsite rules of conduct",
        "info_document_campsite_bohinj": "Rules of conduct in Bohinj",
        "info_document_other_heading": "Other documents and informations",
        "info_document_contact_notice": "For questions before booking, please send an e-mail to tc.bohinj@taborniki.si.",
        "info_document_other_izola": "LD Izola program",
        "info_document_other_participants": "List of participants GS-ZTS",
        "info_document_other_sales": "Sales actions for scouts",
        "info_document_other_radlje": "What to do in and around Radlje ob Dravi",
        "info_document_note": "Document links can be replaced with final PDFs or external pages when they are ready.",
        "landing_eyebrow": "Bohinj and scout accommodation",
        "landing_title": "Choose your place first, then check occupancy for your dates.",
        "landing_text": "This booking prototype works best when each location quickly explains what it offers. Browse the camps and houses below, compare capacity and season notes, then continue into the reservation flow.",
        "landing_stat_locations": "Locations",
        "landing_stat_units": "Bookable units",
        "landing_stat_groups_value": "Scout",
        "landing_stat_groups": "Designed for groups",
        "location_search_title": "Check occupancy",
        "location_units_available": "{count} bookable units",
        "location_season_label": "Season note",
        "location_capacity_label": "Total capacity",
        "from_price": "From EUR {amount} per guest per night",
        "availability_loading": "Checking live availability...",
        "availability_choose_dates": "Choose dates to see live remaining capacity.",
        "availability_remaining": "{count} guests can still stay for the full selected period.",
        "availability_full": "No guest capacity remains for the full selected period.",
        "availability_partial_days": "{location}: occupied days in your selected period: {days}",
        "availability_fully_open": "{location}: all selected days currently have full availability.",
    },
    "sl": {
        "search": "Iskanje",
        "admin": "Admin",
        "prototype": "Lokalni prototip",
        "information": "Informacije",
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
        "estimated_total_warning": "Opozorilo: to ni končni izračun. Končni potrjeni izračun bo poslan po e-pošti po potrditvi in pripravi pogodbe.",
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
        "group_details_intro": "Spodaj dodajte strukturo skupine in nato nadaljujte s kontaktnimi podatki.",
        "sections_heading": "Sekcije",
        "sections_intro": "Dodajte število oseb v vsaki starostni kategoriji. Ti podatki se uporabijo tudi za turistično takso.",
        "scout_unit_details": "Podatki o skavtski enoti",
        "taborniki_unit_details": "Podatki o taborniški enoti",
        "national_scout_organization": "Nacionalna skavtska organizacija",
        "local_scout_unit": "Lokalna skavtska enota",
        "local_taborniki_unit": "Lokalna taborniška enota",
        "group_name_label": "Registrirano ime skupine",
        "street_label": "Ulica",
        "house_number_label": "Hišna številka",
        "post_code_label": "Poštna številka",
        "town_label": "Kraj",
        "country_label": "Država",
        "vat_number_label": "Davčna številka",
        "vat_number_note": "Davčna številka je obvezna.",
        "vat_number_foreign_note": "Če ni relevantno, lahko tuje skupine vpišejo /.",
        "adults_label": "Odrasli",
        "children_label": "Otroci",
        "total_label": "Skupaj",
        "section_total_note": "Mora ustrezati številu gostov iz prejšnjega koraka: {count}",
        "tourist_tax": "Turistična taksa",
        "tourist_tax_exemption_note": "Oprostitev turistične takse: skupina je lahko oproščena plačila turistične takse, če predloži dokazilo, da je nevladna organizacija. Poslati mora uradni dokument.",
        "back": "Nazaj",
        "reset_this_page": "Ponastavi to stran",
        "media_logout": "Odjava medijskih orodij",
        "admin_login_title": "Dostop do admin medijskih orodij",
        "username": "Uporabniško ime",
        "password": "Geslo",
        "unlock_media_tools": "Omogoči medijska orodja",
        "invalid_username_password": "Nepravilno uporabniško ime ali geslo.",
        "media_tools_unlocked": "Medijska orodja so omogočena",
        "media_tools_locked": "Medijska orodja so zaklenjena",
        "admin_login_required": "Potrebna je admin prijava.",
        "upload_button": "Naloži",
        "upload_drop_hint": "Spustite slike sem ali izberite datoteke.",
        "make_first_picture": "Nastavi kot prvo",
        "move_picture_back": "Premakni nazaj",
        "move_picture_forward": "Premakni naprej",
        "admin_manual_booking": "Ročna rezervacija",
        "admin_reservation_board": "Tabla rezervacij",
        "admin_board_intro": "Vizualni pregled po lokacijah in enotah skozi trenutno leto in naslednji dve leti.",
        "admin_bookings": "Rezervacije",
        "admin_booking_details": "Podrobnosti rezervacije #{id}",
        "admin_reservation_details": "Podrobnosti rezervacije",
        "admin_calculation": "Izračun",
        "admin_create_booking": "Ustvari admin rezervacijo",
        "admin_booking_created": "Admin rezervacija ustvarjena",
        "admin_status_updated": "Status rezervacije posodobljen",
        "admin_details": "Podrobnosti",
        "admin_update": "Posodobi",
        "admin_allow_overbooking": "Dovoli prekomerno rezervacijo",
        "admin_no_bookings": "Še ni rezervacij.",
        "admin_default": "Privzeto",
        "admin_all_campsites": "Vsi taborni prostori",
        "admin_all_countries": "Vse države",
        "admin_unit": "Enota",
        "admin_check_in": "Prihod",
        "admin_check_out": "Odhod",
        "admin_status": "Status",
        "admin_total": "Skupaj",
        "admin_action": "Dejanje",
        "admin_applied": "Oddano",
        "admin_campsite": "Taborni prostor",
        "admin_group_name": "Ime skupine",
        "admin_stay": "Termin",
        "admin_board_heading": "Rezervacije po enotah",
        "admin_board_empty": "V tem obdobju ni rezervacij.",
        "admin_unit_header": "Enota",
        "admin_guests_max": "Največ {count} gostov",
        "status_pending": "v obdelavi",
        "status_confirmed": "potrjeno",
        "status_fee_paid": "plačana rezervacija",
        "status_cancelled": "preklicano",
        "status_rejected": "zavrnjeno",
        "status_expired": "poteklo",
        "rental": "Izposoja",
        "rental_heading": "Izposoja",
        "rental_comments_label": "Komentarji za izposojo",
        "rental_comments_help": "Uporabite to, če potrebujete več kot navedeno omejitev ali želite dodati podrobnosti izposoje.",
        "continue_to_contact": "Nadaljuj na kontaktne podatke",
        "continue_to_rental": "Nadaljuj na izposojo",
        "rental_yes": "Da",
        "rental_no": "Ne",
        "rental_days_label": "Dnevi",
        "rental_how_many_days": "Za koliko dni?",
        "rental_days_count": "{count} dni",
        "rental_day_count": "{count} dan",
        "rental_date_later": "Točen datum bo določen kasneje",
        "rental_add_picture": "Dodaj sliko za {label}",
        "rental_available_selected_dates": "Na voljo za izbrane datume: {count}",
        "contact_details": "Kontaktni podatki",
        "contact_leader_section": "Kontaktni podatki: {label}",
        "first_name_label": "Ime",
        "surname_label": "Priimek",
        "contact_name_surname": "{label}: ime in priimek",
        "contact_address": "{label} naslov",
        "contact_address_help": "ulica s hišno številko, kraj, poštna številka",
        "contact_email": "{label} e-pošta",
        "contact_phone": "Dosegljiva telefonska številka",
        "phone_country_code_note": "Prosimo, dodajte tudi klicno številko države, npr. +xxx (telefonska številka).",
        "contact_same_as": "Enako kot {label}",
        "contact_person_name": "Kontaktna oseba: ime in priimek",
        "contact_person_address": "Naslov kontaktne osebe",
        "contact_person_email": "E-pošta kontaktne osebe",
        "international_commissioner_name": "Mednarodni komisar: ime in priimek",
        "international_commissioner_address": "Naslov mednarodnega komisarja",
        "international_commissioner_email": "E-pošta mednarodnega komisarja",
        "international_commissioner_phone": "Telefon mednarodnega komisarja",
        "continue_to_summary": "Nadaljuj na povzetek",
        "unit_leader_label": "Vodja enote",
        "group_leader_label": "Vodja skupine",
        "other_information": "Ostale informacije",
        "subcamp": "Podtabor",
        "our_group_is_from": "Naša (skavtska) skupina prihaja iz:",
        "choose_one": "Izberite eno",
        "capacity_guests": "Kapaciteta: {count} gostov",
        "booking_submitted": "Rezervacija oddana",
        "booking_submitted_text": "Vaša rezervacijska zahteva je bila uspešno oddana.",
        "booking_email_sent": "Povzetek rezervacije je bil poslan na e-poštni naslov kontaktne osebe.",
        "booking_email_not_sent": "Rezervacija je bila shranjena, vendar potrditvenega e-sporočila še ni bilo mogoče poslati.",
        "info_eyebrow": "Pred izbiro termina",
        "info_title": "Pregled taborniških in skupinskih nastanitev.",
        "info_text": "Na tej prvi strani so zbrane osnovne informacije o lokacijah, praktične opombe ter prostor za dokumente in uporabne povezave pred nadaljevanjem na izbiro termina.",
        "info_continue": "Nadaljuj na izbiro termina",
        "info_map_heading": "Zemljevid lokacij",
        "info_map_text": "Povečajte ali pomanjšajte zemljevid in izberite oznako za ogled lokacije.",
        "info_places_heading": "Pregled lokacij",
        "info_documents_heading": "Dokumenti in uporabne povezave",
        "info_document_rules": "Hišni red in navodila za taborjenje",
        "info_document_prices": "Cenik in informacije o izposoji",
        "info_document_contact": "Kontakt pred rezervacijo",
        "info_document_nature_heading": "Splošne informacije in pravila v naravi",
        "info_document_nature_zts": "Obiskovanje narave v Sloveniji",
        "info_document_nature_pzs": "Poletni nasveti za varno obiskovanje gora",
        "info_document_nature_tnp": "Zemljevid Triglavskega narodnega parka",
        "info_document_campsite_heading": "Pravila tabornih prostorov",
        "info_document_campsite_tc": "Pravila tabornih prostorov TC",
        "info_document_campsite_laski": "Pravila obnašanja na taboru Laški rovt",
        "info_document_campsite_bohinj": "Pravila obnašanja v Bohinju",
        "info_document_other_heading": "Drugi dokumenti in informacije",
        "info_document_contact_notice": "Za vprašanja pred rezervacijo pošljite e-pošto na tc.bohinj@taborniki.si.",
        "info_document_other_izola": "Program LD Izola",
        "info_document_other_participants": "Seznam udeležencev GS-ZTS",
        "info_document_other_sales": "Prodajne akcije za skavte",
        "info_document_other_radlje": "Kaj početi v Radljah ob Dravi in okolici",
        "info_document_note": "Povezave do dokumentov lahko kasneje zamenjamo s končnimi PDF-ji ali zunanjimi stranmi.",
        "landing_eyebrow": "Bohinjske in taborniške nastanitve",
        "landing_title": "Najprej izberite lokacijo, nato preverite razpoložljivost za svoje datume.",
        "landing_text": "Ta prototip rezervacij deluje najbolje, če vsaka lokacija hitro pokaže, kaj ponuja. Spodaj preglejte tabore in hiše, primerjajte kapacitete ter sezonske opombe in nato nadaljujte v rezervacijski tok.",
        "landing_stat_locations": "Lokacij",
        "landing_stat_units": "Nastanitvenih enot",
        "landing_stat_groups_value": "Taborniki",
        "landing_stat_groups": "Primerno za taborniške skupine",
        "location_search_title": "Preveri razpoložljivost",
        "location_units_available": "{count} rezervacijskih enot",
        "location_season_label": "Sezonska opomba",
        "location_capacity_label": "Skupna kapaciteta",
        "from_price": "Od EUR {amount} na gosta na noč",
        "availability_loading": "Preverjanje trenutne razpoložljivosti...",
        "availability_choose_dates": "Izberite datume za prikaz preostale kapacitete.",
        "availability_remaining": "Za celotno izbrano obdobje je še na voljo {count} gostov.",
        "availability_full": "Za celotno izbrano obdobje ni več proste kapacitete.",
        "availability_partial_days": "{location}: zasedeni dnevi v izbranem obdobju: {days}",
        "availability_fully_open": "{location}: vsi izbrani dnevi imajo trenutno polno razpoložljivost.",
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
BOOKING_STATUSES = ["pending", "confirmed", "fee_paid", "cancelled", "rejected", "expired"]
ACTIVE_BOOKING_STATUSES = ("pending", "confirmed", "fee_paid")
GROUP_SECTION_OPTIONS = [
    ("age_0_6", "0-6.99 years of age"),
    ("age_7_17", "7-17.99 years of age"),
    ("age_18_plus", "18+ years of age"),
]
NON_SCOUT_SECTION_LABELS = {
    "age_0_6": "0-6.99 years of age",
    "age_7_17": "7-17.99 years of age",
    "age_18_plus": "18+ years of age",
}
ZTS_SECTION_LABELS = {
    "age_0_6": "0-6.99 years of age",
    "age_7_17": "7-17.99 years of age",
    "age_18_plus": "18+ years of age",
}
SLOVENIA_OTHER_SECTION_LABELS = {
    "age_0_6": "0-6.99 years of age",
    "age_7_17": "7-17.99 years of age",
    "age_18_plus": "18+ years of age",
}
ADULT_SECTION_KEYS = {"age_18_plus"}
TOURIST_TAX_RATES = {
    "age_0_6": Decimal("0.00"),
    "age_7_17": Decimal("1.25"),
    "age_18_plus": Decimal("2.50"),
}
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


def load_slovenia_postcodes():
    path = DATA_DIR / "slovenia_postcodes.json"
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        return []
    rows = []
    for item in data:
        postcode = str(item.get("postcode", "")).strip()
        town = str(item.get("town", "")).strip()
        if postcode and town:
            rows.append({"postcode": postcode, "town": town})
    return rows


SLOVENIA_POSTCODE_ROWS = load_slovenia_postcodes()
RENTAL_ITEMS = [
    {"key": "kitchen", "label": "Kitchen", "price": "50.00 EUR", "note": "rent per stay, maximum 2 per group", "max_quantity": 2},
    {"key": "cooler_refrigerator", "label": "Cooler/refrigerator", "price": "50.00 EUR", "note": "rent per stay, maximum 1 per group", "max_quantity": 1},
    {"key": "tent", "label": "Tent", "price": "25.00 EUR", "note": "rent per stay, maximum 10 across all locations", "max_quantity": 10},
    {"key": "table_set", "label": "Set of tables and two benches", "price": "10.00 EUR", "note": "rent per day per set, maximum 10 per group. If needed more than 10 add in the comments below.", "max_quantity": 10},
    {"key": "small_canoe_half_day", "label": "Small canoe (up to 3 people)", "price": "25.00 EUR", "note": "morning or afternoon, pickup at Ukanc forest school (Ukanc 3), maximum 3", "max_quantity": 3},
    {"key": "small_canoe_all_day", "label": "Small canoe (up to 3 people)", "price": "35.00 EUR", "note": "all day, pickup at Ukanc forest school (Ukanc 3), maximum 3", "max_quantity": 3},
    {"key": "large_canoe_half_day", "label": "Large canoe (up to 10 people)", "price": "30.00 EUR", "note": "morning or afternoon, pickup at Ukanc forest school (Ukanc 3), maximum 2", "max_quantity": 2},
    {"key": "large_canoe_all_day", "label": "Large canoe (up to 10 people)", "price": "45.00 EUR", "note": "all day, pickup at Ukanc forest school (Ukanc 3), maximum 2", "max_quantity": 2},
    {"key": "bike_half_day", "label": "Bike", "price": "10.00 EUR", "note": "morning or afternoon, pickup at Ukanc forest school (Ukanc 3), maximum 15", "max_quantity": 15},
    {"key": "bike_all_day", "label": "Bike", "price": "20.00 EUR", "note": "all day, pickup at Ukanc forest school (Ukanc 3), maximum 15", "max_quantity": 15},
    {"key": "electric_bike_half_day", "label": "Electric bike", "price": "40.00 EUR", "note": "half day, pickup at Ukanc forest school (Ukanc 3), maximum 10", "max_quantity": 10, "disabled": True, "disabled_note": "not yet available"},
    {"key": "electric_bike_all_day", "label": "Electric bike", "price": "60.00 EUR", "note": "all day, pickup at Ukanc forest school (Ukanc 3), maximum 10", "max_quantity": 10, "disabled": True, "disabled_note": "not yet available"},
    {"key": "sup_all_day", "label": "SUP", "price": "10.00 EUR", "note": "all day, maximum 2", "max_quantity": 2},
    {"key": "bow_half_day", "label": "Bow", "price": "10.00 EUR", "note": "morning or afternoon, arrows and target included, pickup at Ukanc forest school (Ukanc 3), maximum 2", "max_quantity": 2},
    {"key": "bow_all_day", "label": "Bow", "price": "15.00 EUR", "note": "all day, arrows and target included, pickup at Ukanc forest school (Ukanc 3), maximum 2", "max_quantity": 2},
    {"key": "air_rifle_half_day", "label": "Air rifle", "price": "10.00 EUR", "note": "morning or afternoon, pellets and target included, pickup at Ukanc forest school (Ukanc 3), maximum 1", "max_quantity": 1},
    {"key": "air_rifle_all_day", "label": "Air rifle", "price": "15.00 EUR", "note": "all day, pellets and target included, pickup at Ukanc forest school (Ukanc 3), maximum 1", "max_quantity": 1},
    {"key": "firewood", "label": "Firewood", "price": "90 EUR/m³", "note": "base unit is 1 m³", "quantity_options": ["0.5", "1", "2"]},
    {"key": "pioneering_wood", "label": "Pioneering projects wood", "price": "5.00 EUR per log", "note": "when selected, specify how many and approximately how long, maximum 50 logs", "max_quantity": 50, "requires_length": True},
]
RENTAL_ITEM_TRANSLATIONS = {
    "sl": {
        "kitchen": {"label": "Kuhinja", "note": "najem na bivanje, največ 2 na skupino"},
        "cooler_refrigerator": {"label": "Hladilnik", "note": "najem na bivanje, največ 1 na skupino"},
        "tent": {"label": "Šotor", "note": "najem na bivanje, največ 10 na vseh lokacijah"},
        "table_set": {"label": "Komplet miz in dveh klopi", "note": "najem na dan na komplet, največ 10 na skupino. Če potrebujete več kot 10, dodajte v komentar spodaj."},
        "small_canoe_half_day": {"label": "Mali kanu (do 3 osebe)", "note": "dopoldan ali popoldan, prevzem pri Gozdni šoli Ukanc (Ukanc 3), največ 3"},
        "small_canoe_all_day": {"label": "Mali kanu (do 3 osebe)", "note": "cel dan, prevzem pri Gozdni šoli Ukanc (Ukanc 3), največ 3"},
        "large_canoe_half_day": {"label": "Veliki kanu (do 10 oseb)", "note": "dopoldan ali popoldan, prevzem pri Gozdni šoli Ukanc (Ukanc 3), največ 2"},
        "large_canoe_all_day": {"label": "Veliki kanu (do 10 oseb)", "note": "cel dan, prevzem pri Gozdni šoli Ukanc (Ukanc 3), največ 2"},
        "bike_half_day": {"label": "Kolo", "note": "dopoldan ali popoldan, prevzem pri Gozdni šoli Ukanc (Ukanc 3), največ 15"},
        "bike_all_day": {"label": "Kolo", "note": "cel dan, prevzem pri Gozdni šoli Ukanc (Ukanc 3), največ 15"},
        "electric_bike_half_day": {"label": "Električno kolo", "note": "poldnevni najem, prevzem pri Gozdni šoli Ukanc (Ukanc 3), največ 10", "disabled_note": "še ni na voljo"},
        "electric_bike_all_day": {"label": "Električno kolo", "note": "celodnevni najem, prevzem pri Gozdni šoli Ukanc (Ukanc 3), največ 10", "disabled_note": "še ni na voljo"},
        "sup_all_day": {"label": "SUP", "note": "cel dan, največ 2"},
        "bow_half_day": {"label": "Lok", "note": "dopoldan ali popoldan, puščice in tarča vključene, prevzem pri Gozdni šoli Ukanc (Ukanc 3), največ 2"},
        "bow_all_day": {"label": "Lok", "note": "cel dan, puščice in tarča vključene, prevzem pri Gozdni šoli Ukanc (Ukanc 3), največ 2"},
        "air_rifle_half_day": {"label": "Zračna puška", "note": "dopoldan ali popoldan, naboji in tarča vključeni, prevzem pri Gozdni šoli Ukanc (Ukanc 3), največ 1"},
        "air_rifle_all_day": {"label": "Zračna puška", "note": "cel dan, naboji in tarča vključeni, prevzem pri Gozdni šoli Ukanc (Ukanc 3), največ 1"},
        "firewood": {"label": "Drva", "note": "osnovna enota je 1 m3"},
        "pioneering_wood": {"label": "Les za pionirske projekte", "note": "ob izbiri navedite koliko kosov in približno dolžino, največ 50 kosov"},
    }
}
LIMITED_RENTAL_KEYS_BY_LOCATION = {
    "Taborni prostor Baredi": {"kitchen", "cooler_refrigerator", "tent"},
    "Taborni prostor Radlje ob Dravi": {"kitchen", "cooler_refrigerator", "tent", "firewood", "pioneering_wood"},
}
RENTAL_ITEMS_WITH_DAY_COUNT = {
    "table_set",
    "small_canoe_half_day",
    "small_canoe_all_day",
    "large_canoe_half_day",
    "large_canoe_all_day",
    "bike_half_day",
    "bike_all_day",
    "electric_bike_half_day",
    "electric_bike_all_day",
    "sup_all_day",
    "bow_half_day",
    "bow_all_day",
    "air_rifle_half_day",
    "air_rifle_all_day",
}
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


def format_location_units_available(lang, count):
    count = int(count)
    if get_lang(lang) != "sl":
        return tf(lang, "location_units_available", count=count)
    if count == 1:
        suffix = "rezervacijska enota"
    elif count == 2:
        suffix = "rezervacijski enoti"
    elif count in {3, 4}:
        suffix = "rezervacijske enote"
    else:
        suffix = "rezervacijskih enot"
    return f"{count} {suffix}"


def format_stay_range(lang, start_value, end_value):
    connector = "do" if get_lang(lang) == "sl" else "to"
    return f"{start_value} {connector} {end_value}"


def contact_leader_label(lang, is_group_leader):
    return t(lang, "group_leader_label" if is_group_leader else "unit_leader_label")


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
    options_json = html.escape(json.dumps(COUNTRY_OPTIONS), quote=True)
    input_id = html.escape(list_id)
    return (
        f'<span class="country-combobox">'
        f'<input type="text" id="{input_id}" name="{html.escape(name)}" value="{html.escape(selected_value)}" '
        f'autocomplete="off" class="country-input" role="combobox" aria-autocomplete="list" '
        f'aria-expanded="false" data-country-options="{options_json}">'
        f'<span class="country-suggestions" role="listbox" hidden></span>'
        f'</span>'
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


def localized_rental_item(item, lang):
    translated = RENTAL_ITEM_TRANSLATIONS.get(get_lang(lang), {}).get(item["key"], {})
    if not translated:
        return item
    localized = dict(item)
    localized.update({key: value for key, value in translated.items() if value})
    return localized


def render_rental_quantity_select(item, selected_value, available_max=None):
    options = ['<option value="" class="rental-zero-option">0</option>']
    if "quantity_options" in item:
        for value in item["quantity_options"]:
            if available_max is not None and Decimal(str(value)) > available_max:
                continue
            selected_attr = " selected" if str(value) == str(selected_value) else ""
            options.append(f'<option value="{value}"{selected_attr}>{value}</option>')
    else:
        limit = item["max_quantity"]
        if available_max is not None:
            limit = min(limit, int(available_max))
        for number in range(1, limit + 1):
            selected_attr = " selected" if str(number) == str(selected_value) else ""
            options.append(f'<option value="{number}"{selected_attr}>{number}</option>')
    return (
        f'<select class="rental-qty" data-rental-key="{item["key"]}" name="rental_{item["key"]}">'
        f'{"".join(options)}'
        f'</select>'
    )


def should_hide_rental_quantity(location_name, item):
    return location_name in {"Taborni prostor Baredi", "Taborni prostor Radlje ob Dravi"} and item["key"] in {"kitchen", "cooler_refrigerator"}


def render_rental_days_select(item, selected_value, total_nights, lang="en"):
    options = []
    selected = str(selected_value or "1")
    for number in range(1, max(1, total_nights) + 1):
        selected_attr = " selected" if str(number) == selected else ""
        options.append(f'<option value="{number}"{selected_attr}>{number}</option>')
    return (
        f'<label class="rental-extra-field">'
        f'  <span>{html.escape(t(lang, "rental_how_many_days"))}</span>'
        f'  <select class="rental-days" name="rental_{item["key"]}_days">{"".join(options)}</select>'
        f'</label>'
    )


def parse_selected_dates_value(raw_value):
    selected = []
    for chunk in str(raw_value or "").split(","):
        value = chunk.strip()
        if not value:
            continue
        if value == "__later__":
            return ["__later__"]
        try:
            normalized = parse_date(value).isoformat()
        except ValueError:
            continue
        if normalized not in selected:
            selected.append(normalized)
    return selected


def rental_dates_to_be_decided_later(entry):
    return "__later__" in (entry.get("selected_dates") or [])


def render_rental_selected_dates_picker(item, params, stay_dates, lang):
    item_key = item["key"]
    parsed_selected_dates = parse_selected_dates_value(params.get(f"rental_{item_key}_selected_dates", ""))
    decided_later = "__later__" in parsed_selected_dates
    selected_dates = {value for value in parsed_selected_dates if value != "__later__"}
    buttons = []
    for stay_date in stay_dates:
        iso_value = stay_date.isoformat()
        selected_class = " is-selected" if iso_value in selected_dates else ""
        buttons.append(
            f'''
            <button type="button" class="rental-date-button{selected_class}" data-date="{iso_value}">
              <span>{stay_date.strftime("%d.%m.")}</span>
              <small>{stay_date.strftime("%a")}</small>
            </button>
            '''
        )
    count = len(selected_dates)
    count_label = t(lang, "rental_date_later") if decided_later else tf(lang, "rental_day_count" if count == 1 else "rental_days_count", count=count)
    return f"""
    <span class="rental-days-inline">
      <strong>{html.escape(t(lang, "rental_days_label"))}</strong>
      <span class="rental-days-count">{count_label}</span>
    </span>
    <div class="rental-extra rental-extra--dates">
      <input type="hidden" class="rental-selected-dates" name="rental_{item_key}_selected_dates" value="{html.escape('__later__' if decided_later else ','.join(sorted(selected_dates)))}">
      <label class="rental-decide-later">
        <input type="checkbox" class="rental-decide-later-toggle" {'checked' if decided_later else ''}>
        <span>{html.escape(t(lang, "rental_date_later"))}</span>
      </label>
      <div class="rental-date-grid">
        {''.join(buttons)}
      </div>
    </div>
    """


def build_return_to(path, params):
    query = urlencode({key: value for key, value in params.items() if value != ""})
    return f"{path}?{query}" if query else path


def add_query_params_to_url(url, params):
    parts = urlsplit(url or "/")
    query_params = dict(parse_qsl(parts.query, keep_blank_values=True))
    query_params.update({key: value for key, value in params.items() if value is not None})
    return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", urlencode(query_params), parts.fragment))


def upload_anchor_for_target(target_type, location_name, unit_name=""):
    return "upload-" + slugify_location_name("-".join(part for part in (target_type, location_name, unit_name) if part))


DETAILS_RESET_KEYS = {
    "group_name",
    "organization_name",
    "group_street",
    "group_house_number",
    "group_post_code",
    "group_town",
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

CONTACT_RESET_KEYS = {
    "unit_leader_name",
    "unit_leader_first_name",
    "unit_leader_last_name",
    "unit_leader_address",
    "unit_leader_street",
    "unit_leader_house_number",
    "unit_leader_post_code",
    "unit_leader_town",
    "unit_leader_email",
    "unit_leader_phone",
    "contact_same_as_unit_leader",
    "contact_person_name",
    "contact_person_first_name",
    "contact_person_last_name",
    "contact_person_phone",
    "contact_person_address",
    "contact_person_street",
    "contact_person_house_number",
    "contact_person_post_code",
    "contact_person_town",
    "contact_person_email",
    "international_commissioner_name",
    "international_commissioner_address",
    "international_commissioner_email",
    "international_commissioner_phone",
}


def contact_full_name(source, prefix):
    first_name = source.get(f"{prefix}_first_name", "").strip()
    last_name = source.get(f"{prefix}_last_name", "").strip()
    full_name = " ".join(part for part in (first_name, last_name) if part)
    return full_name or source.get(f"{prefix}_name", "").strip()


def contact_full_address(source, prefix):
    street = source.get(f"{prefix}_street", "").strip()
    house_number = source.get(f"{prefix}_house_number", "").strip()
    post_code = source.get(f"{prefix}_post_code", "").strip()
    town = source.get(f"{prefix}_town", "").strip()
    street_line = " ".join(part for part in (street, house_number) if part)
    town_line = " ".join(part for part in (post_code, town) if part)
    full_address = ", ".join(part for part in (street_line, town_line) if part)
    return full_address or source.get(f"{prefix}_address", "").strip()


def split_contact_name(value):
    parts = str(value or "").strip().split()
    if len(parts) <= 1:
        return str(value or "").strip(), ""
    return " ".join(parts[:-1]), parts[-1]


def should_keep_reset_param(step_name, key):
    if step_name == "type":
        return key in {
            "lang",
            "admin_mode",
            "location_id",
            "check_in",
            "check_out",
            "guest_count",
            "origin_country",
            "member_category",
        }
    if step_name == "details":
        return key not in DETAILS_RESET_KEYS and not key.startswith("section_") and not key.startswith("rental_") and key not in CONTACT_RESET_KEYS
    if step_name == "rental":
        return not key.startswith("rental_") and key != "rental_comments"
    if step_name == "contact":
        return key not in CONTACT_RESET_KEYS
    if step_name == "summary":
        return True
    return True


def build_reset_href(step_name, current_path, params):
    filtered = {
        key: value
        for key, value in params.items()
        if should_keep_reset_param(step_name, key)
    }
    return build_return_to(current_path, filtered)


def render_step_actions(back_href, continue_html, lang, reset_href=""):
    return f"""
    <div class="step-actions field-span-full">
      <a class="button button-secondary" href="{html.escape(back_href)}">{html.escape(t(lang, "back"))}</a>
      {f'<a class="button button-reset" href="{html.escape(reset_href)}">{html.escape(t(lang, "reset_this_page"))}</a>' if reset_href else ''}
      {continue_html}
    </div>
    """


def render_step_actions_form(back_path, continue_html, lang, reset_href=""):
    return f"""
    <div class="step-actions field-span-full">
      <button type="submit" class="button button-secondary" formaction="{html.escape(back_path)}" formnovalidate>{html.escape(t(lang, "back"))}</button>
      {f'<a class="button button-reset" href="{html.escape(reset_href)}">{html.escape(t(lang, "reset_this_page"))}</a>' if reset_href else ''}
      {continue_html}
    </div>
    """


def parse_rental_quantities(source):
    selected = []
    for item in RENTAL_ITEMS:
        enabled = source.get(f"rental_{item['key']}_enabled", "") == "yes"
        raw_value = str(source.get(f"rental_{item['key']}", "")).strip()
        length_value = str(source.get(f"rental_{item['key']}_length", "")).strip()
        days_value = str(source.get(f"rental_{item['key']}_days", "")).strip()
        selected_dates = parse_selected_dates_value(source.get(f"rental_{item['key']}_selected_dates", ""))
        if "quantity_options" in item:
            quantity_value = raw_value if raw_value in item["quantity_options"] else ""
            if enabled and quantity_value:
                selected.append({"item": item, "quantity": quantity_value, "length": length_value, "days": days_value, "selected_dates": selected_dates})
        else:
            quantity = min(
                to_non_negative_int(raw_value or "0"),
                item["max_quantity"],
            )
            if enabled and quantity > 0:
                selected.append({"item": item, "quantity": str(quantity), "length": length_value, "days": days_value, "selected_dates": selected_dates})
    return selected


def get_rental_items_for_location(location_name):
    allowed_keys = LIMITED_RENTAL_KEYS_BY_LOCATION.get(location_name)
    items = RENTAL_ITEMS if allowed_keys is None else [item for item in RENTAL_ITEMS if item["key"] in allowed_keys]
    return sorted(items, key=lambda item: item["label"].lower())


def parse_rental_quantities_for_location(source, location_name):
    allowed_keys = {item["key"] for item in get_rental_items_for_location(location_name)}
    return [entry for entry in parse_rental_quantities(source) if entry["item"]["key"] in allowed_keys]


def get_rental_max_quantity(item):
    if "quantity_options" in item:
        return max(Decimal(str(value)) for value in item["quantity_options"])
    return Decimal(str(item["max_quantity"]))


def get_rental_requested_quantity(entry):
    return Decimal(str(entry["quantity"]))


def rental_uses_day_count(item):
    return item["key"] in RENTAL_ITEMS_WITH_DAY_COUNT


def get_rental_selected_days(entry, total_nights):
    if not rental_uses_day_count(entry["item"]):
        return Decimal("1")
    if rental_dates_to_be_decided_later(entry):
        return Decimal("0")
    selected_dates = entry.get("selected_dates") or []
    if selected_dates:
        return Decimal(str(len(selected_dates)))
    try:
        parsed = Decimal(str(entry.get("days", "1") or "1"))
    except Exception:
        parsed = Decimal("1")
    maximum = Decimal(str(max(1, total_nights)))
    return min(max(Decimal("1"), parsed), maximum)


def get_reserved_rental_quantity(connection, item_key, check_in, check_out, exclude_booking_id=None):
    sql = """
        select coalesce(sum(br.quantity), 0)
        from booking_rentals br
        join bookings b on b.id = br.booking_id
        where br.item_key = ?
          and b.status in ('pending', 'confirmed', 'fee_paid')
          and b.check_in < ?
          and b.check_out > ?
    """
    params = [item_key, check_out.isoformat(), check_in.isoformat()]
    if exclude_booking_id is not None:
        sql += " and b.id != ?"
        params.append(exclude_booking_id)
    value = connection.execute(sql, params).fetchone()[0]
    return Decimal(str(value or "0"))


def get_rental_remaining_quantity(connection, item, check_in, check_out, exclude_booking_id=None):
    maximum = get_rental_max_quantity(item)
    reserved = get_reserved_rental_quantity(
        connection,
        item["key"],
        check_in,
        check_out,
        exclude_booking_id=exclude_booking_id,
    )
    return max(Decimal("0"), maximum - reserved)


def get_rental_availability(connection, check_in, check_out, exclude_booking_id=None):
    availability = {}
    for item in RENTAL_ITEMS:
        availability[item["key"]] = get_rental_remaining_quantity(
            connection,
            item,
            check_in,
            check_out,
            exclude_booking_id=exclude_booking_id,
        )
    return availability


def validate_rental_availability(connection, check_in, check_out, selected_rentals, exclude_booking_id=None):
    errors = []
    availability = get_rental_availability(
        connection,
        check_in,
        check_out,
        exclude_booking_id=exclude_booking_id,
    )
    for entry in selected_rentals:
        item = entry["item"]
        if rental_uses_day_count(item):
            if rental_dates_to_be_decided_later(entry):
                continue
            selected_dates = [
                value for value in entry.get("selected_dates", [])
                if check_in.isoformat() <= value < check_out.isoformat()
            ]
            if not selected_dates:
                errors.append(f"{item['label']}: choose at least one rental day.")
                continue
        requested = get_rental_requested_quantity(entry)
        remaining = availability[item["key"]]
        if requested > remaining:
            remaining_text = format_decimal_display(remaining)
            errors.append(
                f"{item['label']}: only {remaining_text} left for the selected dates."
            )
    return errors, availability


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
          and b.status in ('pending', 'confirmed', 'fee_paid')
          and b.check_in < ?
          and b.check_out > ?
        """,
        ("Taborni prostor Ukanc", "Gozdna sola Ukanc", check_out.isoformat(), check_in.isoformat()),
    ).fetchone()
    return int(row["booking_count"]) if row else 0


def rental_is_per_day(item):
    return rental_uses_day_count(item) or "per day" in str(item.get("note", "")).lower()


def rental_discount_rate(amount):
    amount = Decimal(amount)
    if amount >= Decimal("200.00"):
        return Decimal("0.50")
    if amount >= Decimal("150.00"):
        return Decimal("0.40")
    if amount > Decimal("100.00"):
        return Decimal("0.30")
    return Decimal("0.00")


def format_rental_summary_label(item):
    label = item["label"]
    item_key = str(item.get("key", ""))
    if item_key.endswith("_half_day"):
        return f"{label} - half day"
    if item_key.endswith("_all_day"):
        return f"{label} - all day"
    return label


def build_tourist_tax_rows(section_rows, total_nights):
    rows = []
    total = Decimal("0.00")
    for row in section_rows or []:
        if not row.get("selected"):
            continue
        count = int(row.get("count", 0) or 0)
        if count <= 0:
            continue
        rate = TOURIST_TAX_RATES.get(row.get("key"), Decimal("0.00"))
        amount = (rate * Decimal(count) * Decimal(total_nights)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total += amount
        rows.append({
            "label": f"Tourist tax - {row['label']}",
            "participants": str(count),
            "nights": str(total_nights),
            "price": format_currency(rate),
            "amount": format_currency(amount),
        })
    return rows, total


def section_rows_from_labels(selected_sections):
    rows = []
    for key, label in GROUP_SECTION_OPTIONS:
        count = 0
        for section in selected_sections or []:
            prefix = f"{label}:"
            if section.startswith(prefix):
                count = to_non_negative_int(section.removeprefix(prefix).strip())
                break
        rows.append({"key": key, "label": label, "selected": count > 0, "count": count})
    return rows


def build_summary_breakdown(connection, unit, check_in, check_out, guest_count, member_category, boarding_option, laski_group_type, selected_rentals, section_rows=None):
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

    tourist_tax_rows, tourist_tax_total = build_tourist_tax_rows(section_rows, total_nights)
    rows.extend(tourist_tax_rows)
    total_amount += tourist_tax_total

    for entry in selected_rentals:
        item = entry["item"]
        quantity = Decimal(str(entry["quantity"]))
        rate = parse_decimal_amount(item["price"])
        rental_nights = get_rental_selected_days(entry, total_nights) if rental_is_per_day(item) else Decimal("1")
        base_amount = (rate * quantity * rental_nights).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        discount_rate = rental_discount_rate(base_amount)
        discount_amount = (base_amount * discount_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        amount = (base_amount - discount_amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total_amount += amount
        label = format_rental_summary_label(item)
        if entry.get("length"):
            label += f" ({entry['length']})"
        note = ""
        if rental_dates_to_be_decided_later(entry):
            note = "The exact date is to be decided later"
        if discount_rate > 0:
            note = (note + " | " if note else "") + f"{int(discount_rate * 100)}% discount"
        rows.append({
            "label": label,
            "participants": entry["quantity"],
            "nights": "TBD" if rental_dates_to_be_decided_later(entry) else format_decimal_display(rental_nights),
            "price": format_currency(rate),
            "amount": format_currency(amount),
            "note": note,
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


def render_breakdown_table(breakdown, lang="en"):
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
    {'<p class="tourist-tax-note"><strong>' + html.escape(t(lang, "tourist_tax_exemption_note")) + '</strong></p>' if any(row["label"].startswith("Tourist tax") for row in breakdown["rows"]) else ''}
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
    is_non_scout_group = data.get("laski_group_type", "") == "non_scouts"
    is_slovenia_other_group = is_slovenia_country(data.get("origin_country", "")) and data.get("member_category", "") == "other"
    is_slovenia_zts_group = is_slovenia_country(data.get("origin_country", "")) and (data.get("member_category", "") == "zts_member" or data.get("laski_group_type", "") == "taborniki_zts")
    leader_label = contact_leader_label(lang, is_non_scout_group or is_slovenia_other_group)
    blocks = [
        render_detail_group("Group details" if (is_non_scout_group or is_slovenia_other_group) else t(lang, "taborniki_unit_details") if is_slovenia_zts_group else t(lang, "scout_unit_details"), [
            *(([] if (is_non_scout_group or is_slovenia_other_group) else [("National scout organization", data["organization_name"] or not_specified)])),
            (("Registered name of the group" if (is_non_scout_group or is_slovenia_other_group) else t(lang, "local_taborniki_unit") if is_slovenia_zts_group else t(lang, "local_scout_unit")), data["group_name"] or not_specified),
            ("Street", data["group_street"] or not_specified),
            ("House number", data["group_house_number"] or not_specified),
            ("Post code", data["group_post_code"] or not_specified),
            ("Town", data["group_town"] or not_specified),
            ("VAT number", data["vat_number"] or not_specified),
            ("Country", data["country"] or not_specified),
        ]),
        render_detail_group("Participants", [
            ("Age categories", sections),
            ("Total participants", data["guest_count"] or not_specified),
        ]),
        render_detail_group(leader_label, [
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
        *(([] if (is_non_scout_group or is_slovenia_other_group) else [render_detail_group("International commissioner", [
            ("Name, surname", data["international_commissioner_name"] or not_specified),
            ("Address", data["international_commissioner_address"] or not_specified),
            ("E-mail", data["international_commissioner_email"] or not_specified),
            ("Telephone", data["international_commissioner_phone"] or not_specified),
        ])])),
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
    unit_leader_name = contact_full_name(params, "unit_leader")
    unit_leader_address = contact_full_address(params, "unit_leader")
    unit_leader_email = params.get("unit_leader_email", "")
    unit_leader_phone = params.get("unit_leader_phone", "")
    contact_same_as_unit_leader = params.get("contact_same_as_unit_leader", "") == "on"
    contact_person_name = contact_full_name(params, "contact_person")
    contact_person_phone = params.get("contact_person_phone", "")
    contact_person_address = contact_full_address(params, "contact_person")
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
    group_street = params.get("group_street", "")
    group_house_number = params.get("group_house_number", "")
    group_post_code = params.get("group_post_code", "")
    group_town = params.get("group_town", "")
    vat_number = params.get("vat_number", "")
    country = params.get("country", "")
    rental_comments = params.get("rental_comments", "")
    adult_total, child_total, section_rows = calculate_section_totals(params)
    section_rows = normalize_section_rows_for_group_type(section_rows, laski_group_type, member_category, params.get("origin_country", ""))
    adult_count = str(adult_total)
    child_count = str(child_total)
    selected_rentals = parse_rental_quantities_for_location(params, unit["location_name"])
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
        section_rows,
    )
    details_data = {
        "organization_name": organization_name,
        "group_name": group_name,
        "origin_country": params.get("origin_country", ""),
        "member_category": member_category,
        "laski_group_type": laski_group_type,
        "group_street": group_street,
        "group_house_number": group_house_number,
        "group_post_code": group_post_code,
        "group_town": group_town,
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
            (
                f"{entry['item']['label']} x{entry['quantity']}"
                + (
                    " for the exact date to be decided later"
                    if rental_dates_to_be_decided_later(entry)
                    else (f" for {format_decimal_display(get_rental_selected_days(entry, nights_between(parse_date(check_in), parse_date(check_out))))} days" if rental_uses_day_count(entry["item"]) else "")
                )
                + (f" ({entry['length']})" if entry['length'] else "")
            )
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


def render_rental_item_row(item, params, lang, admin_mode, return_to, stay_dates, available_quantity=None, location_name=""):
    item = localized_rental_item(item, lang)
    item_key = item["key"]
    is_disabled = bool(item.get("disabled"))
    enabled_value = "no" if is_disabled else params.get(f"rental_{item_key}_enabled", "no")
    hide_quantity = should_hide_rental_quantity(location_name, item)
    availability_note = ""
    if available_quantity is not None and not is_disabled:
        availability_note = tf(lang, "rental_available_selected_dates", count=format_decimal_display(available_quantity))
    gallery_images = get_rental_item_gallery(item_key)
    gallery_html = ""
    if admin_mode:
        lead_image = gallery_images[0]
        gallery_html = f"""
        <div class="rental-gallery-admin">
          <img src="{lead_image["url"]}" alt="{html.escape(item["label"])}" class="rental-item-image">
          {render_gallery_admin_controls(lang, "rental_item", item_key, "", lead_image, return_to=return_to) if lead_image.get("filename") else ""}
          {render_upload_form(lang, "rental_item", item_key, "", tf(lang, "rental_add_picture", label=item['label']), extra_class="upload-form--unit", return_to=return_to)}
        </div>
        """
    return f"""
    <div class="rental-item-wrap">
      <label class="rental-row{' rental-row--disabled' if is_disabled else ''}">
        <span class="rental-meta">
          <strong>{html.escape(item["label"])}</strong>
          {f'<span class="rental-unavailable-note">{html.escape(item["disabled_note"])}</span>' if is_disabled and item.get("disabled_note") else ''}
          <span>{html.escape(item["note"]) if item["note"] else ""}</span>
          {f'<span class="rental-availability">{html.escape(availability_note)}</span>' if availability_note else ''}
        </span>
        <span class="rental-price">{html.escape(item["price"])}</span>
        <span class="rental-choice">
          <label><input type="radio" name="rental_{item_key}_enabled" value="no" {"checked" if enabled_value != "yes" else ""} {"disabled" if is_disabled else ""}> {html.escape(t(lang, "rental_no"))}</label>
          <label><input type="radio" name="rental_{item_key}_enabled" value="yes" {"checked" if enabled_value == "yes" else ""} {"disabled" if is_disabled else ""}> {html.escape(t(lang, "rental_yes"))}</label>
        </span>
        {(
            f'<input type="hidden" class="rental-qty rental-qty-hidden" data-rental-key="{item_key}" name="rental_{item_key}" value="1">'
            if hide_quantity else render_rental_quantity_select(item, "" if is_disabled else params.get(f"rental_{item_key}", ""), None if is_disabled else available_quantity)
        )}
        {'' if is_disabled else (render_rental_selected_dates_picker(item, params, stay_dates, lang) if rental_uses_day_count(item) else '')}
      </label>
      {(
        '<div class="rental-extra">'
        + (
            f'''
            <label class="rental-extra-field">
              <span>Approximate length of the logs (write as 5x 5m, 6x 4m)</span>
              <input type="text" class="rental-extra-input" data-rental-key="{item_key}" name="rental_{item_key}_length" value="{html.escape(params.get(f"rental_{item_key}_length", ""))}" {"disabled" if is_disabled else ""}>
            </label>
            '''
            if item.get("requires_length") else ''
        )
        + '</div>'
      ) if item.get("requires_length") else ''}
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


def normalize_section_rows_for_group_type(section_rows, group_type, member_category="", origin_country=""):
    normalized_rows = []
    use_zts_labels = group_type == "taborniki_zts" or member_category == "zts_member"
    use_slovenia_other_labels = member_category == "other" and is_slovenia_country(origin_country)
    for row in section_rows:
        normalized = dict(row)
        if group_type == "non_scouts":
            normalized["label"] = NON_SCOUT_SECTION_LABELS.get(row["key"], row["label"])
        elif use_slovenia_other_labels:
            normalized["label"] = SLOVENIA_OTHER_SECTION_LABELS.get(row["key"], row["label"])
        elif use_zts_labels:
            normalized["label"] = ZTS_SECTION_LABELS.get(row["key"], row["label"])
        if normalized["label"]:
            normalized_rows.append(normalized)
    return normalized_rows


def validate_group_details_params(params):
    errors = []
    is_non_scout_group = params.get("laski_group_type", "") == "non_scouts"
    is_slovenia_other_group = is_slovenia_country(params.get("origin_country", "")) and params.get("member_category", "") == "other"
    vat_number = params.get("vat_number", "").strip()
    if not params.get("group_name", "").strip():
        errors.append("Registered name of the group is required." if (is_non_scout_group or is_slovenia_other_group) else "Local scout unit is required.")
    if not params.get("group_street", "").strip():
        errors.append("Street is required.")
    if not params.get("group_house_number", "").strip():
        errors.append("House number is required.")
    if not params.get("group_post_code", "").strip():
        errors.append("Post code is required.")
    if not params.get("group_town", "").strip():
        errors.append("Town is required.")
    if not is_non_scout_group and not is_slovenia_other_group and not params.get("organization_name", "").strip():
        errors.append("National scout organization is required.")
    if not vat_number:
        errors.append("VAT number is required.")
    elif is_slovenia_country(params.get("origin_country", "")) and vat_number == "/":
        errors.append("VAT number is required for Slovenian groups. / is only allowed for foreign groups.")
    adults, children, _ = calculate_section_totals(params)
    total = adults + children
    expected_total = to_non_negative_int(params.get("guest_count", "0"))
    if total != expected_total:
        errors.append(f"Section total must equal the guest count ({expected_total}).")
    return errors


def validate_contact_details_params(params):
    errors = []
    is_slovenia_other_group = is_slovenia_country(params.get("origin_country", "")) and params.get("member_category", "") == "other"
    leader_label = contact_leader_label("en", params.get("laski_group_type", "") == "non_scouts" or is_slovenia_other_group)
    required_fields = [
        ("unit_leader_first_name", f"{leader_label} first name is required."),
        ("unit_leader_last_name", f"{leader_label} surname is required."),
        ("unit_leader_street", f"{leader_label} street is required."),
        ("unit_leader_house_number", f"{leader_label} house number is required."),
        ("unit_leader_post_code", f"{leader_label} post code is required."),
        ("unit_leader_town", f"{leader_label} town is required."),
        ("unit_leader_email", f"{leader_label} email is required."),
        ("unit_leader_phone", f"{leader_label} telephone number is required."),
    ]
    for field_name, message in required_fields:
        if not params.get(field_name, "").strip():
            errors.append(message)
    if not contact_full_name(params, "unit_leader"):
        errors.append(f"{leader_label} name is required.")
    if not contact_full_address(params, "unit_leader"):
        errors.append(f"{leader_label} address is required.")
    same_as_unit_leader = params.get("contact_same_as_unit_leader", "") == "on"
    if not same_as_unit_leader:
        contact_required = [
            ("contact_person_first_name", "Contact person first name is required."),
            ("contact_person_last_name", "Contact person surname is required."),
            ("contact_person_phone", "Reachable telephone number is required."),
            ("contact_person_street", "Contact person street is required."),
            ("contact_person_house_number", "Contact person house number is required."),
            ("contact_person_post_code", "Contact person post code is required."),
            ("contact_person_town", "Contact person town is required."),
            ("contact_person_email", "Contact person email is required."),
        ]
        for field_name, message in contact_required:
            if not params.get(field_name, "").strip():
                errors.append(message)
        if not contact_full_name(params, "contact_person"):
            errors.append("Contact person name is required.")
        if not contact_full_address(params, "contact_person"):
            errors.append("Contact person address is required.")
    return errors


def validate_rental_params(connection, params):
    unit_id = int(params.get("unit_id", "0") or "0")
    unit = get_unit(connection, unit_id)
    if not unit:
        return ["Selected unit does not exist."]
    try:
        check_in = parse_date(params.get("check_in", ""))
        check_out = parse_date(params.get("check_out", ""))
    except ValueError:
        return ["Dates must use the YYYY-MM-DD format."]
    selected_rentals = parse_rental_quantities_for_location(params, unit["location_name"])
    errors, _ = validate_rental_availability(connection, check_in, check_out, selected_rentals)
    return errors


def display_location_name(name, lang):
    return LOCATION_LABELS.get(name, {}).get(get_lang(lang), name)


def display_unit_name(name, lang):
    if name.startswith("Subcamp "):
        return f"{t(lang, 'subcamp')} {name.split(' ', 1)[1]}"
    return name


def display_location_with_unit(location_name, unit_name, lang):
    location_label = display_location_name(location_name, lang)
    if not unit_name or unit_name == "Main":
        return location_label
    return f"{location_label} / {display_unit_name(unit_name, lang)}"


def translate_location_type(value, lang):
    return t(lang, f"location_type_{value}")


def get_location_content(name, lang):
    content = LOCATION_CONTENT.get(name, {})
    return content.get(get_lang(lang), {})


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


def load_gallery_order(gallery_dir):
    order_path = gallery_dir / "order.json"
    if not order_path.exists():
        return []
    try:
        order = json.loads(order_path.read_text(encoding="utf-8"))
        return order if isinstance(order, list) else []
    except Exception:
        return []


def save_gallery_order(gallery_dir, filenames):
    order_path = gallery_dir / "order.json"
    order_path.write_text(json.dumps(filenames, indent=2), encoding="utf-8")


def list_gallery_items(gallery_dir, web_prefix):
    items = []
    captions = load_gallery_captions(gallery_dir)
    order = load_gallery_order(gallery_dir)
    order_index = {filename: index for index, filename in enumerate(order)}
    if gallery_dir.exists():
        for pattern in ("*.jpg", "*.jpeg", "*.png", "*.webp", "*.svg"):
            for path in gallery_dir.glob(pattern):
                items.append(
                    {
                        "url": f"{web_prefix}/{path.name}",
                        "filename": path.name,
                        "caption": captions.get(path.name, ""),
                    }
                )
    return sorted(items, key=lambda item: (order_index.get(item["filename"], len(order)), item["filename"]))


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
    raw_uploads = form["image"] if "image" in form else []
    uploads = raw_uploads if isinstance(raw_uploads, list) else [raw_uploads]
    uploads = [upload for upload in uploads if getattr(upload, "filename", "")]
    if not uploads:
        return lang, "No image selected.", return_to

    target_dir = gallery_dir_for_target(target_type, location_name, unit_name)
    if target_dir is None:
        return lang, "Invalid upload target.", return_to

    target_dir.mkdir(parents=True, exist_ok=True)
    saved_count = 0
    for upload in uploads:
        original_name = Path(upload.filename).name
        suffix = Path(original_name).suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".svg"}:
            return lang, "Unsupported image type.", return_to
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        safe_name = f"{timestamp}-{saved_count + 1}{suffix}"
        target_path = target_dir / safe_name
        with open(target_path, "wb") as output_file:
            output_file.write(upload.file.read())
        saved_count += 1
    return lang, f"{saved_count} image{'s' if saved_count != 1 else ''} uploaded.", return_to


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
    order = [name for name in load_gallery_order(target_dir) if name != filename]
    save_gallery_order(target_dir, order)
    return lang, "Image deleted.", return_to


def make_gallery_image_primary(environ):
    form = read_post_data(environ)
    lang = get_lang(form.get("lang", "en"))
    return_to = form.get("return_to", "/")
    if not is_admin_request(environ):
        return lang, "Admin login required.", return_to
    target_dir = gallery_dir_for_target(form.get("target_type", ""), form.get("location_name", ""), form.get("unit_name", ""))
    if target_dir is None:
        return lang, "Invalid gallery target.", return_to
    filename = Path(form.get("filename", "")).name
    if not filename or not (target_dir / filename).exists():
        return lang, "Missing filename.", return_to
    current_order = [item["filename"] for item in list_gallery_items(target_dir, "") if item.get("filename")]
    save_gallery_order(target_dir, [filename] + [name for name in current_order if name != filename])
    return lang, "Primary picture updated.", return_to


def move_gallery_image(environ):
    form = read_post_data(environ)
    lang = get_lang(form.get("lang", "en"))
    return_to = form.get("return_to", "/")
    if not is_admin_request(environ):
        return lang, "Admin login required.", return_to
    target_dir = gallery_dir_for_target(form.get("target_type", ""), form.get("location_name", ""), form.get("unit_name", ""))
    if target_dir is None:
        return lang, "Invalid gallery target.", return_to
    filename = Path(form.get("filename", "")).name
    direction = form.get("direction", "")
    if not filename or not (target_dir / filename).exists():
        return lang, "Missing filename.", return_to
    current_order = [item["filename"] for item in list_gallery_items(target_dir, "") if item.get("filename")]
    if filename not in current_order:
        return lang, "Missing filename.", return_to
    index = current_order.index(filename)
    if direction == "back" and index > 0:
        current_order[index - 1], current_order[index] = current_order[index], current_order[index - 1]
    elif direction == "forward" and index < len(current_order) - 1:
        current_order[index + 1], current_order[index] = current_order[index], current_order[index + 1]
    save_gallery_order(target_dir, current_order)
    return lang, "Picture order updated.", return_to


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
                status text not null check (status in ('pending', 'confirmed', 'fee_paid', 'cancelled', 'rejected', 'expired')),
                total_price numeric not null check (total_price >= 0),
                created_by_admin integer not null default 0,
                overbook_allowed integer not null default 0,
                notes text,
                created_at text not null default current_timestamp,
                updated_at text not null default current_timestamp,
                check (check_out > check_in)
            );

            create table if not exists booking_rentals (
                id integer primary key autoincrement,
                booking_id integer not null references bookings(id) on delete cascade,
                item_key text not null,
                quantity numeric not null check (quantity > 0),
                length text,
                selected_dates text,
                created_at text not null default current_timestamp
            );

            create index if not exists idx_bookable_units_location_id
                on bookable_units(location_id);

            create index if not exists idx_bookings_unit_dates
                on bookings(bookable_unit_id, check_in, check_out);

            create index if not exists idx_bookings_status
                on bookings(status);

            create index if not exists idx_booking_rentals_booking_id
                on booking_rentals(booking_id);

            create index if not exists idx_booking_rentals_item_key
                on booking_rentals(item_key);
            """
        )
        rental_columns = {
            row["name"]
            for row in connection.execute("pragma table_info(booking_rentals)")
        }
        if "selected_dates" not in rental_columns:
            connection.execute("alter table booking_rentals add column selected_dates text")
        bookings_table_sql_row = connection.execute(
            "select sql from sqlite_master where type = 'table' and name = 'bookings'"
        ).fetchone()
        bookings_table_sql = (bookings_table_sql_row[0] or "") if bookings_table_sql_row else ""
        if "'fee_paid'" not in bookings_table_sql:
            connection.executescript(
                """
                alter table bookings rename to bookings_old;

                create table bookings (
                    id integer primary key autoincrement,
                    bookable_unit_id integer not null references bookable_units(id) on delete restrict,
                    guest_name text not null,
                    guest_email text not null,
                    guest_phone text,
                    check_in text not null,
                    check_out text not null,
                    guest_count integer not null check (guest_count > 0),
                    status text not null check (status in ('pending', 'confirmed', 'fee_paid', 'cancelled', 'rejected', 'expired')),
                    total_price numeric not null check (total_price >= 0),
                    created_by_admin integer not null default 0,
                    overbook_allowed integer not null default 0,
                    notes text,
                    created_at text not null default current_timestamp,
                    updated_at text not null default current_timestamp,
                    check (check_out > check_in)
                );

                insert into bookings (
                    id, bookable_unit_id, guest_name, guest_email, guest_phone, check_in, check_out,
                    guest_count, status, total_price, created_by_admin, overbook_allowed, notes, created_at, updated_at
                )
                select
                    id, bookable_unit_id, guest_name, guest_email, guest_phone, check_in, check_out,
                    guest_count, status, total_price, created_by_admin, overbook_allowed, notes, created_at, updated_at
                from bookings_old;

                drop table bookings_old;

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


def format_decimal_display(value):
    normalized = Decimal(str(value)).normalize()
    text = format(normalized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


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
          and status in ('pending', 'confirmed', 'fee_paid')
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


def get_location_availability_summary(connection, location_id, check_in, check_out):
    location = None
    for item in fetch_locations(connection):
        if str(item["id"]) == str(location_id):
            location = item
            break
    if not location:
        return None

    unit_summaries = []
    remaining_capacity = 0
    for unit in location["units"]:
        reservations = get_reserved_guests_by_day(connection, unit["id"], check_in, check_out)
        min_available = unit["max_guests"]
        for stay_date in daterange(check_in, check_out):
            reserved = reservations.get(stay_date, 0)
            min_available = min(min_available, max(0, unit["max_guests"] - reserved))
        remaining_capacity += min_available
        unit_summaries.append(
            {
                "unit_id": unit["id"],
                "unit_name": unit["name"],
                "remaining_capacity": min_available,
                "max_guests": unit["max_guests"],
            }
        )
    return {
        "location_id": int(location["id"]),
        "location_name": location["name"],
        "remaining_capacity": remaining_capacity,
        "units": unit_summaries,
    }


def get_location_daily_availability(connection, location_id, start_date, end_date):
    location = None
    for item in fetch_locations(connection):
        if str(item["id"]) == str(location_id):
            location = item
            break
    if not location:
        return None

    total_capacity = sum(unit["max_guests"] for unit in location["units"])
    reservations_by_unit = {
        unit["id"]: get_reserved_guests_by_day(connection, unit["id"], start_date, end_date)
        for unit in location["units"]
    }
    days = []
    for current_date in daterange(start_date, end_date):
        remaining = 0
        for unit in location["units"]:
            reserved = reservations_by_unit[unit["id"]].get(current_date, 0)
            remaining += max(0, unit["max_guests"] - reserved)
        days.append(
            {
                "date": current_date.isoformat(),
                "remaining_capacity": remaining,
                "total_capacity": total_capacity,
                "occupied": remaining < total_capacity,
                "full": remaining <= 0,
            }
        )
    return {
        "location_id": int(location["id"]),
        "location_name": location["name"],
        "total_capacity": total_capacity,
        "days": days,
    }


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


def extract_country_from_notes(notes):
    match = re.search(r"(?:^|\|\s*)Country:\s*([^|]+)", str(notes or ""))
    return match.group(1).strip() if match else ""


def extract_group_name_from_notes(notes):
    match = re.search(r"(?:^|\|\s*)Group name:\s*([^|]+)", str(notes or ""))
    return match.group(1).strip() if match else ""


def parse_booking_notes_metadata(notes):
    metadata = {}
    extra_notes = []
    for chunk in re.split(r"\s+\|\s+", str(notes or "").strip()):
        part = chunk.strip()
        if not part:
            continue
        if ":" in part:
            key, value = part.split(":", 1)
            metadata[key.strip()] = value.strip()
        else:
            extra_notes.append(part)
    return metadata, " | ".join(extra_notes)


def fetch_booking_rentals(connection, booking_id):
    return connection.execute(
        """
        select booking_id, item_key, quantity, length, selected_dates
        from booking_rentals
        where booking_id = ?
        order by id asc
        """,
        (booking_id,),
    ).fetchall()


def format_selected_rental_summary(entry, total_nights):
    item = entry["item"]
    label = format_rental_summary_label(item)
    summary = f"{label} x{entry['quantity']}"
    if rental_dates_to_be_decided_later(entry):
        summary += " for the exact date to be decided later"
    elif rental_uses_day_count(item):
        summary += f" for {format_decimal_display(get_rental_selected_days(entry, total_nights))} days"
    if entry.get("length"):
        summary += f" ({entry['length']})"
    return summary


def build_admin_booking_view_data(connection, booking):
    unit = get_unit(connection, booking["bookable_unit_id"])
    if not unit:
        return None
    metadata, extra_notes = parse_booking_notes_metadata(booking.get("notes", ""))
    rental_lookup = {item["key"]: item for item in RENTAL_ITEMS}
    selected_rentals = []
    for rental_row in fetch_booking_rentals(connection, booking["id"]):
        item = rental_lookup.get(rental_row["item_key"])
        if not item:
            continue
        selected_rentals.append(
            {
                "item": item,
                "quantity": str(rental_row["quantity"]),
                "length": rental_row["length"] or "",
                "selected_dates": parse_selected_dates_value(rental_row["selected_dates"] or ""),
            }
        )
    check_in = parse_date(booking["check_in"])
    check_out = parse_date(booking["check_out"])
    total_nights = nights_between(check_in, check_out)
    member_category = metadata.get("Member category", "")
    laski_group_type = metadata.get("Laski group type", "")
    country = metadata.get("Country", "")
    details_data = {
        "organization_name": metadata.get("Organization", ""),
        "group_name": metadata.get("Group name", ""),
        "group_street": metadata.get("Street", ""),
        "group_house_number": metadata.get("House number", ""),
        "group_post_code": metadata.get("Post code", ""),
        "group_town": metadata.get("Town", ""),
        "vat_number": metadata.get("VAT number", ""),
        "country": country,
        "origin_country": country,
        "member_category": member_category,
        "laski_group_type": laski_group_type,
        "selected_sections": [part.strip() for part in metadata.get("Sections", "").split(",") if part.strip()],
        "adult_count": metadata.get("Adults", ""),
        "child_count": metadata.get("Children", ""),
        "guest_count": str(booking["guest_count"]),
        "unit_leader_name": metadata.get("Unit leader", "") or metadata.get("Group leader", ""),
        "unit_leader_address": metadata.get("Unit leader address", "") or metadata.get("Group leader address", ""),
        "unit_leader_email": metadata.get("Unit leader email", "") or metadata.get("Group leader email", ""),
        "unit_leader_phone": metadata.get("Unit leader phone", "") or metadata.get("Group leader phone", ""),
        "contact_person_name": metadata.get("Contact person", ""),
        "contact_person_address": metadata.get("Contact person address", ""),
        "contact_person_email": metadata.get("Contact person email", ""),
        "contact_person_phone": metadata.get("Contact person phone", ""),
        "international_commissioner_name": metadata.get("International commissioner", ""),
        "international_commissioner_address": metadata.get("International commissioner address", ""),
        "international_commissioner_email": metadata.get("International commissioner email", ""),
        "international_commissioner_phone": metadata.get("International commissioner phone", ""),
        "check_in": booking["check_in"],
        "check_out": booking["check_out"],
        "preferred_arrival_slot": metadata.get("Preferred arrival time", ""),
        "preferred_arrival_note": metadata.get("Arrival note", ""),
        "preferred_departure_slot": metadata.get("Preferred departure time", ""),
        "preferred_departure_note": metadata.get("Departure note", ""),
        "selected_rentals": [format_selected_rental_summary(entry, total_nights) for entry in selected_rentals],
        "rental_comments": metadata.get("Rental comments", ""),
        "notes": extra_notes,
    }
    breakdown = build_summary_breakdown(
        connection,
        unit,
        check_in,
        check_out,
        int(booking["guest_count"]),
        member_category,
        metadata.get("Boarding option", ""),
        laski_group_type,
        selected_rentals,
        section_rows_from_labels(details_data["selected_sections"]),
    )
    return {"unit": unit, "details_data": details_data, "breakdown": breakdown}


def booking_status_class(status):
    return {
        "pending": "is-pending",
        "confirmed": "is-confirmed",
        "fee_paid": "is-fee-paid",
        "cancelled": "is-cancelled",
        "rejected": "is-rejected",
        "expired": "is-expired",
    }.get(status, "is-pending")


def booking_status_label(status, lang="en"):
    status_key = {
        "pending": "status_pending",
        "confirmed": "status_confirmed",
        "fee_paid": "status_fee_paid",
        "cancelled": "status_cancelled",
        "rejected": "status_rejected",
        "expired": "status_expired",
    }.get(status)
    return t(lang, status_key) if status_key else status


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


def booking_status_group(status):
    if status in {"confirmed", "fee_paid"}:
        return "confirmed"
    if status == "pending":
        return "pending"
    return "other"


def assign_booking_tracks_by_status(bookings):
    group_order = ["confirmed", "pending", "other"]
    assigned = []
    next_track_index = 0
    for group_name in group_order:
        group_bookings = [booking for booking in bookings if booking_status_group(booking["status"]) == group_name]
        group_assigned, group_track_count = assign_booking_tracks(group_bookings)
        for booking, track_index in group_assigned:
            assigned.append((booking, next_track_index + track_index))
        if group_bookings:
            next_track_index += group_track_count + 1
    total_tracks = max(1, next_track_index - 1) if assigned else 1
    return assigned, total_tracks


def booking_matches_admin_filters(booking, filters):
    campsite = filters.get("campsite", "").strip()
    if campsite and booking["location_name"] != campsite:
        return False
    country = filters.get("country", "").strip().lower()
    if country and booking.get("country", "").strip().lower() != country:
        return False
    stay_date = filters.get("stay_date", "").strip()
    if stay_date:
        try:
            selected = parse_date(stay_date)
        except ValueError:
            return False
        if not (parse_date(booking["check_in"]) <= selected < parse_date(booking["check_out"])):
            return False
    applied_date = filters.get("applied_date", "").strip()
    if applied_date:
        created_date = str(booking.get("created_at", "")).split(" ")[0]
        if created_date != applied_date:
            return False
    return True


def render_booking_board(locations, bookings, board_start, board_end, lang="en", show_guest_names=True, heading_suffix="Reservations by unit", css_class="admin-board-section", empty_text="No reservations in this period.", compact=False):
    range_days = (board_end - board_start).days
    today = datetime.now().date()
    today_offset = (today - board_start).days
    column_style = f"grid-template-columns: repeat({range_days}, minmax(0, 1fr));"
    canvas_min_width = max(1200, range_days * 22) if not compact else max(2800, range_days * 15)
    label_column_width = 110 if compact else 180
    viewport_width = 980 if compact else None
    timeline_layout_style = (
        f'grid-template-columns: {label_column_width}px {canvas_min_width}px; width:{label_column_width + canvas_min_width}px;'
        if compact else ""
    )
    scroll_style = f'width:{viewport_width}px; max-width:{viewport_width}px;' if compact else ""
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
            assigned, track_count = assign_booking_tracks_by_status(relevant_bookings)
            bars = []
            for booking, track_index in assigned:
                visible_start = max(booking["check_in"], board_start)
                visible_end = min(booking["check_out"], board_end)
                span_days = max(1, (visible_end - visible_start).days)
                start_offset = (visible_start - board_start).days
                left = (start_offset / range_days) * 100
                width = (span_days / range_days) * 100
                top = 0.3 + (track_index * 1.45)
                bar_label = (
                    f"<strong>{html.escape(booking['guest_name'])}</strong><span>{booking['guest_count']} {html.escape(t(lang, 'guests_word'))}</span>"
                    if show_guest_names
                    else f"<strong>{html.escape(booking_status_label(booking['status']).upper())}</strong><span>{booking['guest_count']}</span>"
                )
                if show_guest_names:
                    bars.append(
                        f'''
                        <a class="booking-bar {booking_status_class(booking["status"])}"
                           href="#booking-{booking["id"]}"
                           style="left:{left:.4f}%; width:{width:.4f}%; top:{top:.2f}rem;">
                          {bar_label}
                        </a>
                        '''
                    )
                else:
                    bars.append(
                        f'''
                        <div class="booking-bar {booking_status_class(booking["status"])}"
                             style="left:{left:.4f}%; width:{width:.4f}%; top:{top:.2f}rem;">
                          {bar_label}
                        </div>
                        '''
                    )
            unit_rows.append(
                f'''
                <div class="booking-board-row" style="{timeline_layout_style}">
                  <div class="booking-board-label">
                    <strong>{html.escape(unit["name"])}</strong>
                    <span>{html.escape(tf(lang, "admin_guests_max", count=unit["max_guests"]))}</span>
                  </div>
                  <div class="booking-board-track" style="min-height:{(track_count * 1.45) + 0.6:.2f}rem; width:{canvas_min_width}px;">
                    <div class="booking-board-grid" style="{column_style}">
                      {''.join('<span class="booking-board-cell"></span>' for _ in range(range_days))}
                    </div>
                    {''.join(bars) if bars else f'<p class="booking-board-empty">{html.escape(empty_text)}</p>'}
                  </div>
                </div>
                '''
            )
        location_sections.append(
            f'''
            <section class="panel {css_class}">
              <div class="location-heading">
                <h2>{html.escape(location["name"])}</h2>
                <p>{html.escape(heading_suffix)}</p>
              </div>
              <div class="booking-board-scroll{' booking-board-scroll--compact' if compact else ''}" data-today-offset="{today_offset}" data-range-days="{range_days}" style="{scroll_style}">
                <div class="booking-board-canvas{' booking-board-canvas--compact' if compact else ''}" style="min-width:{canvas_min_width}px; width:{canvas_min_width}px;">
                  <div class="booking-board-header" style="{timeline_layout_style}">
                    <div class="booking-board-label booking-board-label--header">{html.escape(t(lang, "admin_unit_header"))}</div>
                    <div class="booking-board-headings">
                      <div class="booking-board-months" style="{column_style}">{''.join(month_cells)}</div>
                      <div class="booking-board-days" style="{column_style}">{''.join(day_cells)}</div>
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


def render_admin_booking_board(connection, locations, bookings, lang="en"):
    today = datetime.now().date()
    board_start = datetime(today.year, 1, 1).date()
    board_last_year = today.year + 2
    board_end = datetime(board_last_year + 1, 1, 1).date()
    return render_booking_board(
        locations,
        bookings,
        board_start,
        board_end,
        lang=lang,
        show_guest_names=True,
        heading_suffix=t(lang, "admin_board_heading"),
        css_class="admin-board-section",
        empty_text=t(lang, "admin_board_empty"),
        compact=False,
    )


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
        ("Information", t(lang, "information")),
        ("Period", t(lang, "period")),
        ("Type", t(lang, "type")),
        ("Group details", t(lang, "group_details")),
        ("Contact details", t(lang, "contact_details")),
        ("Rental", t(lang, "rental")),
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
    is_foreign_group = bool(origin_country.strip()) and not is_slovenia_country(origin_country)
    is_slovenia_other_group = is_slovenia_country(origin_country) and member_category == "other"
    if is_foreign_group:
        member_category = "other"
        if laski_group_type not in {"foreign_scouts", "non_scouts"}:
            laski_group_type = "foreign_scouts"
    elif is_slovenia_other_group:
        laski_group_type = "foreign_scouts"
    elif member_category == "zts_member":
        laski_group_type = "taborniki_zts"
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
    def render_foreign_group_type_panel():
        group_options = []
        for value, label in [("foreign_scouts", "Scout group"), ("non_scouts", "Non scout group")]:
            checked = " checked" if value == laski_group_type else ""
            group_options.append(
                f"""
                <label class="choice-item">
                  <input type="radio" name="laski_group_type" value="{value}"{checked}>
                  <span>{html.escape(label)}</span>
                </label>
                """
            )
        return f"""
        <section class="panel">
          <div class="location-heading">
            <h2>Type</h2>
            <p>Choose the type of group.</p>
          </div>
          <form method="get" action="/type" class="type-layout">
            <input type="hidden" name="location_id" value="{location_id}">
            <input type="hidden" name="lang" value="{lang}">
            <input type="hidden" name="check_in" value="{html.escape(check_in)}">
            <input type="hidden" name="check_out" value="{html.escape(check_out)}">
            <input type="hidden" name="guest_count" value="{html.escape(guest_count)}">
            <input type="hidden" name="origin_country" value="{html.escape(origin_country)}">
            <input type="hidden" name="member_category" value="other">
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
    if ukanc_flow:
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
        selection_panel = render_foreign_group_type_panel() if is_foreign_group else f"""
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
        zts_member_locked = member_category == "zts_member"
        if zts_member_locked:
            laski_group_type = "taborniki_zts"
        elif is_foreign_group and laski_group_type == "taborniki_zts":
            laski_group_type = "foreign_scouts"
        visible_group_types = (
            [("foreign_scouts", "Scout group"), ("non_scouts", "Non scout group")]
            if is_foreign_group
            else LASKI_GROUP_TYPES
        )
        group_options = []
        for value, label in visible_group_types:
            is_disabled = zts_member_locked and value != "taborniki_zts"
            checked = " checked" if value == laski_group_type else ""
            group_options.append(
                f"""
                <label class="choice-item{' choice-item--disabled' if is_disabled else ''}">
                  <input type="radio" name="laski_group_type" value="{value}"{checked}{" disabled" if is_disabled else ""}>
                  <span>{html.escape(label)}</span>
                </label>
                """
            )
        pricing_note = ""
        selection_panel = ""
        if not is_slovenia_other_group:
            selection_panel = render_foreign_group_type_panel() if is_foreign_group else f"""
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
            <input type="hidden" name="origin_country" value="{html.escape(origin_country)}">
            <input type="hidden" name="member_category" value="{html.escape(member_category)}">
            <input type="hidden" name="preferred_arrival_slot" value="{html.escape(preferred_arrival_slot)}">
            <input type="hidden" name="preferred_arrival_note" value="{html.escape(preferred_arrival_note)}">
            <input type="hidden" name="preferred_departure_slot" value="{html.escape(preferred_departure_slot)}">
            <input type="hidden" name="preferred_departure_note" value="{html.escape(preferred_departure_note)}">
            <section class="choice-panel">
              <h3>Type of group</h3>
              {'<p class="muted">Because you selected Member of Taborniki / ZTS in the previous step, only Taborniki ZTS is available here.</p>' if zts_member_locked else ''}
              <div class="choice-list">
                {''.join(group_options)}
              </div>
              <button type="submit">Update options</button>
            </section>
          </form>
        </section>
        """
    elif is_foreign_group:
        selection_panel = render_foreign_group_type_panel()

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
            if laski_flow or is_foreign_group:
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
    back_to_search = build_return_to("/period", back_to_search_params)
    back_to_search += f"#location-{location_id}"
    reset_href = build_reset_href("type", "/type", {key: first_param(params, key, "") for key in params.keys()})
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
        {render_step_actions(back_to_search, "", lang, reset_href)}
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
    member_category = params.get("member_category", "")
    if member_category == "zts_member":
        laski_group_type = "taborniki_zts"
    elif is_slovenia_country(params.get("origin_country", "")) and member_category == "other":
        laski_group_type = "foreign_scouts"
    is_non_scout_group = laski_group_type == "non_scouts"
    is_slovenia_other_group = is_slovenia_country(params.get("origin_country", "")) and member_category == "other"
    is_slovenia_zts_group = is_slovenia_country(params.get("origin_country", "")) and (member_category == "zts_member" or laski_group_type == "taborniki_zts")

    adult_total, child_total, section_rows = calculate_section_totals(params)
    section_rows = normalize_section_rows_for_group_type(section_rows, laski_group_type, member_category, params.get("origin_country", ""))
    section_total = adult_total + child_total
    expected_guest_total = to_non_negative_int(guest_count)

    fields = {
        "origin_country": params.get("origin_country", ""),
        "group_name": params.get("group_name", ""),
        "organization_name": params.get("organization_name", "") or ("Zveza tabornikov Slovenije" if laski_group_type == "taborniki_zts" or params.get("member_category", "") == "zts_member" else ""),
        "group_street": params.get("group_street", ""),
        "group_house_number": params.get("group_house_number", ""),
        "group_post_code": params.get("group_post_code", ""),
        "group_town": params.get("group_town", ""),
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
        "group_street",
        "group_house_number",
        "group_post_code",
        "group_town",
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
    reset_href = build_reset_href("details", "/details", params)

    content = f"""
    {render_reservation_steps("Group details", lang)}
    {error_html}
    <section class="panel">
      <h2>{html.escape(display_location_with_unit(unit['location_name'], unit['unit_name'], lang))}</h2>
      <p>{html.escape(t(lang, "stay"))}: {html.escape(format_stay_range(lang, check_in, check_out))}</p>
      <p>{html.escape(t(lang, "total_nights"))}: {total_nights}</p>
      <p>{html.escape(t(lang, "guests"))}: {html.escape(guest_count)}</p>
      <p>{html.escape(t(lang, "capacity"))}: {unit['max_guests']} {html.escape(t(lang, "guests_word"))}</p>
    </section>
    <section class="panel">
        <form method="get" action="/contact" class="booking-form">
        {hidden_html}
        <section class="form-section field-span-full">
          <h3>{html.escape(t(lang, "group_details"))}</h3>
          <p>{html.escape(t(lang, "group_details_intro"))}</p>
        </section>
        <section class="panel booking-extra field-span-full">
          <h3>{html.escape(t(lang, "sections_heading"))}</h3>
          <p>{html.escape(t(lang, "sections_intro"))}</p>
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
          <input type="hidden" name="adult_count" class="section-total-adults" value="{html.escape(fields['adult_count'])}">
          <input type="hidden" name="child_count" class="section-total-children" value="{html.escape(fields['child_count'])}">
          <div class="section-totals">
            <label>
              {html.escape(t(lang, "total_label"))}
              <input type="number" name="section_total" class="section-total-all" min="0" value="{section_total}" readonly>
              <small class="section-total-note">{html.escape(tf(lang, "section_total_note", count=expected_guest_total))}</small>
            </label>
          </div>
        </section>
        <section class="form-section field-span-full">
          <h3>{html.escape(t(lang, "group_details") if (is_non_scout_group or is_slovenia_other_group) else t(lang, "taborniki_unit_details") if is_slovenia_zts_group else t(lang, "scout_unit_details"))}</h3>
          <div class="form-section-grid">
            {'<input type="hidden" name="organization_name" value="' + html.escape(fields['organization_name']) + '">' if (is_non_scout_group or is_slovenia_other_group) else f'''
            <label class="field-span-full">
              {html.escape(t(lang, "national_scout_organization"))}
              <input type="text" name="organization_name" value="{html.escape(fields['organization_name'])}" required>
            </label>
            '''}
            <label class="field-span-full">
              {html.escape(t(lang, "group_name_label") if (is_non_scout_group or is_slovenia_other_group) else t(lang, "local_taborniki_unit") if is_slovenia_zts_group else t(lang, "local_scout_unit"))}
              <input type="text" name="group_name" value="{html.escape(fields['group_name'])}" required>
            </label>
            <label class="field-span-2">
              {html.escape(t(lang, "street_label"))}
              <input type="text" name="group_street" value="{html.escape(fields['group_street'])}" required>
            </label>
            <label class="field-span-2">
              {html.escape(t(lang, "house_number_label"))}
              <input type="text" name="group_house_number" value="{html.escape(fields['group_house_number'])}" required>
            </label>
            <label class="field-span-2">
              {html.escape(t(lang, "post_code_label"))}
              <input type="text" name="group_post_code" value="{html.escape(fields['group_post_code'])}" class="slovenia-postcode-input" list="slovenia-postcode-options" autocomplete="off" required>
              <datalist id="slovenia-postcode-options"></datalist>
            </label>
            <label class="field-span-2">
              {html.escape(t(lang, "town_label"))}
              <input type="text" name="group_town" value="{html.escape(fields['group_town'])}" class="slovenia-town-input" list="slovenia-town-options" autocomplete="off" required>
              <datalist id="slovenia-town-options"></datalist>
            </label>
            <label class="field-span-2">
              {html.escape(t(lang, "country_label"))}
              {render_country_input(fields['country'])}
            </label>
            <label class="field-span-2">
              {html.escape(t(lang, "vat_number_label"))}
              <small>{html.escape(t(lang, "vat_number_note") if is_slovenia_country(fields["origin_country"]) else t(lang, "vat_number_foreign_note"))}</small>
              <input type="text" name="vat_number" value="{html.escape(fields['vat_number'])}" required>
            </label>
          </div>
        </section>
        <section class="form-section field-span-full">
          <h3>{html.escape(t(lang, "other_information"))}</h3>
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
        {render_step_actions_form("/type", f'<button type="submit" class="section-submit">{html.escape(t(lang, "continue_to_contact"))}</button>', lang, reset_href)}
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
        const syncCountToggle = (input) => {{
          const row = input.closest('.section-row');
          const toggle = row ? row.querySelector('.section-toggle') : null;
          if (!toggle) {{
            return;
          }}
          const count = Math.max(0, parseInt(input.value || '0', 10) || 0);
          toggle.checked = count > 0;
        }};
        const sync = () => {{
          let adultTotal = 0;
          let childTotal = 0;
          counts.forEach((input) => {{
            const row = input.closest('.section-row');
            const checked = row && row.querySelector('.section-toggle')?.checked;
            const count = Math.max(0, parseInt(input.value || '0', 10) || 0);
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
        counts.forEach((input) => input.addEventListener('input', () => {{
          syncCountToggle(input);
          sync();
        }}));
        sync();

        const countryInput = form.querySelector('input[name="country"]');
        const postcodeInput = form.querySelector('input[name="group_post_code"]');
        const townInput = form.querySelector('input[name="group_town"]');
        const postcodeList = form.querySelector('#slovenia-postcode-options');
        const townList = form.querySelector('#slovenia-town-options');
        const sloveniaAddressRows = {json.dumps(SLOVENIA_POSTCODE_ROWS, ensure_ascii=False)};
        const normalizeValue = (value) => (value || '').trim().toLowerCase();
        const isSloveniaSelected = () => {{
          const value = normalizeValue(countryInput ? countryInput.value : '');
          return value === 'slovenia' || value === 'slovenija';
        }};
        const fillList = (datalist, values) => {{
          if (!datalist) return;
          datalist.innerHTML = '';
          values.forEach((value) => {{
            const option = document.createElement('option');
            option.value = value;
            datalist.appendChild(option);
          }});
        }};
        const uniqueSorted = (values) => Array.from(new Set(values)).sort((a, b) => a.localeCompare(b, 'sl'));
        const syncSloveniaSuggestions = () => {{
          if (!countryInput || !postcodeInput || !townInput || !postcodeList || !townList) {{
            return;
          }}
          if (!isSloveniaSelected()) {{
            fillList(postcodeList, []);
            fillList(townList, []);
            return;
          }}
          const postcodeQuery = normalizeValue(postcodeInput.value);
          const townQuery = normalizeValue(townInput.value);
          const postcodeMatches = uniqueSorted(
            sloveniaAddressRows
              .filter((row) => !postcodeQuery || row.postcode.toLowerCase().includes(postcodeQuery))
              .map((row) => row.postcode)
          ).slice(0, 50);
          const townMatches = uniqueSorted(
            sloveniaAddressRows
              .filter((row) => !townQuery || row.town.toLowerCase().includes(townQuery))
              .map((row) => row.town)
          ).slice(0, 50);
          fillList(postcodeList, postcodeMatches);
          fillList(townList, townMatches);
        }};
        const autofillFromPostcode = () => {{
          if (!isSloveniaSelected()) return;
          const value = postcodeInput.value.trim();
          if (!value) return;
          const towns = uniqueSorted(sloveniaAddressRows.filter((row) => row.postcode === value).map((row) => row.town));
          if (towns.length === 1) {{
            townInput.value = towns[0];
          }}
          syncSloveniaSuggestions();
        }};
        const autofillFromTown = () => {{
          if (!isSloveniaSelected()) return;
          const value = normalizeValue(townInput.value);
          if (!value) return;
          const postcodes = uniqueSorted(sloveniaAddressRows.filter((row) => row.town.toLowerCase() === value).map((row) => row.postcode));
          if (postcodes.length === 1) {{
            postcodeInput.value = postcodes[0];
          }}
          syncSloveniaSuggestions();
        }};
        const openDatalist = (input) => {{
          if (!input || typeof input.showPicker !== 'function') return;
          requestAnimationFrame(() => {{
            try {{
              input.showPicker();
            }} catch (error) {{
            }}
          }});
        }};
        if (countryInput && postcodeInput && townInput) {{
          countryInput.addEventListener('input', syncSloveniaSuggestions);
          countryInput.addEventListener('change', syncSloveniaSuggestions);
          postcodeInput.addEventListener('input', syncSloveniaSuggestions);
          postcodeInput.addEventListener('change', autofillFromPostcode);
          postcodeInput.addEventListener('focus', () => {{
            syncSloveniaSuggestions();
            if (isSloveniaSelected()) openDatalist(postcodeInput);
          }});
          postcodeInput.addEventListener('click', () => {{
            syncSloveniaSuggestions();
            if (isSloveniaSelected()) openDatalist(postcodeInput);
          }});
          townInput.addEventListener('input', syncSloveniaSuggestions);
          townInput.addEventListener('change', autofillFromTown);
          townInput.addEventListener('focus', () => {{
            syncSloveniaSuggestions();
            if (isSloveniaSelected()) openDatalist(townInput);
          }});
          townInput.addEventListener('click', () => {{
            syncSloveniaSuggestions();
            if (isSloveniaSelected()) openDatalist(townInput);
          }});
          if (isSloveniaSelected()) {{
            autofillFromPostcode();
            autofillFromTown();
          }} else {{
            syncSloveniaSuggestions();
          }}
        }}
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

    availability = {}
    try:
        availability = get_rental_availability(
            connection,
            parse_date(params.get("check_in", "")),
            parse_date(params.get("check_out", "")),
        )
    except ValueError:
        availability = {}

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
    total_nights = 1
    stay_dates = []
    try:
        stay_start = parse_date(params.get("check_in", ""))
        stay_end = parse_date(params.get("check_out", ""))
        total_nights = max(1, nights_between(stay_start, stay_end))
        stay_dates = list(daterange(stay_start, stay_end))
    except Exception:
        total_nights = 1
        stay_dates = []
    rental_items = get_rental_items_for_location(unit["location_name"])
    rental_rows_html = "".join(
        render_rental_item_row(item, params, lang, admin_mode, return_to, stay_dates, availability.get(item["key"]), unit["location_name"])
        for item in rental_items
    )
    reset_href = build_reset_href("rental", "/rental", params)

    content = f"""
    {render_reservation_steps("Rental", lang)}
    {error_html}
    <section class="panel">
      <h2>{html.escape(display_location_with_unit(unit['location_name'], unit['unit_name'], lang))}</h2>
      <p>{html.escape(t(lang, "stay"))}: {html.escape(format_stay_range(lang, params.get("check_in", ""), params.get("check_out", "")))}</p>
      <p>{html.escape(t(lang, "guests"))}: {html.escape(params.get("guest_count", ""))}</p>
    </section>
      <section class="panel">
        <form method="get" action="/book" class="booking-form">
        {hidden_html}
        <input type="hidden" name="admin_mode" value="{'1' if admin_mode else ''}">
        <section class="form-section field-span-full">
          <h3>{html.escape(t(lang, "rental_heading"))}</h3>
            <div class="rental-list">
              {rental_rows_html}
            </div>
            <label class="field-span-full">
              {html.escape(t(lang, "rental_comments_label"))}
              <small>{html.escape(t(lang, "rental_comments_help"))}</small>
              <textarea name="rental_comments" rows="4">{html.escape(params.get("rental_comments", ""))}</textarea>
            </label>
          </section>
        {render_step_actions_form("/contact", f'<button type="submit">{html.escape(t(lang, "continue_to_summary"))}</button>', lang, reset_href)}
      </form>
    </section>
    <script>
    (() => {{
        const wraps = document.querySelectorAll('.rental-item-wrap');
      wraps.forEach((wrap) => {{
        const row = wrap.querySelector('.rental-row');
        if (!row) return;
        const qty = row.querySelector('.rental-qty');
        const yes = row.querySelector('input[type="radio"][value="yes"]');
        const no = row.querySelector('input[type="radio"][value="no"]');
        const zeroOption = qty ? qty.querySelector('.rental-zero-option') : null;
        const extraInputs = wrap.querySelectorAll('.rental-extra-input');
        const extras = wrap.querySelectorAll('.rental-extra');
        const selectedDatesInput = wrap.querySelector('.rental-selected-dates');
        const dateButtons = wrap.querySelectorAll('.rental-date-button');
        const daysCount = row.querySelector('.rental-days-count');
        const decideLaterToggle = wrap.querySelector('.rental-decide-later-toggle');
        if (!qty || !yes || !no) return;
        const updateDaysCount = () => {{
          if (!selectedDatesInput || !daysCount) return;
          if (selectedDatesInput.value === '__later__') {{
            daysCount.textContent = %RENTAL_DATE_LATER%;
            return;
          }}
          const count = selectedDatesInput.value
            ? selectedDatesInput.value.split(',').filter(Boolean).length
            : 0;
          daysCount.textContent = count === 1
            ? %RENTAL_DAY_COUNT%.replace('{{count}}', String(count))
            : %RENTAL_DAYS_COUNT%.replace('{{count}}', String(count));
        }};
        const sync = () => {{
          const enabled = yes.checked;
          extras.forEach((extra) => {{
            extra.hidden = !enabled;
          }});
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
          dateButtons.forEach((button) => {{
            button.disabled = !enabled;
            if (!enabled) {{
              button.classList.remove('is-selected');
            }}
          }});
          if (decideLaterToggle) {{
            decideLaterToggle.disabled = !enabled;
            if (!enabled) {{
              decideLaterToggle.checked = false;
            }}
          }}
          if (selectedDatesInput) {{
            if (!enabled) {{
              selectedDatesInput.value = '';
            }}
            updateDaysCount();
          }}
        }};
        yes.addEventListener('change', sync);
        no.addEventListener('change', sync);
        qty.addEventListener('change', sync);
        dateButtons.forEach((button) => {{
          button.addEventListener('click', () => {{
            if (button.disabled || !selectedDatesInput) return;
            if (decideLaterToggle) {{
              decideLaterToggle.checked = false;
            }}
            const current = selectedDatesInput.value
              ? selectedDatesInput.value.split(',').filter((value) => value && value !== '__later__')
              : [];
            const dateValue = button.getAttribute('data-date');
            const exists = current.includes(dateValue);
            const next = exists
              ? current.filter((value) => value !== dateValue)
              : current.concat([dateValue]).sort();
            selectedDatesInput.value = next.join(',');
            button.classList.toggle('is-selected', !exists);
            updateDaysCount();
          }});
        }});
        if (decideLaterToggle) {{
          decideLaterToggle.addEventListener('change', () => {{
            if (!selectedDatesInput) return;
            if (decideLaterToggle.checked) {{
              selectedDatesInput.value = '__later__';
              dateButtons.forEach((button) => button.classList.remove('is-selected'));
            }} else if (selectedDatesInput.value === '__later__') {{
              selectedDatesInput.value = '';
            }}
            updateDaysCount();
          }});
        }}
        sync();
      }});
    }})();
    </script>
    """
    content = content.replace("%RENTAL_DATE_LATER%", "'" + t(lang, "rental_date_later").replace("'", "\\'") + "'")
    content = content.replace("%RENTAL_DAY_COUNT%", "'" + t(lang, "rental_day_count").replace("'", "\\'") + "'")
    content = content.replace("%RENTAL_DAYS_COUNT%", "'" + t(lang, "rental_days_count").replace("'", "\\'") + "'")
    return render_layout(t(lang, "rental"), content, lang=lang, current_path="/rental", current_params=params, is_admin=admin_mode)


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
        if key not in CONTACT_RESET_KEYS
    )
    error_html = ""
    if errors:
        items = "".join(f"<li>{html.escape(error)}</li>" for error in errors)
        error_html = f'<section class="panel error"><ul>{items}</ul></section>'
    is_non_scout_group = params.get("laski_group_type", "") == "non_scouts"
    is_slovenia_other_group = is_slovenia_country(params.get("origin_country", "")) and params.get("member_category", "") == "other"
    leader_label = contact_leader_label(lang, is_non_scout_group or is_slovenia_other_group)
    leader_label_lower = leader_label.lower()
    unit_leader_first_name, unit_leader_last_name = split_contact_name(params.get("unit_leader_name", ""))
    contact_person_first_name, contact_person_last_name = split_contact_name(params.get("contact_person_name", ""))
    contact_same_checked = params.get("contact_same_as_unit_leader") == "on"
    unit_leader_values = {
        "first_name": params.get("unit_leader_first_name", unit_leader_first_name),
        "last_name": params.get("unit_leader_last_name", unit_leader_last_name),
        "street": params.get("unit_leader_street", params.get("unit_leader_address", "")),
        "house_number": params.get("unit_leader_house_number", ""),
        "post_code": params.get("unit_leader_post_code", ""),
        "town": params.get("unit_leader_town", ""),
    }
    contact_person_values = {
        "first_name": params.get("contact_person_first_name", contact_person_first_name),
        "last_name": params.get("contact_person_last_name", contact_person_last_name),
        "street": params.get("contact_person_street", params.get("contact_person_address", "")),
        "house_number": params.get("contact_person_house_number", ""),
        "post_code": params.get("contact_person_post_code", ""),
        "town": params.get("contact_person_town", ""),
    }
    show_international_commissioner = not (is_non_scout_group or is_slovenia_other_group)
    international_commissioner_html = "" if not show_international_commissioner else f"""
              <section class="contact-group">
                <div class="form-section-grid">
                  <label class="field-span-full">
                    {html.escape(t(lang, "international_commissioner_name"))}
                    <input type="text" name="international_commissioner_name" value="{html.escape(params.get('international_commissioner_name', ''))}">
                  </label>
                  <label class="field-span-2">
                    {html.escape(t(lang, "international_commissioner_address"))}
                    <input type="text" name="international_commissioner_address" value="{html.escape(params.get('international_commissioner_address', ''))}">
                  </label>
                  <label class="field-span-2">
                    {html.escape(t(lang, "international_commissioner_email"))}
                    <input type="email" name="international_commissioner_email" value="{html.escape(params.get('international_commissioner_email', ''))}">
                  </label>
                  <label class="field-span-full">
                    {html.escape(t(lang, "international_commissioner_phone"))}
                    <small>{html.escape(t(lang, "phone_country_code_note"))}</small>
                    <input type="text" name="international_commissioner_phone" value="{html.escape(params.get('international_commissioner_phone', ''))}">
                  </label>
                </div>
              </section>
    """
    reset_href = build_reset_href("contact", "/contact", params)
    content = f"""
    {render_reservation_steps("Contact details", lang)}
    {error_html}
    <section class="panel">
      <h2>{html.escape(display_location_with_unit(unit['location_name'], unit['unit_name'], lang))}</h2>
      <p>{html.escape(t(lang, "stay"))}: {html.escape(format_stay_range(lang, params.get("check_in", ""), params.get("check_out", "")))}</p>
      <p>{html.escape(t(lang, "guests"))}: {html.escape(params.get("guest_count", ""))}</p>
    </section>
    <section class="panel">
      <form method="get" action="/rental" class="booking-form">
        {hidden_html}
          <section class="form-section field-span-full">
            <h3>{html.escape(t(lang, "contact_details"))}</h3>
            <div class="contact-groups">
              <section class="contact-group">
                <h4>{html.escape(tf(lang, "contact_leader_section", label=leader_label_lower))}</h4>
                <div class="form-section-grid">
                  <label class="field-span-2">
                    {html.escape(t(lang, "first_name_label"))}
                    <input type="text" name="unit_leader_first_name" value="{html.escape(unit_leader_values['first_name'])}" required>
                  </label>
                  <label class="field-span-2">
                    {html.escape(t(lang, "surname_label"))}
                    <input type="text" name="unit_leader_last_name" value="{html.escape(unit_leader_values['last_name'])}" required>
                  </label>
                  <label class="field-span-2">
                    {html.escape(t(lang, "street_label"))}
                    <input type="text" name="unit_leader_street" value="{html.escape(unit_leader_values['street'])}" required>
                  </label>
                  <label class="field-span-2">
                    {html.escape(t(lang, "house_number_label"))}
                    <input type="text" name="unit_leader_house_number" value="{html.escape(unit_leader_values['house_number'])}" required>
                  </label>
                  <label class="field-span-2">
                    {html.escape(t(lang, "post_code_label"))}
                    <input type="text" name="unit_leader_post_code" value="{html.escape(unit_leader_values['post_code'])}" required>
                  </label>
                  <label class="field-span-2">
                    {html.escape(t(lang, "town_label"))}
                    <input type="text" name="unit_leader_town" value="{html.escape(unit_leader_values['town'])}" required>
                  </label>
                  <label class="field-span-2">
                    {html.escape(tf(lang, "contact_email", label=leader_label))}
                    <input type="email" name="unit_leader_email" value="{html.escape(params.get('unit_leader_email', ''))}" required>
                  </label>
                  <label class="field-span-2">
                    {html.escape(t(lang, "contact_phone"))}
                    <small>{html.escape(t(lang, "phone_country_code_note"))}</small>
                    <input type="text" name="unit_leader_phone" value="{html.escape(params.get('unit_leader_phone', ''))}" required>
                  </label>
                </div>
              </section>
              <section class="contact-group">
                <h4>{html.escape(t(lang, "contact_person_name").split(":", 1)[0])}</h4>
                <label class="field-span-full checkbox contact-same-toggle">
                  <input type="checkbox" name="contact_same_as_unit_leader" {"checked" if contact_same_checked else ""}>
                  {html.escape(tf(lang, "contact_same_as", label=leader_label_lower))}
                </label>
                <div class="form-section-grid">
                  <label class="field-span-2">
                    {html.escape(t(lang, "first_name_label"))}
                    <input type="text" name="contact_person_first_name" class="contact-person-field" value="{html.escape(contact_person_values['first_name'])}" required>
                  </label>
                  <label class="field-span-2">
                    {html.escape(t(lang, "surname_label"))}
                    <input type="text" name="contact_person_last_name" class="contact-person-field" value="{html.escape(contact_person_values['last_name'])}" required>
                  </label>
                  <label class="field-span-2">
                    {html.escape(t(lang, "street_label"))}
                    <input type="text" name="contact_person_street" class="contact-person-field" value="{html.escape(contact_person_values['street'])}" required>
                  </label>
                  <label class="field-span-2">
                    {html.escape(t(lang, "house_number_label"))}
                    <input type="text" name="contact_person_house_number" class="contact-person-field" value="{html.escape(contact_person_values['house_number'])}" required>
                  </label>
                  <label class="field-span-2">
                    {html.escape(t(lang, "post_code_label"))}
                    <input type="text" name="contact_person_post_code" class="contact-person-field" value="{html.escape(contact_person_values['post_code'])}" required>
                  </label>
                  <label class="field-span-2">
                    {html.escape(t(lang, "town_label"))}
                    <input type="text" name="contact_person_town" class="contact-person-field" value="{html.escape(contact_person_values['town'])}" required>
                  </label>
                  <label class="field-span-2">
                    {html.escape(t(lang, "contact_person_email"))}
                    <input type="email" name="contact_person_email" class="contact-person-field" value="{html.escape(params.get('contact_person_email', ''))}" required>
                  </label>
                  <label class="field-span-2">
                    {html.escape(t(lang, "contact_phone"))}
                    <small>{html.escape(t(lang, "phone_country_code_note"))}</small>
                    <input type="text" name="contact_person_phone" class="contact-person-field" value="{html.escape(params.get('contact_person_phone', ''))}" required>
                  </label>
                </div>
              </section>
              {international_commissioner_html}
            </div>
          </section>
          {render_step_actions_form("/details", f'<button type="submit">{html.escape(t(lang, "continue_to_rental"))}</button>', lang, reset_href)}
        </form>
      </section>
      <script>
      (() => {{
        const same = document.querySelector('input[type="checkbox"][name="contact_same_as_unit_leader"]');
        if (!same) return;
        const form = same.closest('form');
        if (!form) return;
        const mappings = [
          ['unit_leader_first_name', 'contact_person_first_name'],
          ['unit_leader_last_name', 'contact_person_last_name'],
          ['unit_leader_street', 'contact_person_street'],
          ['unit_leader_house_number', 'contact_person_house_number'],
          ['unit_leader_post_code', 'contact_person_post_code'],
          ['unit_leader_town', 'contact_person_town'],
          ['unit_leader_email', 'contact_person_email'],
          ['unit_leader_phone', 'contact_person_phone'],
        ];
        const contactFields = form.querySelectorAll('.contact-person-field');
        const getField = (name) => {{
          const fields = Array.from(form.querySelectorAll('[name="' + name + '"]'));
          return fields.find((field) => field.type !== 'hidden') || fields[0] || null;
        }};
        const sync = () => {{
          const enabled = same.checked;
          mappings.forEach(([sourceName, targetName]) => {{
            const source = getField(sourceName);
            const target = getField(targetName);
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
        same.addEventListener('click', sync);
        mappings.forEach(([sourceName]) => {{
          const source = getField(sourceName);
          if (!source) return;
          source.addEventListener('input', sync);
          source.addEventListener('change', sync);
        }});
        sync();
      }})();
      </script>
      """
    return render_layout("Contact details", content, lang=lang, current_path="/contact", current_params=params)


def html_response(body, status="200 OK", content_type="text/html; charset=utf-8"):
    encoded = body.encode("utf-8")
    return status, [("Content-Type", content_type), ("Content-Length", str(len(encoded)))], [encoded]


def json_response(payload, status="200 OK"):
    body = json.dumps(payload).encode("utf-8")
    return status, [("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(body)))], [body]


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
      <h2>{html.escape(t(lang, "admin_login_title"))}</h2>
      <form method="post" action="/admin-login" class="booking-form">
        <input type="hidden" name="lang" value="{lang}">
        <label>
          {html.escape(t(lang, "username"))}
          <input type="text" name="username" required>
        </label>
        <label>
          {html.escape(t(lang, "password"))}
          <input type="password" name="password" required>
        </label>
        <button type="submit">{html.escape(t(lang, "unlock_media_tools"))}</button>
      </form>
    </section>
    """
    return render_layout(t(lang, "admin_login_title"), content, lang=lang, current_path="/admin-login", current_params={"lang": lang})


def render_booking_submitted_page(lang="en", email_sent=True):
    content = f"""
    <section class="panel">
      <h2>{html.escape(t(lang, "booking_submitted"))}</h2>
      <p>{html.escape(t(lang, "booking_submitted_text"))}</p>
      <p>{html.escape(t(lang, "booking_email_sent" if email_sent else "booking_email_not_sent"))}</p>
      <p><a class="button" href="/?lang={lang}">{html.escape(t(lang, "information"))}</a></p>
    </section>
    """
    return render_layout(t(lang, "booking_submitted"), content, lang=lang, current_path="/booking-submitted", current_params={"lang": lang})


def render_upload_form(lang, target_type, location_name, unit_name, label, extra_class="", return_to="/"):
    upload_anchor = upload_anchor_for_target(target_type, location_name, unit_name)
    anchored_return_to = return_to if "#" in return_to else f"{return_to}#{upload_anchor}"
    return f"""
    <form method="post" action="/upload-image" enctype="multipart/form-data" class="upload-form {extra_class} drop-upload" id="{html.escape(upload_anchor)}">
      <input type="hidden" name="lang" value="{lang}">
      <input type="hidden" name="return_to" value="{html.escape(anchored_return_to)}">
      <input type="hidden" name="target_type" value="{target_type}">
      <input type="hidden" name="location_name" value="{html.escape(location_name)}">
      <input type="hidden" name="unit_name" value="{html.escape(unit_name)}">
      <label class="drop-zone">
        <span>{html.escape(label)}</span>
        <small>{html.escape(t(lang, "upload_drop_hint"))}</small>
        <input type="file" name="image" accept=".jpg,.jpeg,.png,.webp,.svg" multiple required>
      </label>
      <button type="submit">{html.escape(t(lang, "upload_button"))}</button>
    </form>
    """


def render_gallery_admin_controls(lang, target_type, location_name, unit_name, image, return_to="/"):
    upload_anchor = upload_anchor_for_target(target_type, location_name, unit_name)
    anchored_return_to = return_to if "#" in return_to else f"{return_to}#{upload_anchor}"
    return f"""
    <div class="gallery-admin">
      <div class="gallery-order-actions">
        <form method="post" action="/make-primary-image" class="gallery-admin-form">
          <input type="hidden" name="lang" value="{lang}">
          <input type="hidden" name="return_to" value="{html.escape(anchored_return_to)}">
          <input type="hidden" name="target_type" value="{target_type}">
          <input type="hidden" name="location_name" value="{html.escape(location_name)}">
          <input type="hidden" name="unit_name" value="{html.escape(unit_name)}">
          <input type="hidden" name="filename" value="{html.escape(image['filename'])}">
          <button type="submit" class="button-secondary">{html.escape(t(lang, "make_first_picture"))}</button>
        </form>
        <form method="post" action="/move-image" class="gallery-admin-form">
          <input type="hidden" name="lang" value="{lang}">
          <input type="hidden" name="return_to" value="{html.escape(anchored_return_to)}">
          <input type="hidden" name="target_type" value="{target_type}">
          <input type="hidden" name="location_name" value="{html.escape(location_name)}">
          <input type="hidden" name="unit_name" value="{html.escape(unit_name)}">
          <input type="hidden" name="filename" value="{html.escape(image['filename'])}">
          <input type="hidden" name="direction" value="back">
          <button type="submit" class="button-secondary">{html.escape(t(lang, "move_picture_back"))}</button>
        </form>
        <form method="post" action="/move-image" class="gallery-admin-form">
          <input type="hidden" name="lang" value="{lang}">
          <input type="hidden" name="return_to" value="{html.escape(anchored_return_to)}">
          <input type="hidden" name="target_type" value="{target_type}">
          <input type="hidden" name="location_name" value="{html.escape(location_name)}">
          <input type="hidden" name="unit_name" value="{html.escape(unit_name)}">
          <input type="hidden" name="filename" value="{html.escape(image['filename'])}">
          <input type="hidden" name="direction" value="forward">
          <button type="submit" class="button-secondary">{html.escape(t(lang, "move_picture_forward"))}</button>
        </form>
      </div>
      <form method="post" action="/delete-image" class="gallery-admin-form">
        <input type="hidden" name="lang" value="{lang}">
        <input type="hidden" name="return_to" value="{html.escape(anchored_return_to)}">
        <input type="hidden" name="target_type" value="{target_type}">
        <input type="hidden" name="location_name" value="{html.escape(location_name)}">
        <input type="hidden" name="unit_name" value="{html.escape(unit_name)}">
        <input type="hidden" name="filename" value="{html.escape(image['filename'])}">
        <button type="submit" class="danger-button">Delete photo</button>
      </form>
    </div>
    """


def render_layout(
    title,
    content,
    notice="",
    lang="en",
    current_path="/",
    current_params=None,
    is_admin=False,
    head_extra="",
    body_extra="",
):
    current_params = dict(current_params or {})
    current_params.pop("lang", None)
    en_query = urlencode({"lang": "en", **current_params})
    sl_query = urlencode({"lang": "sl", **current_params})
    notice_html = f'<div class="notice">{html.escape(notice)}</div>' if notice else ""
    try:
        style_version = int(STYLE_CSS_PATH.stat().st_mtime)
    except OSError:
        style_version = 1
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="/static/style.css?v={style_version}">
  {head_extra}
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
        <a href="/?lang={lang}">{html.escape(t(lang, "information"))}</a>
        <a href="/period?lang={lang}">{html.escape(t(lang, "period"))}</a>
        {f'<a href="/admin?lang={lang}">{html.escape(t(lang, "admin"))}</a><form method="post" action="/admin-logout" class="inline-form inline-form--header"><input type="hidden" name="lang" value="{lang}"><button type="submit">{html.escape(t(lang, "media_logout"))}</button></form>' if is_admin else ''}
      </nav>
    </div>
  </header>
  <main>
    {notice_html}
    {content}
  </main>
  <div class="image-lightbox" hidden>
    <button type="button" class="image-lightbox-close" aria-label="Close">x</button>
    <button type="button" class="image-lightbox-nav image-lightbox-prev" aria-label="Previous picture">&lt;</button>
    <img src="" alt="">
    <button type="button" class="image-lightbox-nav image-lightbox-next" aria-label="Next picture">&gt;</button>
  </div>
  <script>
  (() => {{
    const lightbox = document.querySelector('.image-lightbox');
    if (!lightbox) return;
    const image = lightbox.querySelector('img');
    const closeButton = lightbox.querySelector('.image-lightbox-close');
    const previousButton = lightbox.querySelector('.image-lightbox-prev');
    const nextButton = lightbox.querySelector('.image-lightbox-next');
    let galleryImages = [];
    let activeIndex = 0;
    const showImage = (index) => {{
      if (!galleryImages.length) return;
      activeIndex = (index + galleryImages.length) % galleryImages.length;
      const sourceImage = galleryImages[activeIndex];
      image.src = sourceImage.currentSrc || sourceImage.src;
      image.alt = sourceImage.alt || '';
      const hasMultiple = galleryImages.length > 1;
      previousButton.hidden = !hasMultiple;
      nextButton.hidden = !hasMultiple;
    }};
    const openLightbox = (sourceImage) => {{
      const galleryRoot = sourceImage.closest('.location-gallery, .unit-gallery, .rental-gallery-admin') || document;
      galleryImages = Array.from(galleryRoot.querySelectorAll('.location-image, .gallery-thumb, .rental-item-image'));
      activeIndex = Math.max(0, galleryImages.indexOf(sourceImage));
      showImage(activeIndex);
      lightbox.hidden = false;
      document.body.classList.add('image-lightbox-open');
    }};
    const closeLightbox = () => {{
      lightbox.hidden = true;
      document.body.classList.remove('image-lightbox-open');
      image.src = '';
      galleryImages = [];
    }};
    document.querySelectorAll('.location-image, .gallery-thumb, .rental-item-image').forEach((galleryImage) => {{
      galleryImage.classList.add('is-lightbox-image');
      galleryImage.addEventListener('click', (event) => {{
        event.preventDefault();
        event.stopPropagation();
        openLightbox(galleryImage);
      }});
    }});
    closeButton.addEventListener('click', closeLightbox);
    previousButton.addEventListener('click', () => showImage(activeIndex - 1));
    nextButton.addEventListener('click', () => showImage(activeIndex + 1));
    lightbox.addEventListener('click', (event) => {{
      if (event.target === lightbox) closeLightbox();
    }});
    document.addEventListener('keydown', (event) => {{
      if (lightbox.hidden) return;
      if (event.key === 'Escape') closeLightbox();
      if (event.key === 'ArrowLeft') showImage(activeIndex - 1);
      if (event.key === 'ArrowRight') showImage(activeIndex + 1);
    }});
    const query = new URLSearchParams(window.location.search);
    if (query.get('open_upload') === '1' && window.location.hash) {{
      const uploadForm = document.getElementById(decodeURIComponent(window.location.hash.slice(1)));
      const uploadInput = uploadForm ? uploadForm.querySelector('input[type="file"]') : null;
      const uploadZone = uploadForm ? uploadForm.querySelector('.drop-zone') : null;
      if (uploadZone) {{
        uploadZone.classList.add('is-dragover');
        uploadZone.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
        setTimeout(() => uploadZone.classList.remove('is-dragover'), 1800);
      }}
      if (uploadInput) {{
        uploadInput.focus();
        try {{
          if (typeof uploadInput.showPicker === 'function') {{
            uploadInput.showPicker();
          }} else {{
            uploadInput.click();
          }}
        }} catch (error) {{}}
      }}
    }}
  }})();
  </script>
  {body_extra}
</body>
</html>
"""


INFO_MAP_LOCATIONS = [
    ("Laski rovt ZTS", 46.267851, 13.894797, True),
    ("Laski rovt ZR", 46.267620, 13.895770, True),
    ("Laski rovt MB", 46.267708, 13.892434, True),
    ("Taborni prostor Ukanc", 46.280863, 13.850101, True),
    ("Gozdna sola Ukanc", 46.280293, 13.850284, True),
    ("Taborni prostor Baredi", 45.517479, 13.683167, False),
    ("Taborni prostor Radlje ob Dravi", 46.602909, 15.220587, False),
]


def render_info_map_section(lang):
    locations_json = json.dumps(
        [
            {
                "name": display_location_name(location_name, lang),
                "summary": get_location_content(location_name, lang).get("summary", ""),
                "highlights": get_location_content(location_name, lang).get("highlights", []),
                "seasonLabel": t(lang, "location_season_label"),
                "season": get_location_content(location_name, lang).get("season", ""),
                "lat": lat,
                "lng": lng,
                "requiresZoom": requires_zoom,
            }
            for location_name, lat, lng, requires_zoom in INFO_MAP_LOCATIONS
        ],
        ensure_ascii=False,
    )
    return f"""
    <section class="panel info-map-panel">
      <div class="info-map-heading">
        <h2>{html.escape(t(lang, "info_map_heading"))}</h2>
        <p class="muted">{html.escape(t(lang, "info_map_text"))}</p>
      </div>
      <div id="slovenia-locations-map" class="info-map" data-locations='{html.escape(locations_json, quote=True)}'></div>
    </section>
    """


def render_info_map_assets():
    head_extra = """
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
"""
    body_extra = """
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
  (() => {
    const mapElement = document.getElementById('slovenia-locations-map');
    if (!mapElement || typeof L === 'undefined') return;

    const locations = JSON.parse(mapElement.dataset.locations || '[]');
    const sloveniaBounds = L.latLngBounds(
      [45.38, 13.33],
      [46.90, 16.62]
    );
    const map = L.map(mapElement, {
      scrollWheelZoom: true,
      zoomControl: true,
      maxBounds: sloveniaBounds.pad(0.28),
      maxBoundsViscosity: 0.65,
    });

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors',
    }).addTo(map);

    const closeLocationPopupZoom = 14;
    const escapeHtml = (value) => String(value || '').replace(/[&<>"']/g, (character) => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#039;',
    }[character]));
    const openLocationPopup = (marker, location) => {
      if (location.requiresZoom && map.getZoom() < closeLocationPopupZoom) return;
      marker.bindPopup(renderLocationPopup(location), getPopupPlacement(location));
      marker.openPopup();
    };
    const getPopupPlacement = (location) => {
      const mapSize = map.getSize();
      const markerPoint = map.latLngToContainerPoint([location.lat, location.lng]);
      const popupWidth = Math.min(360, Math.max(280, mapSize.x * 0.48));
      const popupHeight = 300;
      const markerGap = 42;
      const space = {
        top: markerPoint.y,
        right: mapSize.x - markerPoint.x,
        bottom: mapSize.y - markerPoint.y,
        left: markerPoint.x,
      };
      const side = [
        ['top', space.top - popupHeight],
        ['right', space.right - popupWidth],
        ['bottom', space.bottom - popupHeight],
        ['left', space.left - popupWidth],
      ].sort((a, b) => b[1] - a[1])[0][0];
      const placements = {
        top: { offset: [0, -markerGap], className: 'map-popup--top' },
        right: { offset: [Math.round(popupWidth / 2) + markerGap, 12], className: 'map-popup--right' },
        bottom: { offset: [0, popupHeight + markerGap], className: 'map-popup--bottom' },
        left: { offset: [-(Math.round(popupWidth / 2) + markerGap), 12], className: 'map-popup--left' },
      };
      return {
        closeButton: false,
        autoPan: false,
        maxWidth: popupWidth,
        ...placements[side],
      };
    };
    const renderLocationPopup = (location) => {
      const highlights = Array.isArray(location.highlights)
        ? location.highlights.map((item) => `<li>${escapeHtml(item)}</li>`).join('')
        : '';
      const season = location.season
        ? `<p class="map-popup-season"><strong>${escapeHtml(location.seasonLabel)}:</strong> ${escapeHtml(location.season)}</p>`
        : '';
      return `
        <article class="map-location-popup">
          <h3>${escapeHtml(location.name)}</h3>
          <p>${escapeHtml(location.summary)}</p>
          ${highlights ? `<ul>${highlights}</ul>` : ''}
          ${season}
        </article>
      `;
    };
    const bounds = [];
    locations.forEach((location) => {
      const marker = L.marker([location.lat, location.lng]).addTo(map);
      marker.bindTooltip(location.name, {
        direction: 'top',
        offset: [0, -10],
        opacity: 0.95,
        permanent: true,
      });
      marker.on('mouseover', () => openLocationPopup(marker, location));
      marker.on('focus', () => openLocationPopup(marker, location));
      marker.on('click', () => openLocationPopup(marker, location));
      marker.on('mouseout', () => marker.closePopup());
      marker.on('blur', () => marker.closePopup());
      bounds.push([location.lat, location.lng]);
    });

    map.fitBounds(sloveniaBounds, { padding: [22, 22] });
    setTimeout(() => map.invalidateSize(), 80);
  })();
  </script>
"""
    return head_extra, body_extra


def render_information_page(connection, params):
    lang = get_lang(params.get("lang", "en"))
    notice = params.get("notice", "")
    locations = fetch_locations(connection)
    place_cards = []
    for location in locations:
        content = get_location_content(location["name"], lang)
        highlights = "".join(f"<li>{html.escape(item)}</li>" for item in content.get("highlights", []))
        place_cards.append(
            f"""
            <article class="info-place-card">
              <h3>{html.escape(display_location_name(location["name"], lang))}</h3>
              <p>{html.escape(content.get("summary", ""))}</p>
              <ul>{highlights}</ul>
              <p class="muted"><strong>{html.escape(t(lang, "location_season_label"))}:</strong> {html.escape(content.get("season", ""))}</p>
            </article>
            """
        )
    content = f"""
    {render_steps("Information", lang)}
    <section class="panel info-hero">
      <p class="eyebrow">{html.escape(t(lang, "info_eyebrow"))}</p>
      <h2>{html.escape(t(lang, "info_title"))}</h2>
      <p>{html.escape(t(lang, "info_text"))}</p>
      <p><a class="button" href="/period?lang={lang}">{html.escape(t(lang, "info_continue"))}</a></p>
    </section>
    {render_info_map_section(lang)}
    <section class="panel">
      <h2>{html.escape(t(lang, "info_places_heading"))}</h2>
      <div class="info-place-grid">
        {''.join(place_cards)}
      </div>
    </section>
    <section class="panel info-documents">
      <h2>{html.escape(t(lang, "info_documents_heading"))}</h2>
      <div class="info-document-group">
        <h3>{html.escape(t(lang, "info_document_nature_heading"))}</h3>
        <div class="info-document-grid">
          <a href="/static/documents/zts-visiting-nature-in-slovenia.pdf" target="_blank" rel="noopener">{html.escape(t(lang, "info_document_nature_zts"))}</a>
          <a href="/static/documents/pzs-summer-mountaineering-safety-tips-eng.pdf" target="_blank" rel="noopener">{html.escape(t(lang, "info_document_nature_pzs"))}</a>
          <a href="/static/documents/triglav-national-park-map.pdf" target="_blank" rel="noopener">{html.escape(t(lang, "info_document_nature_tnp"))}</a>
        </div>
      </div>
      <div class="info-document-group">
        <h3>{html.escape(t(lang, "info_document_campsite_heading"))}</h3>
        <div class="info-document-grid">
          <a href="/static/documents/rules-tc-en-2024.pdf" target="_blank" rel="noopener">{html.escape(t(lang, "info_document_campsite_tc"))}</a>
          <a href="/static/documents/laski-rovt-campsite-rules-of-conduct.pdf" target="_blank" rel="noopener">{html.escape(t(lang, "info_document_campsite_laski"))}</a>
          <a href="/static/documents/rules-of-conduct-in-bohinj.pdf" target="_blank" rel="noopener">{html.escape(t(lang, "info_document_campsite_bohinj"))}</a>
        </div>
      </div>
      <div class="info-document-group">
        <h3>{html.escape(t(lang, "info_document_other_heading"))}</h3>
        <div class="info-document-grid info-document-grid--other">
          <a href="mailto:tc.bohinj@taborniki.si" onclick="alert('{html.escape(t(lang, "info_document_contact_notice"), quote=True)}')">{html.escape(t(lang, "info_document_contact"))}</a>
          <a href="/static/documents/ld-izola-program-ang.pdf" target="_blank" rel="noopener">{html.escape(t(lang, "info_document_other_izola"))}</a>
          <a href="/static/documents/list-of-participants-gs-zts.xlsx" target="_blank" rel="noopener">{html.escape(t(lang, "info_document_other_participants"))}</a>
          <a href="/static/documents/aa-sales-actions-scouts-en-2025.pdf" target="_blank" rel="noopener">{html.escape(t(lang, "info_document_other_sales"))}</a>
          <a href="/static/documents/what-to-do-in-and-around-radlje-ob-dravi.pdf" target="_blank" rel="noopener">{html.escape(t(lang, "info_document_other_radlje"))}</a>
        </div>
      </div>
      <p class="muted">{html.escape(t(lang, "info_document_note"))}</p>
    </section>
    """
    map_head_extra, map_body_extra = render_info_map_assets()
    return render_layout(
        t(lang, "information"),
        content,
        notice=notice,
        lang=lang,
        current_path="/",
        current_params=params,
        head_extra=map_head_extra,
        body_extra=map_body_extra,
    )


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
    locations = fetch_locations(connection)
    bookings = fetch_bookings(connection)
    total_units = sum(len(location["units"]) for location in locations)
    intro = f"""
    {render_steps("Period", lang)}
    <section class="panel landing-hero">
      <div class="landing-hero-copy">
        <p class="eyebrow">{html.escape(t(lang, "landing_eyebrow"))}</p>
        <h2>{html.escape(t(lang, "landing_title"))}</h2>
        <p>{html.escape(t(lang, "landing_text"))}</p>
        <p class="muted">{html.escape(t(lang, "choose_intro"))}</p>
      </div>
      <div class="landing-stats" aria-label="Overview">
        <article class="landing-stat">
          <strong>{len(locations)}</strong>
          <span>{html.escape(t(lang, "landing_stat_locations"))}</span>
        </article>
        <article class="landing-stat">
          <strong>{total_units}</strong>
          <span>{html.escape(t(lang, "landing_stat_units"))}</span>
        </article>
        <article class="landing-stat">
          <strong>{html.escape(t(lang, "landing_stat_groups_value"))}</strong>
          <span>{html.escape(t(lang, "landing_stat_groups"))}</span>
        </article>
      </div>
    </section>
    <div class="step-actions">
      <a class="button period-back-button" href="/?lang={lang}">{html.escape(t(lang, "back"))}</a>
    </div>
    """
    if error_html:
        intro += f'<section class="panel error"><ul>{error_html}</ul></section>'

    cards = []
    for location in locations:
        public_board_start = datetime.now().date().replace(day=1)
        public_board_end = datetime(public_board_start.year + 2, 1, 1).date()
        public_board_html = render_booking_board(
            [location],
            bookings,
            public_board_start,
            public_board_end,
            show_guest_names=False,
            heading_suffix="Availability by unit",
            css_class="public-board-section",
            empty_text="No reservations in this period.",
            compact=True,
        )
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
        lowest_price = min(unit["price_per_guest_per_night"] for unit in location["units"])
        location_content = get_location_content(location["name"], lang)
        highlights = location_content.get("highlights", [])
        summary_text = location_content.get("summary", "")
        season_text = location_content.get("season", "")
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
                        {render_gallery_admin_controls(lang, "location", location["name"], "", image, return_to=f"/period?lang={lang}&admin_mode=1") if admin_mode and image.get("filename") else ''}
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
                {render_gallery_admin_controls(lang, "location", location["name"], "", lead_image, return_to=f"/period?lang={lang}&admin_mode=1") if admin_mode and lead_image.get("filename") else ''}
            </div>
            """
        if admin_mode:
              gallery_html += render_upload_form(lang, "location", location["name"], "", f"Add picture for {display_location_name(location['name'], lang)}", return_to=f"/period?lang={lang}&admin_mode=1")
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
                                    {render_gallery_admin_controls(lang, "unit", location["name"], unit["name"], image, return_to=f"/period?lang={lang}&admin_mode=1") if admin_mode and image.get("filename") else ''}
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
                            {render_gallery_admin_controls(lang, "unit", location["name"], unit["name"], lead_image, return_to=f"/period?lang={lang}&admin_mode=1") if admin_mode and lead_image.get("filename") else ''}
                        </div>
                        """
                if admin_mode:
                    unit_gallery_html += render_upload_form(lang, "unit", location["name"], unit["name"], f"Add picture for {unit['name']}", extra_class="upload-form--unit", return_to=f"/period?lang={lang}&admin_mode=1")
                unit_summaries.append(
                    f"""
                    <article class="unit-card unit-card--summary">
                      <h3>{html.escape(display_unit_name(unit['name'], lang))}</h3>
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
            <section id="location-{location['id']}" class="panel{' panel--selected' if is_selected_location else ''} location-card">
              <div class="location-overview">
                <div class="location-overview-main">
                  <div class="location-heading">
                    <p class="location-type-pill">{html.escape(translate_location_type(location['type'], lang))}</p>
                    <h2>{html.escape(display_location_name(location['name'], lang))}</h2>
                  </div>
                  <p class="location-summary">{html.escape(summary_text)}</p>
                  <div class="location-meta">
                    <p><strong>{html.escape(t(lang, "location_capacity_label"))}:</strong> {location_capacity_total}</p>
                    <p><strong>{html.escape(format_location_units_available(lang, len(location["units"])))}</strong></p>
                    <p><strong>{html.escape(t(lang, "location_season_label"))}:</strong> {html.escape(season_text)}</p>
                    <p><strong>{html.escape(t(lang, "price"))}:</strong> {html.escape(tf(lang, "from_price", amount=f"{lowest_price:.2f}"))}</p>
                  </div>
                  {'<ul class="location-highlights">' + ''.join(f"<li>{html.escape(item)}</li>" for item in highlights) + '</ul>' if highlights else ''}
                </div>
                <div class="location-overview-media">
                  {gallery_html}
                </div>
              </div>
              {'<div class="unit-grid">' + ''.join(unit_summaries) + '</div>' if unit_summaries else ''}
              {public_board_html}
              <div class="booking-entry">
                <div class="booking-entry-head">
                  <h3>{html.escape(t(lang, "location_search_title"))}</h3>
                  <p class="muted">{html.escape(t(lang, "choose_intro"))}</p>
                </div>
                <form method="get" action="/type" class="search-form location-search-form" data-location-id="{location['id']}" data-location-name="{html.escape(location['name'])}" data-date-min="{location_min_date.isoformat() if location_min_date else ''}" data-date-max="{location_max_date.isoformat() if location_max_date else ''}" data-location-capacity="{location_capacity_total}">
                  <input type="hidden" name="location_id" value="{location['id']}">
                  <input type="hidden" name="lang" value="{lang}">
                  {preserved_search_hidden}
                  <label>
                    {html.escape(t(lang, "check_in"))}
                    <div class="checkout-picker checkin-picker">
                      <input type="hidden" name="check_in" class="stay-check-in" value="{html.escape(card_check_in)}" required>
                      <button type="button" class="checkout-trigger">{html.escape(card_check_in or t(lang, "check_in"))}</button>
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
                    <p class="stay-live-capacity">{html.escape(t(lang, "availability_choose_dates"))}</p>
                    <p class="stay-occupied-days" hidden style="display:none;"></p>
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
              </div>
            </section>
            """
        )
    script = """
    <script>
    (() => {
      const forms = document.querySelectorAll('.location-search-form');
      forms.forEach((form) => {
        const checkIn = form.querySelector('.stay-check-in');
        const checkInPicker = form.querySelector('.checkin-picker');
        const checkInTrigger = checkInPicker ? checkInPicker.querySelector('.checkout-trigger') : null;
        const checkInCalendar = checkInPicker ? checkInPicker.querySelector('.checkout-calendar') : null;
        const checkInMonth = checkInPicker ? checkInPicker.querySelector('.checkout-calendar-month') : null;
        const checkInDays = checkInPicker ? checkInPicker.querySelector('.checkout-calendar-days') : null;
        const checkInPrev = checkInPicker ? checkInPicker.querySelector('.calendar-prev') : null;
        const checkInNext = checkInPicker ? checkInPicker.querySelector('.calendar-next') : null;
        const checkOut = form.querySelector('.stay-check-out');
        const checkOutPicker = form.querySelector('.checkout-picker:not(.checkin-picker)');
        const checkOutTrigger = checkOutPicker ? checkOutPicker.querySelector('.checkout-trigger') : null;
        const checkOutCalendar = checkOutPicker ? checkOutPicker.querySelector('.checkout-calendar') : null;
        const checkOutMonth = checkOutPicker ? checkOutPicker.querySelector('.checkout-calendar-month') : null;
        const checkOutDays = checkOutPicker ? checkOutPicker.querySelector('.checkout-calendar-days') : null;
        const checkOutPrev = checkOutPicker ? checkOutPicker.querySelector('.calendar-prev') : null;
        const checkOutNext = checkOutPicker ? checkOutPicker.querySelector('.calendar-next') : null;
        const guestCountInput = form.querySelector('input[name="guest_count"]');
        const originCountryInput = form.querySelector('input[name="origin_country"]');
        const memberCategoryWrap = form.querySelector('.member-category-period');
        const memberCategorySelect = form.querySelector('.member-category-select');
        const continueButton = form.querySelector('button[type="submit"]');
        const output = form.querySelector('.stay-nights');
        const liveCapacity = form.querySelector('.stay-live-capacity');
        const occupiedDaysOutput = form.querySelector('.stay-occupied-days');
        const warning = form.querySelector('.stay-warning');
        const capacityWarning = form.querySelector('.stay-warning-capacity');
        const details = form.querySelector('.stay-details');
        const locationId = form.getAttribute('data-location-id') || '';
        const locationName = form.getAttribute('data-location-name') || '';
        const minDateValue = form.getAttribute('data-date-min') || '';
        const maxDateValue = form.getAttribute('data-date-max') || '';
        const locationCapacity = Number.parseInt(form.getAttribute('data-location-capacity') || '0', 10);
        let visibleCheckInMonthStart = null;
        let visibleMonthStart = null;
        let availabilityRequestId = 0;
        let calendarRequestId = 0;
        let latestRemainingCapacity = null;
        let calendarAvailability = new Map();
        let loadedCalendarMonths = new Set();
        const formatDate = (date) => {
          const year = date.getFullYear();
          const month = String(date.getMonth() + 1).padStart(2, '0');
          const day = String(date.getDate()).padStart(2, '0');
          return year + '-' + month + '-' + day;
        };
        const getMonthStart = (date) => new Date(date.getFullYear(), date.getMonth(), 1);
        const parseIsoDate = (value) => value ? new Date(value + 'T00:00:00') : null;
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const absoluteMinDate = parseIsoDate(minDateValue);
        const absoluteMaxDate = parseIsoDate(maxDateValue);
        const availabilityLoadingText = %AVAILABILITY_LOADING%;
        const availabilityChooseDatesText = %AVAILABILITY_CHOOSE_DATES%;
        const availabilityRemainingTemplate = %AVAILABILITY_REMAINING%;
        const availabilityFullText = %AVAILABILITY_FULL%;
        const availabilityPartialDaysTemplate = %AVAILABILITY_PARTIAL_DAYS%;
        const availabilityFullyOpenText = %AVAILABILITY_FULLY_OPEN%;
        const renderLocationTemplate = (template) => template.replace('{location}', locationName);
        const renderAvailabilityText = (count) => {
          if (count <= 0) {
            return availabilityFullText;
          }
          return availabilityRemainingTemplate.replace('{count}', String(count));
        };
        const monthKey = (date) => date.getFullYear() + '-' + String(date.getMonth() + 1).padStart(2, '0');
        const formatDayAvailabilityLabel = (dayData) => {
          return dayData.remaining_capacity + ' / ' + dayData.total_capacity;
        };
        const updateOccupiedDaysSummary = () => {
          if (!occupiedDaysOutput) {
            return;
          }
          if (!checkIn.value || !checkOut.value) {
            occupiedDaysOutput.textContent = '';
            occupiedDaysOutput.hidden = true;
            occupiedDaysOutput.style.display = 'none';
            return;
          }
          occupiedDaysOutput.hidden = false;
          occupiedDaysOutput.style.display = 'block';
          const start = parseIsoDate(checkIn.value);
          const end = parseIsoDate(checkOut.value);
          if (!start || !end || end <= start) {
            occupiedDaysOutput.textContent = '';
            occupiedDaysOutput.hidden = true;
            occupiedDaysOutput.style.display = 'none';
            return;
          }
          const occupied = [];
          const cursor = new Date(start);
          while (cursor < end) {
            const value = formatDate(cursor);
            const dayData = calendarAvailability.get(value);
            if (dayData && dayData.occupied) {
              occupied.push(value + ' (' + formatDayAvailabilityLabel(dayData) + ')');
            }
            cursor.setDate(cursor.getDate() + 1);
          }
          occupiedDaysOutput.textContent = occupied.length
            ? renderLocationTemplate(availabilityPartialDaysTemplate).replace('{days}', occupied.join(', '))
            : renderLocationTemplate(availabilityFullyOpenText);
        };
        const fetchCalendarAvailability = async (date) => {
          if (!locationId || !date) {
            return;
          }
          const key = monthKey(date);
          if (loadedCalendarMonths.has(key)) {
            return;
          }
          const currentRequestId = ++calendarRequestId;
          try {
            const response = await fetch('/api/location-calendar?location_id=' + encodeURIComponent(locationId) + '&month=' + encodeURIComponent(key));
            if (!response.ok) {
              throw new Error('calendar request failed');
            }
            const data = await response.json();
            if (currentRequestId !== calendarRequestId) {
              return;
            }
            loadedCalendarMonths.add(key);
            (data.days || []).forEach((day) => {
              calendarAvailability.set(day.date, day);
            });
            updateOccupiedDaysSummary();
            renderCheckInCalendar();
            renderCheckoutCalendar();
          } catch (error) {
            if (currentRequestId !== calendarRequestId) {
              return;
            }
          }
        };
        const updateCapacityWarning = () => {
          const guestCount = Number.parseInt(guestCountInput.value || '0', 10);
          const hardCapacityExceeded = Number.isFinite(locationCapacity) && locationCapacity > 0 && guestCount > locationCapacity;
          const liveCapacityExceeded = latestRemainingCapacity !== null && guestCount > latestRemainingCapacity;
          const exceeded = hardCapacityExceeded || liveCapacityExceeded;
          if (capacityWarning) {
            capacityWarning.hidden = !exceeded;
          }
          if (continueButton && checkIn.value && checkOut.value) {
            continueButton.disabled = exceeded;
          }
          return exceeded;
        };
        const fetchLiveAvailability = async () => {
          if (!checkIn.value || !checkOut.value || !locationId) {
            latestRemainingCapacity = null;
            if (liveCapacity) {
              liveCapacity.textContent = availabilityChooseDatesText;
            }
            updateCapacityWarning();
            return;
          }
          const currentRequestId = ++availabilityRequestId;
          if (liveCapacity) {
            liveCapacity.textContent = availabilityLoadingText;
          }
          try {
            const response = await fetch('/api/location-availability?location_id=' + encodeURIComponent(locationId) + '&check_in=' + encodeURIComponent(checkIn.value) + '&check_out=' + encodeURIComponent(checkOut.value));
            if (!response.ok) {
              throw new Error('availability request failed');
            }
            const data = await response.json();
            if (currentRequestId !== availabilityRequestId) {
              return;
            }
            latestRemainingCapacity = Number.parseInt(String(data.remaining_capacity || 0), 10);
            if (liveCapacity) {
              liveCapacity.textContent = renderAvailabilityText(latestRemainingCapacity);
            }
            updateCapacityWarning();
          } catch (error) {
            if (currentRequestId !== availabilityRequestId) {
              return;
            }
            latestRemainingCapacity = null;
            if (liveCapacity) {
              liveCapacity.textContent = availabilityChooseDatesText;
            }
            updateCapacityWarning();
          }
        };
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
          const effectiveMinDate = absoluteMinDate && absoluteMinDate > today
            ? new Date(absoluteMinDate)
            : new Date(today);
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
            const beforeMin = current < effectiveMinDate;
            const afterMax = absoluteMaxDate && current > absoluteMaxDate;
            const selected = value === checkIn.value;
            const classNames = ['calendar-day'];
            const dayData = calendarAvailability.get(value);
            if (beforeMin || afterMax) classNames.push('calendar-day--disabled');
            if (selected) classNames.push('calendar-day--selected');
            if (dayData && dayData.full) classNames.push('calendar-day--full');
            else if (dayData && dayData.occupied) classNames.push('calendar-day--occupied');
            const disabled = beforeMin || afterMax ? ' disabled' : '';
            const title = dayData ? ' title="' + value + ': ' + formatDayAvailabilityLabel(dayData) + ' places left"' : '';
            const helper = dayData ? '<span class="calendar-day-meta">' + dayData.remaining_capacity + '</span>' : '';
            dayCells.push('<button type="button" class="' + classNames.join(' ') + '" data-date="' + value + '"' + title + disabled + '><span class="calendar-day-number">' + day + '</span>' + helper + '</button>');
          }
          checkInMonth.textContent = new Intl.DateTimeFormat(%LOCALE%, { month: 'long', year: 'numeric' }).format(monthStart);
          checkInPrev.disabled = absoluteMinDate ? monthStart <= getMonthStart(absoluteMinDate) : false;
          checkInNext.disabled = absoluteMaxDate ? monthStart >= getMonthStart(absoluteMaxDate) : false;
          checkInDays.innerHTML = dayCells.join('');
          fetchCalendarAvailability(monthStart);
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
            const dayData = calendarAvailability.get(value);
            if (beforeMin || afterMax) classNames.push('calendar-day--disabled');
            if (selected) classNames.push('calendar-day--selected');
            if (dayData && dayData.full) classNames.push('calendar-day--full');
            else if (dayData && dayData.occupied) classNames.push('calendar-day--occupied');
            const disabled = beforeMin || afterMax ? ' disabled' : '';
            const title = dayData ? ' title="' + value + ': ' + formatDayAvailabilityLabel(dayData) + ' places left"' : '';
            const helper = dayData ? '<span class="calendar-day-meta">' + dayData.remaining_capacity + '</span>' : '';
            dayCells.push('<button type="button" class="' + classNames.join(' ') + '" data-date="' + value + '"' + title + disabled + '><span class="calendar-day-number">' + day + '</span>' + helper + '</button>');
          }
          checkOutMonth.textContent = new Intl.DateTimeFormat(%LOCALE%, { month: 'long', year: 'numeric' }).format(monthStart);
          checkOutPrev.disabled = monthStart <= getMonthStart(effectiveMinDate);
          checkOutNext.disabled = absoluteMaxDate ? monthStart >= getMonthStart(absoluteMaxDate) : false;
          checkOutDays.innerHTML = dayCells.join('');
          fetchCalendarAvailability(monthStart);
        };
        const recalc = () => {
          renderCheckoutCalendar();
          const checkInDate = parseIsoDate(checkIn.value);
          const guestCount = Number.parseInt(guestCountInput.value || '0', 10);
          const overCapacity = updateCapacityWarning();
          if (checkInDate && ((absoluteMinDate && checkInDate < absoluteMinDate) || (absoluteMaxDate && checkInDate > absoluteMaxDate))) {
            output.textContent = 'Selected dates are outside the allowed period for this location.';
            latestRemainingCapacity = null;
            if (liveCapacity) {
              liveCapacity.textContent = availabilityChooseDatesText;
            }
            updateOccupiedDaysSummary();
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
            latestRemainingCapacity = null;
            if (liveCapacity) {
              liveCapacity.textContent = availabilityChooseDatesText;
            }
            updateOccupiedDaysSummary();
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
            latestRemainingCapacity = null;
            if (liveCapacity) {
              liveCapacity.textContent = availabilityChooseDatesText;
            }
            updateOccupiedDaysSummary();
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
            continueButton.disabled = overCapacity;
          }
          details.classList.add('is-ready');
          updateOccupiedDaysSummary();
          fetchLiveAvailability();
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
            event.stopPropagation();
            zone.classList.add('is-dragover');
          });
        });
        ['dragleave', 'drop'].forEach((eventName) => {
          zone.addEventListener(eventName, (event) => {
            event.preventDefault();
            event.stopPropagation();
            zone.classList.remove('is-dragover');
          });
        });
        zone.addEventListener('drop', (event) => {
          const files = event.dataTransfer ? event.dataTransfer.files : null;
          if (!files || !files.length) return;
          input.files = files;
          form.requestSubmit();
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
          const combo = input.closest('.country-combobox');
          const suggestions = combo ? combo.querySelector('.country-suggestions') : null;
          if (!combo || !suggestions) return;
          let allOptions = [];
          try {
            allOptions = JSON.parse(input.dataset.countryOptions || '[]');
          } catch (error) {
            allOptions = [];
          }
          const closeOptions = () => {
            suggestions.hidden = true;
            input.setAttribute('aria-expanded', 'false');
          };
          const showOptions = () => {
            suggestions.hidden = false;
            input.setAttribute('aria-expanded', 'true');
          };
          const renderOptions = () => {
            const query = input.value.trim().toLowerCase();
            const startsWithMatches = allOptions.filter((country) => country.toLowerCase().startsWith(query));
            const containsMatches = query
              ? allOptions.filter((country) => !country.toLowerCase().startsWith(query) && country.toLowerCase().includes(query))
              : [];
            const filtered = startsWithMatches.concat(containsMatches).slice(0, 80);
            suggestions.replaceChildren();
            filtered.forEach((country) => {
              const option = document.createElement('button');
              option.type = 'button';
              option.className = 'country-suggestion';
              option.setAttribute('role', 'option');
              option.textContent = country;
              option.addEventListener('mousedown', (event) => {
                event.preventDefault();
                input.value = country;
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.dispatchEvent(new Event('change', { bubbles: true }));
                closeOptions();
              });
              suggestions.appendChild(option);
            });
            if (filtered.length) {
              showOptions();
            } else {
              closeOptions();
            }
          };
          const openOptions = () => {
            renderOptions();
          };
          input.addEventListener('input', renderOptions);
          input.addEventListener('focus', openOptions);
          input.addEventListener('click', openOptions);
          input.addEventListener('keydown', (event) => {
            const items = Array.from(suggestions.querySelectorAll('.country-suggestion'));
            if (event.key === 'Escape') {
              closeOptions();
              return;
            }
            if (event.key === 'ArrowDown' && items.length) {
              event.preventDefault();
              items[0].focus();
            }
          });
          suggestions.addEventListener('keydown', (event) => {
            const items = Array.from(suggestions.querySelectorAll('.country-suggestion'));
            const currentIndex = items.indexOf(document.activeElement);
            if (event.key === 'Escape') {
              closeOptions();
              input.focus();
            } else if (event.key === 'ArrowDown' && items.length) {
              event.preventDefault();
              items[Math.min(currentIndex + 1, items.length - 1)].focus();
            } else if (event.key === 'ArrowUp') {
              event.preventDefault();
              if (currentIndex <= 0) {
                input.focus();
              } else {
                items[currentIndex - 1].focus();
              }
            }
          });
          input.addEventListener('blur', () => {
            window.setTimeout(() => {
              if (!combo.contains(document.activeElement)) closeOptions();
            }, 120);
          });
        });
        document.addEventListener('mousedown', (event) => {
          countryInputs.forEach((input) => {
            const combo = input.closest('.country-combobox');
            const suggestions = combo ? combo.querySelector('.country-suggestions') : null;
            if (combo && suggestions && !combo.contains(event.target)) {
              suggestions.hidden = true;
              input.setAttribute('aria-expanded', 'false');
            }
          });
        });
      })();
      </script>
      """
    script = script.replace("%CHOOSE_DATES%", "'" + t(lang, "choose_dates_to_calc").replace("'", "\\'") + "'")
    script = script.replace("%CHECKIN_LABEL%", "'" + t(lang, "check_in").replace("'", "\\'") + "'")
    script = script.replace("%SELECT_CHECKOUT%", "'" + t(lang, "check_out").replace("'", "\\'") + "'")
    script = script.replace("%AVAILABILITY_LOADING%", "'" + t(lang, "availability_loading").replace("'", "\\'") + "'")
    script = script.replace("%AVAILABILITY_CHOOSE_DATES%", "'" + t(lang, "availability_choose_dates").replace("'", "\\'") + "'")
    script = script.replace("%AVAILABILITY_REMAINING%", "'" + t(lang, "availability_remaining").replace("'", "\\'") + "'")
    script = script.replace("%AVAILABILITY_FULL%", "'" + t(lang, "availability_full").replace("'", "\\'") + "'")
    script = script.replace("%AVAILABILITY_PARTIAL_DAYS%", "'" + t(lang, "availability_partial_days").replace("'", "\\'") + "'")
    script = script.replace("%AVAILABILITY_FULLY_OPEN%", "'" + t(lang, "availability_fully_open").replace("'", "\\'") + "'")
    script = script.replace("%LOCALE%", "'" + ("sl-SI" if lang == "sl" else "en-GB") + "'")
    return render_layout(t(lang, "app_title"), intro + "".join(cards) + script, notice=notice, lang=lang, current_path="/period", current_params=params, is_admin=admin_mode)


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
        group_street = details_data["group_street"]
        group_house_number = details_data["group_house_number"]
        group_post_code = details_data["group_post_code"]
        group_town = details_data["group_town"]
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
        group_street = details_data["group_street"]
        group_house_number = details_data["group_house_number"]
        group_post_code = details_data["group_post_code"]
        group_town = details_data["group_town"]
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
        <h2>{html.escape(display_location_with_unit(unit['location_name'], unit['unit_name'], lang))}</h2>
        <p>{html.escape(t(lang, "stay"))}: {html.escape(format_stay_range(lang, check_in, check_out))}</p>
        <p>{html.escape(t(lang, "total_nights"))}: {total_nights}</p>
        <p>{html.escape(t(lang, "guests"))}: {html.escape(guest_count)}</p>
        <p>{html.escape(t(lang, "capacity"))}: {unit['max_guests']} {html.escape(t(lang, "guests_word"))}</p>
        <p>{html.escape(t(lang, "price"))}: {display_price}</p>
        <p>{html.escape(t(lang, "estimated_total"))}: EUR {total_price:.2f}</p>
        <p class="summary-warning"><strong>{html.escape(t(lang, "estimated_total_warning"))}</strong></p>
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
      {render_breakdown_table(breakdown, lang)}
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
          <input type="hidden" name="group_street" value="{html.escape(group_street)}">
          <input type="hidden" name="group_house_number" value="{html.escape(group_house_number)}">
          <input type="hidden" name="group_post_code" value="{html.escape(group_post_code)}">
          <input type="hidden" name="group_town" value="{html.escape(group_town)}">
          <input type="hidden" name="organization_name" value="{html.escape(organization_name)}">
          <input type="hidden" name="vat_number" value="{html.escape(vat_number)}">
          <input type="hidden" name="country" value="{html.escape(country)}">
        <input type="hidden" name="adult_count" value="{html.escape(adult_count)}">
        <input type="hidden" name="child_count" value="{html.escape(child_count)}">
          {''.join(
              f'<input type="hidden" name="rental_{item["key"]}_enabled" value="{html.escape(params.get("rental_" + item["key"] + "_enabled", ""))}">'
              f'<input type="hidden" name="rental_{item["key"]}" value="{html.escape(params.get("rental_" + item["key"], ""))}">'
              f'<input type="hidden" name="rental_{item["key"]}_days" value="{html.escape(params.get("rental_" + item["key"] + "_days", ""))}">'
              f'<input type="hidden" name="rental_{item["key"]}_selected_dates" value="{html.escape(params.get("rental_" + item["key"] + "_selected_dates", ""))}">'
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
        {render_step_actions(back_to_contact, f'<button type="submit">{html.escape(t(lang, "create_booking"))}</button>', lang)}
      </form>
    </section>
    """
    return render_layout(t(lang, "booking"), content, lang=lang, current_path="/book", current_params=params)


def build_booking_email_text(payload):
    summary = payload["summary_data"]
    details = summary["details_data"]
    breakdown = summary["breakdown"]
    detail_blocks = build_submitted_group_details_html(details, "en")
    breakdown_table = render_breakdown_table(breakdown, "en")
    return f"""
<html>
  <body style="font-family: Georgia, 'Times New Roman', serif; color: #203127; background: #f3efe4; margin: 0; padding: 24px;">
    <div style="max-width: 960px; margin: 0 auto;">
      <h1 style="margin: 0 0 16px;">Booking summary</h1>
      <div style="background: #fffaf0; border: 1px solid #d8cfbc; border-radius: 18px; padding: 20px; margin-bottom: 16px;">
        <h2 style="margin-top: 0;">{html.escape(display_location_with_unit(payload['location_name'], payload['unit_name'], 'en'))}</h2>
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
            f"Booking summary\n\nLocation: {display_location_with_unit(payload['location_name'], payload['unit_name'], 'en')}\n"
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
        f"Booking summary\n\nLocation: {display_location_with_unit(payload['location_name'], payload['unit_name'], 'en')}\nStay: {payload['check_in'].isoformat()} to {payload['check_out'].isoformat()}\nGuests: {payload['guest_count']}\nTotal: EUR {payload['total_price']:.2f}"
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

    unit_leader_name = contact_full_name(form, "unit_leader")
    unit_leader_address = contact_full_address(form, "unit_leader")
    unit_leader_email = form.get("unit_leader_email", "").strip()
    unit_leader_phone = form.get("unit_leader_phone", "").strip()
    contact_same_as_unit_leader = form.get("contact_same_as_unit_leader", "") == "on"
    contact_person_name = contact_full_name(form, "contact_person")
    contact_person_phone = form.get("contact_person_phone", "").strip()
    contact_person_address = contact_full_address(form, "contact_person")
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
    group_street = form.get("group_street", "").strip()
    group_house_number = form.get("group_house_number", "").strip()
    group_post_code = form.get("group_post_code", "").strip()
    group_town = form.get("group_town", "").strip()
    organization_name = form.get("organization_name", "").strip()
    vat_number = form.get("vat_number", "").strip()
    country = form.get("country", "").strip()
    rental_comments = form.get("rental_comments", "").strip()
    adult_total, child_total, section_rows = calculate_section_totals(form)
    adult_count = str(adult_total) if adult_total else ""
    child_count = str(child_total) if child_total else ""
    selected_rentals = parse_rental_quantities_for_location(form, unit["location_name"])
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
    is_slovenia_other_group = is_slovenia_country(form.get("origin_country", "").strip()) and form.get("member_category", "").strip() == "other"
    leader_label = contact_leader_label("en", laski_group_type == "non_scouts" or is_slovenia_other_group)
    if unit_leader_name:
        metadata_lines.append(f"{leader_label}: {unit_leader_name}")
    if unit_leader_address:
        metadata_lines.append(f"{leader_label} address: {unit_leader_address}")
    if unit_leader_email:
        metadata_lines.append(f"{leader_label} email: {unit_leader_email}")
    if unit_leader_phone:
        metadata_lines.append(f"{leader_label} phone: {unit_leader_phone}")
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
    if group_street:
        metadata_lines.append(f"Street: {group_street}")
    if group_house_number:
        metadata_lines.append(f"House number: {group_house_number}")
    if group_post_code:
        metadata_lines.append(f"Post code: {group_post_code}")
    if group_town:
        metadata_lines.append(f"Town: {group_town}")
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
        rental_violations, _ = validate_rental_availability(connection, check_in, check_out, selected_rentals)
        errors.extend(rental_violations)

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
        section_rows,
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
        "selected_rentals": selected_rentals,
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
        rental_violations, _ = validate_rental_availability(
            connection,
            payload["check_in"],
            payload["check_out"],
            payload["selected_rentals"],
        )
        if rental_violations:
            connection.rollback()
            return rental_violations

    cursor = connection.execute(
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
    booking_id = cursor.lastrowid
    for entry in payload["selected_rentals"]:
        connection.execute(
            """
            insert into booking_rentals (booking_id, item_key, quantity, length, selected_dates)
            values (?, ?, ?, ?, ?)
            """,
            (
                booking_id,
                entry["item"]["key"],
                format_decimal_display(entry["quantity"]),
                entry.get("length", ""),
                ",".join(entry.get("selected_dates", [])),
            ),
        )
    connection.commit()
    return []


def render_admin_page(connection, notice="", filters=None):
    filters = filters or {}
    lang = get_lang(filters.get("lang", "en"))
    bookings = []
    for booking in fetch_bookings(connection):
        booking_data = dict(booking)
        booking_data["country"] = extract_country_from_notes(booking_data.get("notes", ""))
        booking_data["group_name"] = extract_group_name_from_notes(booking_data.get("notes", "")) or booking_data.get("guest_name", "")
        bookings.append(booking_data)
    locations = fetch_locations(connection)
    sorted_bookings = sorted(
        bookings,
        key=lambda booking: (
            booking.get("country", "").strip().lower(),
            booking.get("check_in", ""),
            booking.get("created_at", ""),
            booking.get("id", 0),
        ),
    )
    booking_board_html = render_admin_booking_board(connection, locations, sorted_bookings, lang)
    selected_campsite = filters.get("campsite", "").strip()
    selected_country = filters.get("country", "").strip()
    if selected_campsite:
        sorted_bookings = [booking for booking in sorted_bookings if booking["location_name"] == selected_campsite]
    if selected_country:
        sorted_bookings = [booking for booking in sorted_bookings if booking.get("country", "") == selected_country]
    sort_specs = [
        ("status_sort", lambda booking: booking_status_label(booking["status"], lang).lower()),
        ("guests_sort", lambda booking: int(booking["guest_count"])),
        ("applied_sort", lambda booking: booking.get("created_at", "")),
        ("stay_sort", lambda booking: booking.get("check_in", "")),
        ("group_sort", lambda booking: booking.get("group_name", "").lower()),
        ("id_sort", lambda booking: int(booking["id"])),
    ]
    for param_name, key_fn in sort_specs:
        direction = filters.get(param_name, "").strip().lower()
        if direction in {"asc", "desc"}:
            sorted_bookings = sorted(sorted_bookings, key=key_fn, reverse=direction == "desc")
    campsite_options = "".join(
        f'<option value="{html.escape(location["name"])}"{" selected" if selected_campsite == location["name"] else ""}>{html.escape(location["name"])}</option>'
        for location in locations
    )
    country_options = "".join(
        f'<option value="{html.escape(country)}"{" selected" if selected_country == country else ""}>{html.escape(country)}</option>'
        for country in sorted({booking["country"] for booking in bookings if booking.get("country")}, key=lambda value: value.lower())
    )
    def select_options(selected_value, option_pairs):
        return "".join(
            f'<option value="{value}"{" selected" if selected_value == value else ""}>{label}</option>'
            for value, label in option_pairs
        )
    booking_rows = []
    booking_detail_modals = []
    for booking in sorted_bookings:
        booking_view = build_admin_booking_view_data(connection, booking)
        modal_id = f"admin-booking-details-{booking['id']}"
        if booking_view:
            booking_detail_modals.append(
                f"""
                <div class="admin-modal" id="{modal_id}" hidden>
                  <div class="admin-modal-backdrop" data-admin-modal-close></div>
                  <div class="admin-modal-dialog" role="dialog" aria-modal="true" aria-labelledby="{modal_id}-title">
                    <div class="admin-modal-header">
                      <div>
                        <h3 id="{modal_id}-title">{html.escape(tf(lang, "admin_booking_details", id=booking["id"]))}</h3>
                        <p>{html.escape(display_location_with_unit(booking['location_name'], booking['unit_name'], lang))} | {html.escape(format_stay_range(lang, booking['check_in'], booking['check_out']))}</p>
                      </div>
                      <button type="button" class="admin-modal-close" data-admin-modal-close aria-label="Close">x</button>
                    </div>
                    <div class="admin-modal-body">
                      <section class="panel">
                        <h2>{html.escape(t(lang, "admin_reservation_details"))}</h2>
                        {build_submitted_group_details_html(booking_view['details_data'], lang)}
                      </section>
                      <section class="panel">
                        <h2>{html.escape(t(lang, "admin_calculation"))}</h2>
                        {render_breakdown_table(booking_view['breakdown'], lang)}
                      </section>
                    </div>
                  </div>
                </div>
                """
            )
        booking_rows.append(
            f"""
            <tr id="booking-{booking['id']}" class="admin-booking-row {booking_status_class(booking['status'])}">
              <td>{booking['id']}</td>
              <td>{html.escape(booking['location_name'])}</td>
              <td>{html.escape(booking['group_name'])}<br><span class="muted">{html.escape(booking['guest_name'])}</span></td>
              <td>{booking['check_in']} to {booking['check_out']}</td>
              <td>{html.escape(booking.get('created_at', '').split(' ')[0])}</td>
              <td>{html.escape(booking.get('country', ''))}</td>
              <td>{booking['guest_count']}</td>
              <td>{html.escape(booking_status_label(booking['status'], lang))}</td>
              <td>EUR {Decimal(str(booking['total_price'])):.2f}</td>
              <td>
                <form method="post" action="/admin/status" class="admin-status-form" id="admin-status-form-{booking['id']}">
                  <input type="hidden" name="booking_id" value="{booking['id']}">
                  <input type="hidden" name="lang" value="{lang}">
                  <input type="hidden" name="return_anchor" value="booking-{booking['id']}">
                  <select name="status">
                    {render_status_options(booking['status'], lang)}
                  </select>
                </form>
              </td>
            </tr>
            <tr class="admin-booking-actions-row {booking_status_class(booking['status'])}">
              <td colspan="10">
                <div class="admin-booking-actions">
                  <button type="button" class="button button-secondary admin-details-button" data-admin-details-target="{modal_id}">{html.escape(t(lang, "admin_details"))}</button>
                  <button type="submit" class="admin-update-button" form="admin-status-form-{booking['id']}">{html.escape(t(lang, "admin_update"))}</button>
                </div>
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
    <section class="panel" id="admin-bookings">
      <h2>{html.escape(t(lang, "admin_manual_booking"))}</h2>
      <form method="post" action="/admin/manual" class="booking-form">
        <input type="hidden" name="lang" value="{lang}">
        <label>
          {html.escape(t(lang, "admin_unit"))}
          <select name="unit_id">{''.join(unit_options)}</select>
        </label>
        <label>
          {html.escape(t(lang, "admin_check_in"))}
          <input type="date" name="check_in" required>
        </label>
        <label>
          {html.escape(t(lang, "admin_check_out"))}
          <input type="date" name="check_out" required>
        </label>
        <label>
          {html.escape(t(lang, "guests"))}
          <input type="number" name="guest_count" min="1" value="2" required>
        </label>
        <label>
          {html.escape(t(lang, "full_name"))}
          <input type="text" name="guest_name" required>
        </label>
        <label>
          {html.escape(t(lang, "email"))}
          <input type="email" name="guest_email" required>
        </label>
        <label>
          {html.escape(t(lang, "phone"))}
          <input type="text" name="guest_phone">
        </label>
        <label>
          {html.escape(t(lang, "admin_status"))}
          <select name="status">
            <option value="pending">pending</option>
            <option value="confirmed">confirmed</option>
            <option value="fee_paid">paid reservation fee</option>
          </select>
        </label>
        <label class="checkbox">
          <input type="checkbox" name="overbook_allowed">
          {html.escape(t(lang, "admin_allow_overbooking"))}
        </label>
        <label>
          {html.escape(t(lang, "notes"))}
          <textarea name="notes" rows="3"></textarea>
        </label>
        <button type="submit">{html.escape(t(lang, "admin_create_booking"))}</button>
      </form>
    </section>
    <section class="panel">
      <h2>{html.escape(t(lang, "admin_reservation_board"))}</h2>
      <p>{html.escape(t(lang, "admin_board_intro"))}</p>
    </section>
    {booking_board_html}
    <section class="panel">
      <h2>{html.escape(t(lang, "admin_bookings"))}</h2>
      <div class="table-wrap">
        <table class="admin-bookings-table">
          <thead>
            <tr>
              <th>ID
                <select class="admin-header-filter" data-admin-filter="id_sort">
                  <option value="">{html.escape(t(lang, "admin_default"))}</option>
                  {select_options(filters.get("id_sort", ""), [("asc", "a-z"), ("desc", "z-a")])}
                </select>
              </th>
              <th>{html.escape(t(lang, "admin_campsite"))}
                <select class="admin-header-filter" data-admin-filter="campsite">
                  <option value="">{html.escape(t(lang, "admin_all_campsites"))}</option>
                  {campsite_options}
                </select>
              </th>
              <th>{html.escape(t(lang, "admin_group_name"))}
                <select class="admin-header-filter" data-admin-filter="group_sort">
                  <option value="">{html.escape(t(lang, "admin_default"))}</option>
                  {select_options(filters.get("group_sort", ""), [("asc", "a-z"), ("desc", "z-a")])}
                </select>
              </th>
              <th>{html.escape(t(lang, "admin_stay"))}
                <select class="admin-header-filter" data-admin-filter="stay_sort">
                  <option value="">{html.escape(t(lang, "admin_default"))}</option>
                  {select_options(filters.get("stay_sort", ""), [("desc", "newest"), ("asc", "latest")])}
                </select>
              </th>
              <th>{html.escape(t(lang, "admin_applied"))}
                <select class="admin-header-filter" data-admin-filter="applied_sort">
                  <option value="">{html.escape(t(lang, "admin_default"))}</option>
                  {select_options(filters.get("applied_sort", ""), [("asc", "a-z"), ("desc", "z-a")])}
                </select>
              </th>
              <th>{html.escape(t(lang, "country_label"))}
                <select class="admin-header-filter" data-admin-filter="country">
                  <option value="">{html.escape(t(lang, "admin_all_countries"))}</option>
                  {country_options}
                </select>
              </th>
              <th>{html.escape(t(lang, "guests"))}
                <select class="admin-header-filter" data-admin-filter="guests_sort">
                  <option value="">{html.escape(t(lang, "admin_default"))}</option>
                  {select_options(filters.get("guests_sort", ""), [("asc", "low-high"), ("desc", "high-low")])}
                </select>
              </th>
              <th>{html.escape(t(lang, "admin_status"))}
                <select class="admin-header-filter" data-admin-filter="status_sort">
                  <option value="">{html.escape(t(lang, "admin_default"))}</option>
                  {select_options(filters.get("status_sort", ""), [("asc", "a-z"), ("desc", "z-a")])}
                </select>
              </th>
              <th>{html.escape(t(lang, "admin_total"))}</th>
              <th>{html.escape(t(lang, "admin_action"))}</th>
            </tr>
          </thead>
          <tbody>
            {''.join(booking_rows) or f'<tr><td colspan="10">{html.escape(t(lang, "admin_no_bookings"))}</td></tr>'}
          </tbody>
        </table>
      </div>
    </section>
    {''.join(booking_detail_modals)}
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
      const headerFilters = document.querySelectorAll('.admin-header-filter');
      const scrollKey = 'adminBookingsScrollY';
      const savedScrollY = window.sessionStorage.getItem(scrollKey);
      if (savedScrollY !== null) {{
        window.scrollTo(0, Number.parseInt(savedScrollY, 10) || 0);
        window.sessionStorage.removeItem(scrollKey);
      }}
      headerFilters.forEach((input) => {{
        input.addEventListener('change', () => {{
          window.sessionStorage.setItem(scrollKey, String(window.scrollY || window.pageYOffset || 0));
          const params = new URLSearchParams(window.location.search);
          headerFilters.forEach((field) => {{
            const key = field.getAttribute('data-admin-filter');
            const value = field.value.trim();
            if (!key) return;
            if (value) {{
              params.set(key, value);
            }} else {{
              params.delete(key);
            }}
          }});
          params.delete('notice');
          const query = params.toString();
          window.location.href = query ? '/admin?' + query : '/admin';
        }});
      }});
      const closeModal = (modal) => {{
        if (!modal) return;
        modal.hidden = true;
        document.body.classList.remove('admin-modal-open');
      }};
      const openModal = (modal) => {{
        if (!modal) return;
        modal.hidden = false;
        document.body.classList.add('admin-modal-open');
      }};
      document.querySelectorAll('[data-admin-details-target]').forEach((button) => {{
        button.addEventListener('click', () => {{
          openModal(document.getElementById(button.getAttribute('data-admin-details-target')));
        }});
      }});
      document.querySelectorAll('[data-admin-modal-close]').forEach((button) => {{
        button.addEventListener('click', () => {{
          closeModal(button.closest('.admin-modal'));
        }});
      }});
      document.addEventListener('keydown', (event) => {{
        if (event.key !== 'Escape') return;
        document.querySelectorAll('.admin-modal').forEach((modal) => {{
          if (!modal.hidden) closeModal(modal);
        }});
      }});
    }})();
    </script>
    """
    return render_layout(t(lang, "admin"), content, notice=notice, lang=lang, current_path="/admin", current_params=filters, is_admin=True)


def render_status_options(selected, lang="en"):
    statuses = BOOKING_STATUSES
    options = []
    for status in statuses:
        selected_attr = " selected" if status == selected else ""
        options.append(f'<option value="{status}"{selected_attr}>{booking_status_label(status, lang)}</option>')
    return "".join(options)


def handle_location_availability_api(environ):
    query_params = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
    location_id = (query_params.get("location_id") or [""])[0]
    check_in_value = (query_params.get("check_in") or [""])[0]
    check_out_value = (query_params.get("check_out") or [""])[0]
    if not location_id or not check_in_value or not check_out_value:
        return json_response({"error": "Missing parameters."}, status="400 Bad Request")
    try:
        check_in = parse_date(check_in_value)
        check_out = parse_date(check_out_value)
    except ValueError:
        return json_response({"error": "Invalid dates."}, status="400 Bad Request")
    if check_out <= check_in:
        return json_response({"error": "Check-out must be after check-in."}, status="400 Bad Request")
    with closing(get_connection()) as connection:
        summary = get_location_availability_summary(connection, location_id, check_in, check_out)
    if not summary:
        return json_response({"error": "Location not found."}, status="404 Not Found")
    return json_response(summary)


def handle_location_calendar_api(environ):
    query_params = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
    location_id = (query_params.get("location_id") or [""])[0]
    month_value = (query_params.get("month") or [""])[0]
    if not location_id or not month_value:
        return json_response({"error": "Missing parameters."}, status="400 Bad Request")
    try:
        month_start = datetime.strptime(month_value, "%Y-%m").date().replace(day=1)
    except ValueError:
        return json_response({"error": "Invalid month."}, status="400 Bad Request")
    next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    with closing(get_connection()) as connection:
        summary = get_location_daily_availability(connection, location_id, month_start, next_month)
    if not summary:
        return json_response({"error": "Location not found."}, status="404 Not Found")
    return json_response(summary)


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
        ".pdf": "application/pdf",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }.get(suffix, "application/octet-stream")
    data = target.read_bytes()
    return "200 OK", [("Content-Type", content_type), ("Content-Length", str(len(data)))], [data]


def application(environ, start_response):
    path = environ.get("PATH_INFO", "/")
    method = environ.get("REQUEST_METHOD", "GET").upper()

    try:
        if path.startswith("/static/"):
            status, headers, body = serve_static(environ)
        elif path == "/api/location-availability" and method == "GET":
            status, headers, body = handle_location_availability_api(environ)
        elif path == "/api/location-calendar" and method == "GET":
            status, headers, body = handle_location_calendar_api(environ)
        elif path == "/" and method == "GET":
            params = {key: values[0] for key, values in parse_qs(environ.get("QUERY_STRING", "")).items()}
            with closing(get_connection()) as connection:
                status, headers, body = html_response(render_information_page(connection, params))
        elif path == "/period" and method == "GET":
            params = {key: values[0] for key, values in parse_qs(environ.get("QUERY_STRING", "")).items()}
            params["admin_mode"] = "1" if is_admin_request(environ) else ""
            with closing(get_connection()) as connection:
                status, headers, body = html_response(render_search_page(connection, params, []))
        elif path == "/admin-login" and method == "GET":
            lang = get_lang(parse_qs(environ.get("QUERY_STRING", "")).get("lang", ["en"])[0])
            if is_admin_request(environ):
                status, headers, body = redirect_with_cookie(f"/period?lang={lang}&notice={quote_plus(t(lang, 'media_tools_unlocked'))}", "campsite_admin=1; Path=/")
            else:
                status, headers, body = html_response(render_admin_login_page(lang))
        elif path == "/admin-login" and method == "POST":
            form = read_post_data(environ)
            lang = get_lang(form.get("lang", "en"))
            if form.get("username", "") == ADMIN_USERNAME and form.get("password", "") == ADMIN_PASSWORD:
                status, headers, body = redirect_with_cookie(f"/period?lang={lang}&notice={quote_plus(t(lang, 'media_tools_unlocked'))}", "campsite_admin=1; Path=/")
            else:
                status, headers, body = html_response(render_admin_login_page(lang, error=t(lang, "invalid_username_password")))
        elif path == "/admin-logout" and method == "POST":
            lang = get_lang(read_post_data(environ).get("lang", "en"))
            status, headers, body = redirect_with_cookie(f"/period?lang={lang}&notice={quote_plus(t(lang, 'media_tools_locked'))}", "campsite_admin=; Path=/; Max-Age=0")
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
                group_errors = validate_group_details_params(params)
                contact_errors = validate_contact_details_params(params) if not group_errors else []
                if group_errors:
                    status, headers, body = html_response(render_details_page(connection, params, group_errors))
                elif contact_errors:
                    status, headers, body = html_response(render_contact_page(connection, params, contact_errors))
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
            status, headers, body = redirect_response(add_query_params_to_url(return_to, {"lang": lang, "notice": notice}))
        elif path == "/delete-image" and method == "POST":
            lang, notice, return_to = delete_gallery_image(environ)
            status, headers, body = redirect_response(add_query_params_to_url(return_to, {"lang": lang, "notice": notice, "open_upload": "1"}))
        elif path == "/make-primary-image" and method == "POST":
            lang, notice, return_to = make_gallery_image_primary(environ)
            status, headers, body = redirect_response(add_query_params_to_url(return_to, {"lang": lang, "notice": notice}))
        elif path == "/move-image" and method == "POST":
            lang, notice, return_to = move_gallery_image(environ)
            status, headers, body = redirect_response(add_query_params_to_url(return_to, {"lang": lang, "notice": notice}))
        elif path == "/book" and method == "GET":
            query_params = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
            params = {key: values[0] for key, values in query_params.items()}
            if "accommodation_type" in query_params:
                params["accommodation_type"] = query_params["accommodation_type"]
            with closing(get_connection()) as connection:
                group_errors = validate_group_details_params(params)
                contact_errors = validate_contact_details_params(params)
                rental_errors = validate_rental_params(connection, params) if not group_errors else []
                if group_errors:
                    status, headers, body = html_response(render_details_page(connection, params, group_errors))
                elif contact_errors:
                    status, headers, body = html_response(render_contact_page(connection, params, contact_errors))
                elif rental_errors:
                    status, headers, body = html_response(render_rental_page(connection, params, rental_errors))
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
                    status, headers, body = html_response(render_admin_page(connection, notice=params.get("notice", ""), filters=params))
        elif path == "/admin/status" and method == "POST":
            form = read_post_data(environ)
            lang = get_lang(form.get("lang", "en"))
            if not is_admin_request(environ):
                status, headers, body = redirect_response(f"/admin-login?lang={lang}")
            else:
                with closing(get_connection()) as connection:
                    booking_id = int(form.get("booking_id", "0"))
                    connection.execute(
                        "update bookings set status = ?, updated_at = current_timestamp where id = ?",
                        (form.get("status", "pending"), booking_id),
                    )
                    connection.commit()
                    return_anchor = form.get("return_anchor", "").strip() or f"booking-{booking_id}"
                    status, headers, body = redirect_response(f"/admin?lang={lang}&notice={quote_plus(t(lang, 'admin_status_updated'))}#{quote_plus(return_anchor)}")
        elif path == "/admin/manual" and method == "POST":
            form = read_post_data(environ)
            lang = get_lang(form.get("lang", "en"))
            if not is_admin_request(environ):
                status, headers, body = redirect_response(f"/admin-login?lang={lang}")
            else:
                with closing(get_connection()) as connection:
                    payload, errors = validate_booking_form(connection, form, admin_mode=True)
                    if errors:
                        status, headers, body = html_response(render_admin_page(connection, notice="; ".join(errors), filters=form))
                    else:
                        insert_errors = insert_booking(connection, payload)
                        notice = t(lang, "admin_booking_created") if not insert_errors else "; ".join(insert_errors)
                        safe_notice = quote_plus(notice)
                        status, headers, body = redirect_response(f"/admin?lang={lang}&notice={safe_notice}")
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

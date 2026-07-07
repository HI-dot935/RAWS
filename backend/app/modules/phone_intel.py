"""
Fully offline phone number intelligence built on Google's libphonenumber
numbering-plan data via the `phonenumbers` package. No network calls -
everything here is derived from bundled numbering metadata (country,
region, number type, and, where the optional geocoder/carrier data is
present, approximate carrier/geographic description).
"""
import phonenumbers
from phonenumbers import geocoder, carrier as carrier_lookup, timezone as tz_lookup, PhoneNumberType

NUMBER_TYPE_NAMES = {
    PhoneNumberType.FIXED_LINE: "Fixed line",
    PhoneNumberType.MOBILE: "Mobile",
    PhoneNumberType.FIXED_LINE_OR_MOBILE: "Fixed line or mobile",
    PhoneNumberType.TOLL_FREE: "Toll free",
    PhoneNumberType.PREMIUM_RATE: "Premium rate",
    PhoneNumberType.SHARED_COST: "Shared cost",
    PhoneNumberType.VOIP: "VoIP",
    PhoneNumberType.PERSONAL_NUMBER: "Personal number",
    PhoneNumberType.PAGER: "Pager",
    PhoneNumberType.UAN: "UAN",
    PhoneNumberType.VOICEMAIL: "Voicemail",
    PhoneNumberType.UNKNOWN: "Unknown",
}


def analyze_phone(raw_number: str, default_region: str | None = None) -> dict:
    result = {"input": raw_number}
    try:
        parsed = phonenumbers.parse(raw_number, default_region)
    except phonenumbers.NumberParseException as e:
        result["valid"] = False
        result["error"] = str(e)
        result["hint"] = "Include a country code, e.g. +1 555 123 4567, or specify a default region."
        return result

    result["valid"] = phonenumbers.is_valid_number(parsed)
    result["possible"] = phonenumbers.is_possible_number(parsed)
    result["e164"] = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    result["international"] = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
    result["national"] = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL)
    result["country_code"] = parsed.country_code
    result["region_code"] = phonenumbers.region_code_for_number(parsed)
    result["number_type"] = NUMBER_TYPE_NAMES.get(phonenumbers.number_type(parsed), "Unknown")
    result["geographic_description"] = geocoder.description_for_number(parsed, "en") or None
    carriers = carrier_lookup.name_for_number(parsed, "en")
    result["carrier_hint"] = carriers or "Not available offline (common for mobile-ported or VoIP numbers)"
    result["timezones"] = list(tz_lookup.time_zones_for_number(parsed))

    bits = [
        "valid" if result["valid"] else "NOT a valid number",
        result["number_type"],
        result["geographic_description"] or result["region_code"] or "",
    ]
    result["summary"] = " · ".join(b for b in bits if b)
    return result

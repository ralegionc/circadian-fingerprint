"""
Language editions to profile, with the timezone most of their readership sits in.

`tz` is used only to re-express UTC hours as local clock time. For editions whose
readers are concentrated in one country (ja, ko, pl, th, he) this is close to
exact. For editions spread across many timezones (en, es, ar, pt) it is a rough
anchor, and `spread` marks them so the write-up can say so rather than implying
a precision the data does not have.
"""

LANGUAGES = [
    # code,  label,            tz,                     spread
    ("ja",   "Japanese",       "Asia/Tokyo",           False),
    ("ko",   "Korean",         "Asia/Seoul",           False),
    ("zh",   "Chinese",        "Asia/Taipei",          False),
    ("th",   "Thai",           "Asia/Bangkok",         False),
    ("vi",   "Vietnamese",     "Asia/Ho_Chi_Minh",     False),
    ("id",   "Indonesian",     "Asia/Jakarta",         False),
    ("hi",   "Hindi",          "Asia/Kolkata",         False),
    ("fa",   "Persian",        "Asia/Tehran",          False),
    ("he",   "Hebrew",         "Asia/Jerusalem",       False),
    ("ar",   "Arabic",         "Africa/Cairo",         True),
    ("tr",   "Turkish",        "Europe/Istanbul",      False),
    ("ru",   "Russian",        "Europe/Moscow",        True),
    ("uk",   "Ukrainian",      "Europe/Kyiv",          False),
    ("pl",   "Polish",         "Europe/Warsaw",        False),
    ("de",   "German",         "Europe/Berlin",        False),
    ("nl",   "Dutch",          "Europe/Amsterdam",     False),
    ("sv",   "Swedish",        "Europe/Stockholm",     False),
    ("fi",   "Finnish",        "Europe/Helsinki",      False),
    ("fr",   "French",         "Europe/Paris",         False),
    ("it",   "Italian",        "Europe/Rome",          False),
    ("es",   "Spanish",        "Europe/Madrid",        True),
    ("pt",   "Portuguese",     "America/Sao_Paulo",    True),
    ("en",   "English",        "America/New_York",     True),
]

BY_CODE = {c: (label, tz, spread) for c, label, tz, spread in LANGUAGES}

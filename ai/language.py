def detect_language(text):
    if not text:
        return "unknown"
    for ch in text:
        code = ord(ch)
        if 0x0C80 <= code <= 0x0CFF:
            return "Kannada"
        if 0x0900 <= code <= 0x097F:
            return "Hindi"
        if 0x0B80 <= code <= 0x0BFF:
            return "Tamil"
        if 0x0C00 <= code <= 0x0C7F:
            return "Telugu"
        if 0x0D00 <= code <= 0x0D7F:
            return "Malayalam"
    return "English / Latin-script"

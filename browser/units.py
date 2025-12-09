UNITS = [
    (64*27*27, 'chest{} of shulker boxes', 's'),
    (64*27, 'chest{}', 's'),
    (64, 'stack{}', 's'),
]

def to_minecraft(number):
    parts = []
    for unit, name, suffix in UNITS:
        count, number = divmod(number, unit)
        if count:
            english = name.format(suffix if count > 1 else '')
            parts.append(f'{count} {english}')
    if number or not len(parts):
        parts.append(str(number))
    text = ' and '.join(parts)
    return text

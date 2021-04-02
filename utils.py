

def is_valid_number(number):
    try:
        float_number = float(number)
        return float_number
    except Exception as e:
        return False

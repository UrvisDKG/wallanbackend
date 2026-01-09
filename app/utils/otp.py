import random

_otp_store = {}

def generate_otp(phone: str):
    otp = random.randint(1000, 9999)
    print(f"OTP for {phone}: {otp}", flush=True)
    _otp_store[phone] = otp
    return otp

def verify_otp(phone: str, otp: int):
    if phone in _otp_store and str(_otp_store[phone]) == str(otp):
        return True
    return False

import os

class Config:
    #  SECURITY 
    SECRET_KEY = os.environ.get("SECRET_KEY") or "super-secret-key"

    #  DATABASE 
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get("DATABASE_URL")
        or "mysql+pymysql://root:tiger@localhost/supermarket_db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    #  LOGIN 
    REMEMBER_COOKIE_DURATION = 3600  # 1 hour

    #  EMAIL  (✔ FIXED & VERIFIED)
    MAIL_SERVER = "smtp.gmail.com"
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    MAIL_SUPPRESS_SEND = False          # ✅ VERY IMPORTANT
    MAIL_DEBUG = True                   # ✅ helps in terminal logs

    MAIL_USERNAME = "sahil.salunke816@gmail.com"
    MAIL_PASSWORD = "thjrwshgyeterjlj"   # Gmail App Password
    MAIL_DEFAULT_SENDER = (
        "Smart Supermarket POS",
        "sahil.salunke816@gmail.com"
    )

    #razorpay keyss
    RAZORPAY_KEY_ID = "rzp_test_SGt8M3dSyJAjOV"
    RAZORPAY_KEY_SECRET = "M1bhfcbZpO1zHbGPxeUCmbw5"

    #  LOW STOCK ALERT 
    LOW_STOCK_THRESHOLD = 10

    LOW_STOCK_RECIPIENTS = [
        "sahil.salunke999@gmail.com"
    ]
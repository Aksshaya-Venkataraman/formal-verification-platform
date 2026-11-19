from flask_limiter import Limiter

from fvp.security import rate_limit_key

limiter = Limiter(key_func=rate_limit_key, headers_enabled=True, strategy="moving-window")

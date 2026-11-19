# Threads let several users verify at once; prover processes are capped
# separately by MAX_CONCURRENT_PROVERS.
bind = "0.0.0.0:8000"
workers = 2
worker_class = "gthread"
threads = 4
# Must exceed the longest verification (MAX_TIME_LIMIT plus process start-up).
timeout = 120
graceful_timeout = 30
keepalive = 5
accesslog = None
errorlog = "-"
loglevel = "info"
limit_request_line = 4094
limit_request_fields = 50

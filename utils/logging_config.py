import logging

def init_logging(level=logging.INFO):
    level = logging.INFO
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=level,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler(),  # console
            logging.FileHandler("app.log", encoding="utf-8")  # file
        ]
    )
import logging


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    # httpx's INFO message includes the complete request URL. Provider APIs use
    # query-string credentials, so emitting that message would write Meta and
    # Similarweb secrets into the local runtime log.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

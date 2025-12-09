# backend/app/services/ticket_service.py
import logging
from app.services.db_service import insert_prediction

logger = logging.getLogger("ticket_service")


def create_ticket(machine_id: str, prediction_id: str, priority: str = "normal", details: dict = None):
    """Very light-weight ticket creator that currently just logs & returns a ticket id.
    You can later implement DB insert or call an external ticketing API.
    """
    ticket = {
        "machine_id": machine_id,
        "prediction_id": prediction_id,
        "priority": priority,
        "details": details or {},
    }
    logger.info("Ticket created (simulated): %s", ticket)
    # TODO: insert into tickets table (create SQL) or call external system
    return "ticket-simulated-" + prediction_id
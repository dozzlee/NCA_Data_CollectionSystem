from celery import shared_task

from .workbook_import import process_workbook_import_record


@shared_task(name="forms_engine.process_workbook_import")
def process_workbook_import(import_id):
    return process_workbook_import_record(import_id)

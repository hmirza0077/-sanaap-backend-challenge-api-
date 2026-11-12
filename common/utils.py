import os
import uuid


def upload_document_prefix_helper(instance, filename):
    # random file name -> the stored path cannot be guessed
    _, file_extension = os.path.splitext(filename)
    return f"documents/{uuid.uuid4().hex}{file_extension.lower()}"

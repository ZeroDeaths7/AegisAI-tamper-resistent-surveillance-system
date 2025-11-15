"""
AEGIS Backend Package
Database and validation modules for tamper detection system.
"""

from .database import aegis_db, save_glare_image, get_incident_description
from .watermark_validator import validate_video

__all__ = [
    'aegis_db',
    'save_glare_image',
    'get_incident_description',
    'validate_video'
]
